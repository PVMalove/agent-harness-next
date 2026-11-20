"""Egress proxy of the docker executor's sidecar: HTTP(S) to the pinned plan hosts only (issue #706).

The sidecar sits on the default bridge and on the worker's ``--internal`` network, so it is the
worker's only route out. It speaks plain HTTP forwarding and ``CONNECT`` and nothing else: ssh,
raw TCP and any other protocol are not proxied. Standard library only, because it ships as a
drift-checked payload and its image is built by the operator, never by the harness.

Rules, applied to every request before any upstream connection:

* the target host must equal one entry of ``HARNESS_EGRESS_ALLOWED_HOSTS`` (exact match, no
  wildcards or subdomains), and an IP-literal target is refused even when it is listed;
* the target port must be 80 or 443;
* the host is resolved once, and a host with any loopback, link-local, unspecified or multicast
  answer is refused as a whole; the connection then uses the checked address, never a second lookup.

Everything else gets ``403``. The resolver, the address policy and the port set are injectable so a
test can reach a local server without weakening the defaults.

When the sidecar's environment names an upstream proxy (``https_proxy``/``HTTPS_PROXY`` for
``CONNECT``, ``http_proxy``/``HTTP_PROXY`` for plain HTTP; lower case wins), an allowed request is
chained through it: ``CONNECT`` for tunnels, an absolute-form request line for HTTP, with
``Proxy-Authorization`` from the proxy URL's credentials. The checks above still run first on the
target; the upstream proxy is configuration, never a target. A host matching ``no_proxy``/``NO_PROXY``,
a scheme without an upstream, and a loopback or unspecified upstream (unreachable from a container)
connect directly (issue #1201).
"""

from __future__ import annotations

import base64
import ipaddress
import os
import select
import signal
import socket
import socketserver
import sys
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import FrameType
from urllib.parse import unquote, urlsplit
from urllib.request import (  # type: ignore[attr-defined]  # absent from typeshed
    proxy_bypass_environment,
)

ALLOWED_HOSTS_ENV = "HARNESS_EGRESS_ALLOWED_HOSTS"
LISTEN_PORT = 3128
DEFAULT_PORTS = frozenset({80, 443})
CONNECT_TIMEOUT_SECONDS = 10
# A tunnel or a response that stays silent this long is closed.
IDLE_TIMEOUT_SECONDS = 120
MAX_HEAD_BYTES = 64 * 1024
_CHUNK = 64 * 1024
# Headers that describe the client-to-proxy hop: they never reach the upstream.
_HOP_HEADERS = frozenset(
    {"connection", "proxy-connection", "proxy-authorization", "keep-alive"}
)

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
Resolver = Callable[[str, int], Sequence[str]]
AddressPolicy = Callable[[IPAddress], bool]
Log = Callable[[str], None]


class Refused(Exception):
    """The request breaks the allowlist policy: ``403``."""


class Unreachable(Exception):
    """The allowed target cannot be resolved or reached: ``502``."""


class BadRequest(Exception):
    """The request head is not a well-formed proxy request: ``400``."""


@dataclass(frozen=True)
class Upstream:
    """An upstream proxy: its address and the ready ``Proxy-Authorization`` value, if any."""

    host: str
    port: int
    authorization: str | None = None

    def __str__(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass(frozen=True)
class Upstreams:
    """The upstream proxy per scheme and the ``no_proxy`` bypass list; all empty means direct."""

    http: Upstream | None = None
    https: Upstream | None = None
    no_proxy: str = ""


@dataclass(frozen=True)
class Route:
    """The opened connection and how to address the request on it."""

    socket: socket.socket
    via_upstream: bool
    authorization: str | None = None


def resolve(host: str, port: int) -> list[str]:
    """The distinct addresses ``host`` resolves to, in answer order."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


def default_address_allowed(address: IPAddress) -> bool:
    """Refuse loopback, link-local (cloud metadata), unspecified and multicast addresses."""
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return not (
        address.is_loopback
        or address.is_link_local
        or address.is_unspecified
        or address.is_multicast
    )


def normalize_host(host: str) -> str:
    """The comparison form of a host name: lower case without one trailing dot."""
    return host.strip().lower().removesuffix(".")


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


class EgressPolicy:
    """Decides and opens the one upstream connection a request may make."""

    def __init__(
        self,
        hosts: Iterable[str],
        *,
        ports: Collection[int] = DEFAULT_PORTS,
        resolver: Resolver = resolve,
        address_allowed: AddressPolicy = default_address_allowed,
        upstreams: Upstreams | None = None,
    ) -> None:
        self.hosts = frozenset(normalize_host(host) for host in hosts if host.strip())
        self.ports = frozenset(ports)
        self._resolver = resolver
        self._address_allowed = address_allowed
        self.upstreams = upstreams or Upstreams()

    def _usable(self, address: str) -> bool:
        try:
            return self._address_allowed(ipaddress.ip_address(address))
        except ValueError:
            return False

    def connect(self, host: str, port: int, *, tunnel: bool) -> Route:
        """Open the connection for ``host:port``, or raise ``Refused`` or ``Unreachable``.

        The target checks always run first; only then is the route chosen: the upstream proxy of
        the scheme unless ``no_proxy`` matches, otherwise a direct connection to a checked address.
        """
        host = normalize_host(host)
        addresses = self._checked_addresses(host, port)
        upstream = self.upstreams.https if tunnel else self.upstreams.http
        if upstream is not None and not (
            self.upstreams.no_proxy
            and proxy_bypass_environment(host, {"no": self.upstreams.no_proxy})
        ):
            return _via_upstream(upstream, host, port, tunnel=tunnel)
        failure: OSError | None = None
        for address in addresses:
            try:
                return Route(
                    socket.create_connection(
                        (address, port), timeout=CONNECT_TIMEOUT_SECONDS
                    ),
                    via_upstream=False,
                )
            except OSError as exc:
                failure = exc
        raise Unreachable(f"cannot connect to {host}:{port}: {failure}")

    def _checked_addresses(self, host: str, port: int) -> list[str]:
        """The resolved addresses of an allowed target; every policy check happens here."""
        if _is_ip_literal(host):
            raise Refused("an IP-literal target is not allowed")
        if host not in self.hosts:
            raise Refused(f"host {host} is not on the allowlist")
        if port not in self.ports:
            raise Refused(f"port {port} is not allowed")
        try:
            addresses = list(self._resolver(host, port))
        except OSError as exc:
            raise Unreachable(f"cannot resolve {host}: {exc}") from exc
        if not addresses:
            raise Unreachable(f"cannot resolve {host}: no address")
        if not all(self._usable(address) for address in addresses):
            raise Refused(f"host {host} resolves to a refused address")
        return addresses


def _via_upstream(upstream: Upstream, host: str, port: int, *, tunnel: bool) -> Route:
    """Connect to the upstream proxy and, for a tunnel, have it open ``host:port``."""
    try:
        connection = socket.create_connection(
            (upstream.host, upstream.port), timeout=CONNECT_TIMEOUT_SECONDS
        )
    except OSError as exc:
        raise Unreachable(
            f"cannot connect to upstream proxy {upstream} for {host}:{port}: {exc}"
        ) from exc
    if not tunnel:
        return Route(
            connection, via_upstream=True, authorization=upstream.authorization
        )
    lines = [f"CONNECT {host}:{port} HTTP/1.1", f"Host: {host}:{port}"]
    if upstream.authorization:
        lines.append(f"Proxy-Authorization: {upstream.authorization}")
    try:
        connection.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1"))
        head, extra = _read_head(connection)
    except (OSError, BadRequest) as exc:
        connection.close()
        raise Unreachable(
            f"upstream proxy {upstream} failed the tunnel to {host}:{port}: {exc}"
        ) from exc
    status = head.split(b"\r\n", 1)[0].decode("latin-1")
    fields = status.split(" ", 2)
    if len(fields) < 2 or not fields[1].startswith("2") or extra:
        connection.close()
        raise Unreachable(
            f"upstream proxy {upstream} answered {status!r} for {host}:{port}"
        )
    return Route(connection, via_upstream=True)


def _stderr_log(message: str) -> None:
    print(f"egress-proxy: {message}", file=sys.stderr, flush=True)


class EgressServer(socketserver.ThreadingTCPServer):
    """One thread per connection; each connection carries exactly one request."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        policy: EgressPolicy,
        log: Log = _stderr_log,
    ) -> None:
        super().__init__(address, _Handler)
        self.policy = policy
        self.log = log


def _read_head(client: socket.socket) -> tuple[bytes, bytes]:
    """The request head and the bytes already read behind it."""
    buffer = b""
    while b"\r\n\r\n" not in buffer:
        if len(buffer) > MAX_HEAD_BYTES:
            raise BadRequest("request head is too large")
        chunk = client.recv(_CHUNK)
        if not chunk:
            raise BadRequest("connection closed inside the request head")
        buffer += chunk
    head, _, rest = buffer.partition(b"\r\n\r\n")
    return head, rest


def _parse_authority(target: str) -> tuple[str, int]:
    """``host:port`` of a CONNECT target; the port is mandatory."""
    host, separator, port = target.rpartition(":")
    if not separator or not host or not port.isdecimal():
        raise BadRequest("CONNECT needs host:port")
    return host.strip("[]"), int(port)


def _rewrite_http(
    target: str, headers: list[tuple[str, str]]
) -> tuple[str, int, str, str, list[str]]:
    """Host, port, origin-form target, authority and forwarded header lines of an absolute URI."""
    parts = urlsplit(target)
    if parts.scheme.lower() != "http" or not parts.hostname:
        raise Refused("only absolute http:// requests and CONNECT are proxied")
    if parts.username is not None or parts.password is not None:
        raise Refused("credentials in the target are not allowed")
    try:
        explicit_port = parts.port
    except ValueError as exc:
        raise BadRequest("invalid port") from exc
    port = explicit_port or 80
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    authority = parts.hostname + (f":{explicit_port}" if explicit_port else "")
    lines = [f"Host: {authority}"]
    lines += [
        f"{name}: {value}"
        for name, value in headers
        if name.lower() not in _HOP_HEADERS and name.lower() != "host"
    ]
    lines.append("Connection: close")
    return parts.hostname, port, path, authority, lines


def _relay(first: socket.socket, second: socket.socket) -> None:
    """Copy bytes both ways until both sides finish or the pair goes idle."""
    peers = {first: second, second: first}
    while peers:
        readable, _, _ = select.select(list(peers), [], [], IDLE_TIMEOUT_SECONDS)
        if not readable:
            return
        for source in readable:
            data = source.recv(_CHUNK)
            if data:
                peers[source].sendall(data)
                continue
            target = peers.pop(source)
            try:
                target.shutdown(socket.SHUT_WR)
            except OSError:
                pass


class _Handler(socketserver.BaseRequestHandler):
    server: EgressServer

    def handle(self) -> None:
        client: socket.socket = self.request
        client.settimeout(IDLE_TIMEOUT_SECONDS)
        try:
            self._serve(client)
        except OSError:
            # A peer that vanished mid-request has nobody left to answer.
            pass

    def _serve(self, client: socket.socket) -> None:
        upstream: socket.socket | None = None
        subject = "-"
        try:
            head, rest = _read_head(client)
            lines = head.decode("latin-1").split("\r\n")
            request = lines[0].split(" ")
            if len(request) != 3 or not request[2].startswith("HTTP/1."):
                raise BadRequest("malformed request line")
            method, target, version = request
            headers = []
            for line in lines[1:]:
                name, separator, value = line.partition(":")
                if not separator or not name or name != name.strip():
                    raise BadRequest("malformed header")
                headers.append((name, value.strip()))
            if method.upper() == "CONNECT":
                host, port = _parse_authority(target)
                subject = f"CONNECT {host}:{port}"
                route = self.server.policy.connect(host, port, tunnel=True)
                upstream = route.socket
                client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                forwarded = rest
            else:
                host, port, path, authority, lines = _rewrite_http(target, headers)
                subject = f"{method.upper()} {host}:{port}"
                route = self.server.policy.connect(host, port, tunnel=False)
                upstream = route.socket
                request_target = (
                    f"http://{authority}{path}" if route.via_upstream else path
                )
                lines.insert(0, f"{method} {request_target} {version}")
                if route.authorization:
                    lines.append(f"Proxy-Authorization: {route.authorization}")
                forwarded = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + rest
            self.server.log(
                f"allow {subject}"
                + (" via upstream proxy" if route.via_upstream else "")
            )
            if forwarded:
                upstream.sendall(forwarded)
            _relay(client, upstream)
        except BadRequest as exc:
            self.server.log(f"bad request: {exc}")
            self._reply(client, 400, "Bad Request")
        except Refused as exc:
            self.server.log(f"deny {subject}: {exc}")
            self._reply(client, 403, "Forbidden")
        except Unreachable as exc:
            self.server.log(f"unreachable {subject}: {exc}")
            self._reply(client, 502, "Bad Gateway")
        finally:
            if upstream is not None:
                upstream.close()

    @staticmethod
    def _reply(client: socket.socket, status: int, reason: str) -> None:
        client.sendall(
            f"HTTP/1.1 {status} {reason}\r\nContent-Length: 0\r\n"
            "Connection: close\r\n\r\n".encode("ascii")
        )


def allowed_hosts_from_env(environ: Mapping[str, str]) -> list[str]:
    """The allowlist the sidecar was started with; an empty one is a launch error."""
    hosts = [
        host.strip()
        for host in environ.get(ALLOWED_HOSTS_ENV, "").split(",")
        if host.strip()
    ]
    if not hosts:
        raise SystemExit(f"{ALLOWED_HOSTS_ENV} lists no host; refusing to start")
    return hosts


_PROXY_VARIABLES = {
    "http": ("http_proxy", "HTTP_PROXY"),
    "https": ("https_proxy", "HTTPS_PROXY"),
}


def _local_upstream(host: str) -> bool:
    if normalize_host(host) == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return address.is_loopback or address.is_unspecified


def _upstream_from_url(name: str, value: str, log: Log) -> Upstream | None:
    """One ``http://[user:password@]host[:port]`` proxy URL; a bare ``host[:port]`` is http."""
    text = value.strip()
    if "://" not in text:
        text = f"http://{text}"
    parts = urlsplit(text)
    if parts.scheme.lower() != "http":
        raise SystemExit(
            f"{name} must name an http:// upstream proxy, not {parts.scheme}://; refusing to start"
        )
    if not parts.hostname:
        raise SystemExit(f"{name} names no upstream proxy host; refusing to start")
    try:
        port = parts.port or 80
    except ValueError as exc:
        raise SystemExit(f"{name} has an invalid port; refusing to start") from exc
    shown = f"{parts.hostname}:{port}"
    if _local_upstream(parts.hostname):
        log(
            f"ignoring {name}: upstream proxy {shown} is a loopback or unspecified address, "
            "unreachable from the container; connecting directly"
        )
        return None
    authorization = None
    if parts.username is not None:
        credentials = f"{unquote(parts.username)}:{unquote(parts.password or '')}"
        authorization = "Basic " + base64.b64encode(credentials.encode()).decode(
            "ascii"
        )
    log(f"upstream proxy from {name}: {shown}")
    return Upstream(parts.hostname, port, authorization)


def upstreams_from_env(environ: Mapping[str, str], log: Log) -> Upstreams:
    """The upstream proxies the runtime passed to the sidecar; none means direct connections."""
    chosen: dict[str, Upstream | None] = {}
    for scheme, names in _PROXY_VARIABLES.items():
        name = next((name for name in names if environ.get(name, "").strip()), None)
        chosen[scheme] = (
            _upstream_from_url(name, environ[name], log) if name is not None else None
        )
    no_proxy = (environ.get("no_proxy") or environ.get("NO_PROXY") or "").strip()
    return Upstreams(http=chosen["http"], https=chosen["https"], no_proxy=no_proxy)


def _stop(signum: int, frame: FrameType | None) -> None:
    raise SystemExit(0)


def main() -> int:
    """Serve on every interface of the container: the internal network reaches it by name."""
    policy = EgressPolicy(
        allowed_hosts_from_env(os.environ),
        upstreams=upstreams_from_env(os.environ, _stderr_log),
    )
    # PID 1 ignores SIGTERM without a handler, which would make ``docker stop`` wait for a kill.
    signal.signal(signal.SIGTERM, _stop)
    with EgressServer(("0.0.0.0", LISTEN_PORT), policy) as server:
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
