"""Admission rules of the console server over raw request facts; no transport imports.

Headers are an ASGI-style raw list: lower-case names, duplicates kept, in arrival order.
"""

from __future__ import annotations

import secrets
from collections.abc import Collection, Sequence

Headers = Sequence[tuple[bytes, bytes]]

ALLOWED_METHODS = b"GET, HEAD"
UPGRADE_PATH = "/ws"


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


def authenticated(headers: Headers, port: int, token: str) -> bool:
    """One bearer header, or one cookie together with the loopback Origin."""
    auth = _values(headers, b"authorization")
    cookies = _values(headers, b"cookie")
    origin = _values(headers, b"origin")
    if len(auth) == 1 and not cookies:
        return secrets.compare_digest(auth[0], b"Bearer " + token.encode())
    if len(cookies) == 1 and not auth and origin == [b"http://" + _loopback(port)]:
        return secrets.compare_digest(cookies[0], b"console_token=" + token.encode())
    return False


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
