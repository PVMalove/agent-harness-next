#!/usr/bin/env python3
"""The egress proxy sidecar over real sockets, and its delivery as a drift-checked payload (#706).

Upstream servers listen on loopback; the injected resolver maps allowed names to them and the
injected address policy lets the tests reach them, while the default policy is checked on its own.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import threading
import unittest
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from harness.bin import harness as harness_cli
from harness.container import egress_proxy

ALLOWED = "allowed.test"


class Upstream:
    """A loopback TCP server: it records each request head and answers with a fixed body."""

    def __init__(self) -> None:
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port: int = self.server.getsockname()[1]
        self.heads: list[str] = []
        self.connections = 0
        self.tunnel_echo = False
        threading.Thread(target=self._accept, daemon=True).start()

    def close(self) -> None:
        self.server.close()

    def _accept(self) -> None:
        while True:
            try:
                connection, _ = self.server.accept()
            except OSError:
                return
            self.connections += 1
            threading.Thread(
                target=self._serve, args=(connection,), daemon=True
            ).start()

    def _serve(self, connection: socket.socket) -> None:
        with connection:
            if self.tunnel_echo:
                while data := connection.recv(4096):
                    connection.sendall(b"echo:" + data)
                return
            buffer = b""
            while b"\r\n\r\n" not in buffer:
                chunk = connection.recv(4096)
                if not chunk:
                    return
                buffer += chunk
            self.heads.append(buffer.partition(b"\r\n\r\n")[0].decode("latin-1"))
            connection.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\nConnection: close\r\n\r\nhello"
            )


class ProxyFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.upstream = Upstream()
        self.addCleanup(self.upstream.close)
        self.resolved: list[tuple[str, int]] = []
        self.logs: list[str] = []
        self.answers = {ALLOWED: ["127.0.0.1"]}
        self.proxy_port = self.start(
            egress_proxy.EgressPolicy(
                [ALLOWED, "127.0.0.1"],
                ports={self.upstream.port},
                resolver=self.resolver,
                address_allowed=lambda address: True,
            )
        )

    def resolver(self, host: str, port: int) -> list[str]:
        self.resolved.append((host, port))
        if host not in self.answers:
            raise socket.gaierror(socket.EAI_NONAME, "unknown host")
        return self.answers[host]

    def start(self, policy: egress_proxy.EgressPolicy) -> int:
        server = egress_proxy.EgressServer(("127.0.0.1", 0), policy, self.logs.append)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return int(server.server_address[1])

    @contextmanager
    def client(self, port: int | None = None) -> Iterator[socket.socket]:
        with socket.create_connection(
            ("127.0.0.1", port or self.proxy_port), timeout=5
        ) as connection:
            yield connection

    def exchange(self, request: str, port: int | None = None) -> bytes:
        """Send one request and read until the proxy or the upstream closes."""
        with self.client(port) as connection:
            connection.sendall(request.encode("latin-1"))
            received = b""
            while chunk := connection.recv(4096):
                received += chunk
            return received

    def status(self, request: str) -> str:
        return self.exchange(request).split(b"\r\n", 1)[0].decode("latin-1")


class ForwardingTests(ProxyFixture):
    def test_an_allowed_http_request_reaches_the_upstream_in_origin_form(self) -> None:
        port = self.upstream.port

        response = self.exchange(
            f"GET http://{ALLOWED}:{port}/path?q=1 HTTP/1.1\r\n"
            f"Host: {ALLOWED}:{port}\r\nProxy-Connection: keep-alive\r\n"
            "Proxy-Authorization: Basic c2VjcmV0\r\nAccept: */*\r\n\r\n"
        )

        self.assertTrue(response.startswith(b"HTTP/1.1 200 OK"), response)
        self.assertTrue(response.endswith(b"hello"), response)
        [head] = self.upstream.heads
        lines = head.split("\r\n")
        self.assertEqual(lines[0], "GET /path?q=1 HTTP/1.1")
        self.assertIn(f"Host: {ALLOWED}:{port}", lines)
        self.assertIn("Accept: */*", lines)
        self.assertIn("Connection: close", lines)
        self.assertFalse(
            [line for line in lines if line.lower().startswith("proxy-")], lines
        )

    def test_the_request_host_header_cannot_name_another_virtual_host(self) -> None:
        port = self.upstream.port

        self.exchange(
            f"GET http://{ALLOWED}:{port}/ HTTP/1.1\r\nHost: other.test\r\n\r\n"
        )

        self.assertEqual(
            [
                line
                for line in self.upstream.heads[0].split("\r\n")
                if line[:5] == "Host:"
            ],
            [f"Host: {ALLOWED}:{port}"],
        )

    def test_a_request_body_is_forwarded_with_the_head(self) -> None:
        port = self.upstream.port
        seen: list[bytes] = []
        original = self.upstream._serve

        def capture(connection: socket.socket) -> None:
            peeked = connection.recv(4096, socket.MSG_PEEK)
            seen.append(peeked)
            original(connection)

        self.upstream._serve = capture  # type: ignore[method-assign]

        self.exchange(
            f"POST http://{ALLOWED}:{port}/submit HTTP/1.1\r\nContent-Length: 4\r\n\r\nbody"
        )

        self.assertTrue(any(chunk.endswith(b"\r\n\r\nbody") for chunk in seen), seen)

    def test_an_allowed_connect_tunnels_bytes_both_ways(self) -> None:
        self.upstream.tunnel_echo = True
        port = self.upstream.port

        with self.client() as connection:
            connection.sendall(
                f"CONNECT {ALLOWED}:{port} HTTP/1.1\r\nHost: {ALLOWED}:{port}\r\n\r\n".encode()
            )
            established = connection.recv(4096)
            connection.sendall(b"ping")
            answer = connection.recv(4096)

        self.assertTrue(established.startswith(b"HTTP/1.1 200"), established)
        self.assertEqual(answer, b"echo:ping")

    def test_the_host_is_matched_exactly_but_without_case_or_a_trailing_dot(
        self,
    ) -> None:
        port = self.upstream.port
        self.answers["allowed.test"] = ["127.0.0.1"]

        allowed = self.status(f"GET http://ALLOWED.test.:{port}/ HTTP/1.1\r\n\r\n")
        sub = self.status(f"GET http://sub.{ALLOWED}:{port}/ HTTP/1.1\r\n\r\n")
        parent = self.status(f"GET http://test:{port}/ HTTP/1.1\r\n\r\n")
        suffixed = self.status(
            f"GET http://{ALLOWED}.evil.test:{port}/ HTTP/1.1\r\n\r\n"
        )

        self.assertEqual(allowed, "HTTP/1.1 200 OK")
        self.assertEqual({sub, parent, suffixed}, {"HTTP/1.1 403 Forbidden"})


class RefusalTests(ProxyFixture):
    def test_a_host_outside_the_allowlist_is_forbidden_without_resolving_it(
        self,
    ) -> None:
        port = self.upstream.port

        get = self.status(f"GET http://denied.test:{port}/ HTTP/1.1\r\n\r\n")
        connect = self.status(f"CONNECT denied.test:{port} HTTP/1.1\r\n\r\n")

        self.assertEqual((get, connect), ("HTTP/1.1 403 Forbidden",) * 2)
        self.assertEqual(self.resolved, [])
        self.assertEqual(self.upstream.connections, 0)
        self.assertTrue(
            any("deny" in line and "denied.test" in line for line in self.logs)
        )

    def test_an_ip_literal_is_forbidden_even_when_the_allowlist_names_it(self) -> None:
        port = self.upstream.port

        statuses = {
            self.status(f"GET http://127.0.0.1:{port}/ HTTP/1.1\r\n\r\n"),
            self.status(f"CONNECT 127.0.0.1:{port} HTTP/1.1\r\n\r\n"),
            self.status(f"CONNECT [::1]:{port} HTTP/1.1\r\n\r\n"),
            self.status(f"GET http://[::1]:{port}/ HTTP/1.1\r\n\r\n"),
        }

        self.assertEqual(statuses, {"HTTP/1.1 403 Forbidden"})
        self.assertEqual(self.resolved, [])
        self.assertEqual(self.upstream.connections, 0)

    def test_only_ports_80_and_443_are_allowed_by_default(self) -> None:
        self.assertEqual(egress_proxy.DEFAULT_PORTS, frozenset({80, 443}))
        defaults = self.start(
            egress_proxy.EgressPolicy(
                [ALLOWED],
                resolver=self.resolver,
                address_allowed=lambda address: True,
            )
        )

        statuses = {
            self.exchange(request, defaults).split(b"\r\n", 1)[0]
            for request in (
                f"CONNECT {ALLOWED}:22 HTTP/1.1\r\n\r\n",
                f"CONNECT {ALLOWED}:8080 HTTP/1.1\r\n\r\n",
                f"GET http://{ALLOWED}:{self.upstream.port}/ HTTP/1.1\r\n\r\n",
            )
        }

        self.assertEqual(statuses, {b"HTTP/1.1 403 Forbidden"})
        self.assertEqual(self.resolved, [])

    def test_unsupported_request_shapes_are_forbidden(self) -> None:
        port = self.upstream.port
        statuses = {
            self.status("GET / HTTP/1.1\r\nHost: allowed.test\r\n\r\n"),
            self.status(f"GET https://{ALLOWED}:{port}/ HTTP/1.1\r\n\r\n"),
            self.status(f"GET ftp://{ALLOWED}:{port}/ HTTP/1.1\r\n\r\n"),
            self.status(f"GET http://user:pw@{ALLOWED}:{port}/ HTTP/1.1\r\n\r\n"),
        }

        self.assertEqual(statuses, {"HTTP/1.1 403 Forbidden"})
        self.assertEqual(self.upstream.connections, 0)

    def test_a_malformed_head_is_a_bad_request(self) -> None:
        self.assertEqual(self.status("NONSENSE\r\n\r\n"), "HTTP/1.1 400 Bad Request")
        self.assertEqual(
            self.status(f"CONNECT {ALLOWED} HTTP/1.1\r\n\r\n"),
            "HTTP/1.1 400 Bad Request",
        )
        self.assertEqual(
            self.status(f"GET http://{ALLOWED}:99999/ HTTP/1.1\r\n\r\n"),
            "HTTP/1.1 400 Bad Request",
        )

    def test_an_allowed_host_that_does_not_resolve_or_connect_is_a_bad_gateway(
        self,
    ) -> None:
        port = self.upstream.port
        self.answers["gone.test"] = []
        free = socket.create_server(("127.0.0.1", 0))
        closed_port: int = free.getsockname()[1]
        free.close()
        refused = self.start(
            egress_proxy.EgressPolicy(
                [ALLOWED, "gone.test", "unknown.test"],
                ports={closed_port, port},
                resolver=self.resolver,
                address_allowed=lambda address: True,
            )
        )

        statuses = {
            self.exchange(f"CONNECT unknown.test:{port} HTTP/1.1\r\n\r\n", refused)[
                :12
            ],
            self.exchange(f"CONNECT gone.test:{port} HTTP/1.1\r\n\r\n", refused)[:12],
            self.exchange(f"CONNECT {ALLOWED}:{closed_port} HTTP/1.1\r\n\r\n", refused)[
                :12
            ],
        }

        self.assertEqual(statuses, {b"HTTP/1.1 502"})


class AddressPolicyTests(ProxyFixture):
    def test_the_default_policy_refuses_local_and_metadata_addresses(self) -> None:
        cases: dict[str, bool] = {
            "127.0.0.1": False,
            "127.8.9.10": False,
            "169.254.169.254": False,
            "0.0.0.0": False,
            "224.0.0.1": False,
            "::1": False,
            "fe80::1": False,
            "::": False,
            "ff02::1": False,
            "::ffff:127.0.0.1": False,
            "::ffff:169.254.169.254": False,
            "93.184.216.34": True,
            "10.1.2.3": True,
            "2606:2800:220:1:248:1893:25c8:1946": True,
        }
        for text, expected in cases.items():
            with self.subTest(address=text):
                self.assertIs(
                    egress_proxy.default_address_allowed(ipaddress.ip_address(text)),
                    expected,
                )

    def test_a_default_policy_host_resolving_to_a_refused_address_is_never_connected(
        self,
    ) -> None:
        port = self.upstream.port
        strict = self.start(
            egress_proxy.EgressPolicy(
                ["loop.test", "meta.test", "mixed.test"],
                ports={port},
                resolver=self.resolver,
            )
        )
        self.answers.update(
            {
                "loop.test": ["127.0.0.1"],
                "meta.test": ["169.254.169.254"],
                "mixed.test": ["93.184.216.34", "127.0.0.1"],
            }
        )

        statuses = {
            self.exchange(f"CONNECT {host}:{port} HTTP/1.1\r\n\r\n", strict)[:12]
            for host in ("loop.test", "meta.test", "mixed.test")
        }

        self.assertEqual(statuses, {b"HTTP/1.1 403"})
        self.assertEqual(self.upstream.connections, 0)

    def test_the_host_is_resolved_once_per_request_and_the_checked_address_is_used(
        self,
    ) -> None:
        port = self.upstream.port
        answers: Iterator[list[str]] = iter([["127.0.0.1"], ["169.254.169.254"]])
        calls: list[str] = []

        def flipping(host: str, _: int) -> list[str]:
            calls.append(host)
            return next(answers)

        rebinding = self.start(
            egress_proxy.EgressPolicy(
                [ALLOWED],
                ports={port},
                resolver=flipping,
                address_allowed=lambda address: True,
            )
        )

        status = self.exchange(
            f"GET http://{ALLOWED}:{port}/ HTTP/1.1\r\n\r\n", rebinding
        ).split(b"\r\n", 1)[0]

        self.assertEqual(status, b"HTTP/1.1 200 OK")
        self.assertEqual(calls, [ALLOWED])


class FakeUpstreamProxy:
    """A loopback upstream proxy: it records each head, accepts CONNECT and echoes the tunnel."""

    def __init__(self) -> None:
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port: int = self.server.getsockname()[1]
        self.heads: list[str] = []
        self.connections = 0
        self.connect_reply = b"HTTP/1.1 200 Connection established\r\n\r\n"
        threading.Thread(target=self._accept, daemon=True).start()

    def close(self) -> None:
        self.server.close()

    def _accept(self) -> None:
        while True:
            try:
                connection, _ = self.server.accept()
            except OSError:
                return
            self.connections += 1
            threading.Thread(
                target=self._serve, args=(connection,), daemon=True
            ).start()

    def _serve(self, connection: socket.socket) -> None:
        with connection:
            buffer = b""
            while b"\r\n\r\n" not in buffer:
                chunk = connection.recv(4096)
                if not chunk:
                    return
                buffer += chunk
            head = buffer.partition(b"\r\n\r\n")[0].decode("latin-1")
            self.heads.append(head)
            if not head.startswith("CONNECT "):
                connection.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Length: 7\r\nConnection: close\r\n\r\nproxied"
                )
                return
            connection.sendall(self.connect_reply)
            if not self.connect_reply.startswith(b"HTTP/1.1 200"):
                return
            while data := connection.recv(4096):
                connection.sendall(b"echo:" + data)


class UpstreamProxyTests(ProxyFixture):
    """The sidecar chains allowed requests through the operator's upstream proxy (#1201)."""

    def setUp(self) -> None:
        super().setUp()
        self.proxy = FakeUpstreamProxy()
        self.addCleanup(self.proxy.close)
        self.answers["public.test"] = ["93.184.216.34"]
        self.answers["loop.test"] = ["127.0.0.1"]

    def chained(self, upstreams: egress_proxy.Upstreams) -> int:
        return self.start(
            egress_proxy.EgressPolicy(
                ["public.test", "loop.test"],
                resolver=self.resolver,
                upstreams=upstreams,
            )
        )

    def via_proxy(self, authorization: str | None = None) -> egress_proxy.Upstream:
        return egress_proxy.Upstream("127.0.0.1", self.proxy.port, authorization)

    def test_an_allowed_connect_is_chained_through_the_upstream_proxy(self) -> None:
        port = self.chained(egress_proxy.Upstreams(https=self.via_proxy("Basic dTpw")))

        with self.client(port) as connection:
            connection.sendall(
                b"CONNECT public.test:443 HTTP/1.1\r\nHost: public.test:443\r\n\r\n"
            )
            established = connection.recv(4096)
            connection.sendall(b"ping")
            answer = connection.recv(4096)

        self.assertTrue(established.startswith(b"HTTP/1.1 200"), established)
        self.assertEqual(answer, b"echo:ping")
        self.assertEqual(
            self.proxy.heads,
            [
                "CONNECT public.test:443 HTTP/1.1\r\nHost: public.test:443\r\n"
                "Proxy-Authorization: Basic dTpw"
            ],
        )
        self.assertEqual(self.resolved, [("public.test", 443)])

    def test_an_allowed_http_request_goes_to_the_upstream_proxy_in_absolute_form(
        self,
    ) -> None:
        port = self.chained(egress_proxy.Upstreams(http=self.via_proxy("Basic dTpw")))

        response = self.exchange(
            "GET http://public.test/path?q=1 HTTP/1.1\r\nHost: public.test\r\n"
            "Proxy-Authorization: Basic c2VjcmV0\r\nAccept: */*\r\n\r\n",
            port,
        )

        self.assertTrue(response.endswith(b"proxied"), response)
        [head] = self.proxy.heads
        lines = head.split("\r\n")
        self.assertEqual(lines[0], "GET http://public.test/path?q=1 HTTP/1.1")
        self.assertIn("Host: public.test", lines)
        self.assertIn("Accept: */*", lines)
        self.assertIn("Proxy-Authorization: Basic dTpw", lines)
        self.assertNotIn("c2VjcmV0", head)

    def test_without_an_upstream_for_the_scheme_or_under_no_proxy_it_connects_directly(
        self,
    ) -> None:
        origin = self.upstream.port
        cases = {
            "no upstream": egress_proxy.Upstreams(),
            "https only": egress_proxy.Upstreams(https=self.via_proxy()),
            "no_proxy": egress_proxy.Upstreams(
                http=self.via_proxy(), no_proxy="example.org, .ALLOWED.test"
            ),
        }
        for name, upstreams in cases.items():
            with self.subTest(case=name):
                port = self.start(
                    egress_proxy.EgressPolicy(
                        [ALLOWED],
                        ports={origin},
                        resolver=self.resolver,
                        address_allowed=lambda address: True,
                        upstreams=upstreams,
                    )
                )

                response = self.exchange(
                    f"GET http://{ALLOWED}:{origin}/x HTTP/1.1\r\n\r\n", port
                )

                self.assertTrue(response.endswith(b"hello"), response)
                self.assertEqual(
                    self.upstream.heads[-1].split("\r\n")[0], "GET /x HTTP/1.1"
                )
        self.assertEqual(self.proxy.connections, 0)

    def test_refused_targets_never_reach_the_upstream_proxy(self) -> None:
        both = self.via_proxy()
        port = self.chained(egress_proxy.Upstreams(http=both, https=both))

        statuses = {
            self.exchange(request, port).split(b"\r\n", 1)[0]
            for request in (
                "CONNECT denied.test:443 HTTP/1.1\r\n\r\n",
                "GET http://denied.test/ HTTP/1.1\r\n\r\n",
                f"CONNECT 127.0.0.1:{self.proxy.port} HTTP/1.1\r\n\r\n",
                f"GET http://127.0.0.1:{self.proxy.port}/ HTTP/1.1\r\n\r\n",
                "CONNECT public.test:22 HTTP/1.1\r\n\r\n",
                "CONNECT loop.test:443 HTTP/1.1\r\n\r\n",
                "GET http://loop.test/ HTTP/1.1\r\n\r\n",
            )
        }

        self.assertEqual(statuses, {b"HTTP/1.1 403 Forbidden"})
        self.assertEqual(self.proxy.connections, 0)

    def test_a_failing_or_refusing_upstream_proxy_is_a_bad_gateway(self) -> None:
        free = socket.create_server(("127.0.0.1", 0))
        closed_port: int = free.getsockname()[1]
        free.close()
        self.proxy.connect_reply = b"HTTP/1.1 407 Proxy Authentication Required\r\n\r\n"
        refusing = self.chained(egress_proxy.Upstreams(https=self.via_proxy()))
        gone = self.chained(
            egress_proxy.Upstreams(
                https=egress_proxy.Upstream("127.0.0.1", closed_port, None),
                http=egress_proxy.Upstream("127.0.0.1", closed_port, None),
            )
        )

        statuses = {
            self.exchange("CONNECT public.test:443 HTTP/1.1\r\n\r\n", refusing)[:12],
            self.exchange("CONNECT public.test:443 HTTP/1.1\r\n\r\n", gone)[:12],
            self.exchange("GET http://public.test/ HTTP/1.1\r\n\r\n", gone)[:12],
        }

        self.assertEqual(statuses, {b"HTTP/1.1 502"})
        self.assertTrue(
            any("unreachable" in line and "407" in line for line in self.logs),
            self.logs,
        )


class UpstreamsFromEnvTests(unittest.TestCase):
    def parse(
        self, environ: dict[str, str]
    ) -> tuple[egress_proxy.Upstreams, list[str]]:
        logs: list[str] = []
        return egress_proxy.upstreams_from_env(environ, logs.append), logs

    def test_no_proxy_variables_mean_direct_connections(self) -> None:
        upstreams, _ = self.parse({})

        self.assertEqual(upstreams, egress_proxy.Upstreams())

    def test_lower_case_wins_and_no_proxy_is_kept(self) -> None:
        upstreams, logs = self.parse(
            {
                "https_proxy": "http://user:p%40ss@proxy.corp:3128/",
                "HTTPS_PROXY": "http://other.corp:9999",
                "HTTP_PROXY": "proxy.corp",
                "NO_PROXY": "localhost,.corp",
            }
        )

        self.assertEqual(
            upstreams,
            egress_proxy.Upstreams(
                http=egress_proxy.Upstream("proxy.corp", 80, None),
                https=egress_proxy.Upstream("proxy.corp", 3128, "Basic dXNlcjpwQHNz"),
                no_proxy="localhost,.corp",
            ),
        )
        self.assertFalse([line for line in logs if "p%40ss" in line or "p@ss" in line])

    def test_a_loopback_or_unspecified_upstream_is_ignored_with_a_log_line(
        self,
    ) -> None:
        for value in (
            "http://127.0.0.1:3128",
            "http://localhost:3128",
            "http://[::1]:3128",
            "http://0.0.0.0:3128",
        ):
            with self.subTest(value=value):
                upstreams, logs = self.parse({"HTTPS_PROXY": value})

                self.assertIsNone(upstreams.https)
                self.assertTrue(any("HTTPS_PROXY" in line for line in logs), logs)

    def test_an_unsupported_proxy_url_refuses_to_start(self) -> None:
        for value in (
            "https://proxy.corp:443",
            "socks5://proxy.corp:1080",
            "http://:8080",
        ):
            with (
                self.subTest(value=value),
                self.assertRaises(SystemExit) as refused,
            ):
                self.parse({"HTTP_PROXY": value})
            self.assertIn("HTTP_PROXY", str(refused.exception))


class StartupTests(unittest.TestCase):
    def test_the_allowlist_comes_from_the_environment(self) -> None:
        hosts = egress_proxy.allowed_hosts_from_env(
            {egress_proxy.ALLOWED_HOSTS_ENV: " api.example.com, files.example.com ,,"}
        )

        self.assertEqual(hosts, ["api.example.com", "files.example.com"])

    def test_an_empty_or_missing_allowlist_refuses_to_start(self) -> None:
        for environ in ({}, {egress_proxy.ALLOWED_HOSTS_ENV: " , "}):
            with (
                self.subTest(environ=environ),
                self.assertRaises(SystemExit) as refused,
            ):
                egress_proxy.allowed_hosts_from_env(environ)
            self.assertIn(egress_proxy.ALLOWED_HOSTS_ENV, str(refused.exception))


class PayloadDeliveryTests(unittest.TestCase):
    """The proxy is a target payload of backend-orchestration with drift control (#706)."""

    def test_the_proxy_code_and_dockerfile_land_in_the_target_container_directory(
        self,
    ) -> None:
        payload = harness_cli.package_files(["backend-orchestration"])
        container = harness_cli.PACKAGE / "container"

        for name in ("egress_proxy.py", "Dockerfile.proxy", "Dockerfile.sandbox"):
            with self.subTest(name=name):
                self.assertEqual(
                    payload[f".harness/container/{name}"],
                    (container / name).read_bytes(),
                )
        self.assertTrue(
            all(path.startswith(".harness/") for path in payload), "outside .harness/"
        )

    def test_the_sandbox_base_image_is_a_plain_pinned_from_base(self) -> None:
        """Dockerfile.sandbox only installs tools: the executor owns entrypoint, user and home (#710)."""
        dockerfile = (
            harness_cli.PACKAGE / "container" / "Dockerfile.sandbox"
        ).read_text(encoding="utf-8")
        instructions = [
            line.split(maxsplit=1)
            for line in dockerfile.splitlines()
            if line.strip() and not line.startswith(("#", " ", "\t"))
        ]
        keywords = [parts[0].upper() for parts in instructions]
        base = next(parts[1] for parts in instructions if parts[0].upper() == "FROM")

        self.assertRegex(base, r"^debian:[a-z]+-\d{8}-slim$")
        self.assertFalse(
            {"ENTRYPOINT", "CMD", "USER", "VOLUME", "ARG", "ENV"} & set(keywords)
        )
        self.assertRegex(dockerfile, r"ghcr\.io/astral-sh/uv:\d+\.\d+\.\d+ ")
        for tool in ("git", "curl", "jq", "ca-certificates", "python3", "nodejs"):
            with self.subTest(tool=tool):
                self.assertRegex(dockerfile, rf"\s{re.escape(tool)}\s")
        for build in ("docker build", "podman build"):
            with self.subTest(build=build):
                self.assertIn(
                    f"#   {build} -f .harness/container/Dockerfile.sandbox", dockerfile
                )

    def test_a_project_without_orchestration_does_not_receive_the_proxy(self) -> None:
        payload = harness_cli.package_files(["engineering-suite"])

        self.assertFalse([path for path in payload if "/container/" in path])

    def test_root_docs_are_not_a_source_of_the_container_payload(self) -> None:
        root_docs = (harness_cli.ROOT / "docs").resolve()
        sources = harness_cli.selected_resources(["backend-orchestration"])

        container = [s for s in sources if s.name == "container"]

        self.assertEqual(len(container), 1)
        self.assertFalse(any(s.resolve().is_relative_to(root_docs) for s in sources))
        self.assertFalse(
            [
                path
                for path in harness_cli.package_files(["backend-orchestration"])
                if path.startswith(".harness/container/") and "docs" in path
            ]
        )


Check = Callable[[], None]

if __name__ == "__main__":
    unittest.main()
