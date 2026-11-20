"""Admission rules of the console server over raw request facts; no transport imports.

Headers are an ASGI-style raw list: lower-case names, duplicates kept, in arrival order.
"""

from __future__ import annotations

import secrets
from collections.abc import Collection, Sequence

Headers = Sequence[tuple[bytes, bytes]]

ALLOWED_METHODS = b"GET, HEAD"
UPGRADE_PATH = "/ws"
BOOTSTRAP_PATH = "/"
LEGACY_COOKIE = b"console_token"

# RFC 6265 section 4.1.1: cookie-name is an RFC 2616 token, cookie-value is cookie-octets.
_NAME_OCTETS = frozenset(
    b"!#$%&'*+-.^_`|~0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
)
_VALUE_OCTETS = frozenset(
    [
        0x21,
        *range(0x23, 0x2C),
        *range(0x2D, 0x3B),
        *range(0x3C, 0x5C),
        *range(0x5D, 0x7F),
    ]
)


def _values(headers: Headers, name: bytes) -> list[bytes]:
    return [value for key, value in headers if key == name]


def _loopback(port: int) -> bytes:
    return f"127.0.0.1:{port}".encode()


def request_status(headers: Headers, method: bytes, port: int) -> int | None:
    """403 for a foreign Host or Origin, 405 for a method other than GET or HEAD."""
    expected = _loopback(port)
    origin = _values(headers, b"origin")
    if _values(headers, b"host") != [expected] or origin not in (
        [],
        [b"http://" + expected],
    ):
        return 403
    if method not in (b"GET", b"HEAD"):
        return 405
    return None


def page_status(path: str, query: bytes, pages: Collection[str]) -> int:
    """200 for a known page without a query string, otherwise 404."""
    return 200 if path in pages and not query else 404


def cookie_name(port: int) -> bytes:
    """The port-scoped cookie, so consoles of two projects never overwrite each other."""
    return LEGACY_COOKIE + b"_" + str(port).encode()


def parse_cookies(header: bytes) -> dict[bytes, bytes] | None:
    """The pairs of one Cookie header, or None for a malformed header or a repeated name."""
    cookies: dict[bytes, bytes] = {}
    for pair in header.split(b"; "):
        name, separator, value = pair.partition(b"=")
        if len(value) >= 2 and value[:1] == value[-1:] == b'"':
            value = value[1:-1]
        if (
            not separator
            or not name
            or not _NAME_OCTETS.issuperset(name)
            or not _VALUE_OCTETS.issuperset(value)
            or name in cookies
        ):
            return None
        cookies[name] = value
    return cookies


def authenticated(headers: Headers, port: int, token: str) -> bool:
    """One bearer header, or one cookie header together with the loopback Origin."""
    auth = _values(headers, b"authorization")
    cookies = _values(headers, b"cookie")
    origin = _values(headers, b"origin")
    if len(auth) == 1 and not cookies:
        return secrets.compare_digest(auth[0], b"Bearer " + token.encode())
    if len(cookies) == 1 and not auth and origin == [b"http://" + _loopback(port)]:
        parsed = parse_cookies(cookies[0])
        if parsed is None:
            return False
        value = parsed.get(cookie_name(port), parsed.get(LEGACY_COOKIE))
        return value is not None and secrets.compare_digest(value, token.encode())
    return False


def bootstrap_status(
    headers: Headers, method: bytes, path: str, query: bytes, token: str
) -> int | None:
    """303 when GET / carries exactly the session token as its only query parameter, 401 for a
    wrong token there, None for any other request with a query (the caller answers 404)."""
    name, separator, value = query.partition(b"=")
    if (
        method != b"GET"
        or path != BOOTSTRAP_PATH
        or name != b"token"
        or not separator
        or b"&" in value
        or b";" in value
        or _values(headers, b"authorization")
        or _has_body(headers)
    ):
        return None
    return 303 if secrets.compare_digest(value, token.encode()) else 401


def _has_body(headers: Headers) -> bool:
    for name, value in headers:
        if name == b"transfer-encoding":
            return True
        if name == b"content-length":
            try:
                if int(value) != 0:
                    return True
            except ValueError:
                return True
    return False


def upgrade_status(
    headers: Headers, method: bytes, path: str, query: bytes, port: int, token: str
) -> int | None:
    """Rules after request_status for a WebSocket upgrade: 404, 405, 401, then 400 for a body."""
    if path != UPGRADE_PATH or query:
        return 404
    if method != b"GET":
        return 405
    if not authenticated(headers, port, token):
        return 401
    if _has_body(headers):
        return 400
    return None
