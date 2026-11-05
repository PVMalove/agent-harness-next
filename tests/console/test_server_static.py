"""The console server serves a React build from dist/ over GET and HEAD only."""

from __future__ import annotations

import asyncio
import http.client
import re
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest

from harness.console.backend.server import DEFAULT_STATIC_ROOT, ConsoleServer

INDEX = b"<!doctype html><title>Console</title><script src=/assets/app.js></script>"
ASSET = b"console.log('console');\n"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_bytes(INDEX)
    (root / "assets" / "app.js").write_bytes(ASSET)
    return root


def _request(
    port: int, method: str, path: str, body: bytes | None = None
) -> tuple[int, dict[str, str], bytes]:
    client = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        client.request(method, path, body=body)
        response = client.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        client.close()


async def _raw(port: int, data: bytes) -> bytes:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        writer.write(data)
        await writer.drain()
        return await asyncio.wait_for(reader.read(), 2)
    finally:
        writer.close()
        await writer.wait_closed()


def _serve(
    project: Path, static_root: Path, check: Callable[[int], Awaitable[None]]
) -> None:
    async def scenario() -> None:
        server = ConsoleServer(project, static_root=static_root)
        await server.start()
        try:
            await check(server.port)
        finally:
            await server.close()

    asyncio.run(scenario())


def _assert_static_headers(headers: dict[str, str], port: int) -> None:
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    policy = headers["Content-Security-Policy"]
    assert policy == (
        "default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; "
        f"img-src 'self'; connect-src 'self' ws://127.0.0.1:{port}; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'none'"
    )
    assert not re.search(r"https?:", policy)


@pytest.mark.parametrize(
    "path,content",
    [("/", INDEX), ("/index.html", INDEX), ("/assets/app.js", ASSET)],
)
def test_get_and_head_serve_the_build_with_equal_headers(
    project: Path, dist: Path, path: str, content: bytes
) -> None:
    async def check(port: int) -> None:
        get = await asyncio.to_thread(_request, port, "GET", path)
        head = await asyncio.to_thread(_request, port, "HEAD", path)
        assert get[0] == head[0] == 200
        assert get[2] == content and head[2] == b""
        assert get[1] == head[1]
        _assert_static_headers(get[1], port)

    _serve(project, dist, check)


def test_a_missing_asset_is_404_with_the_strict_policy(
    project: Path, dist: Path
) -> None:
    async def check(port: int) -> None:
        status, headers, body = await asyncio.to_thread(
            _request, port, "GET", "/assets/missing.js"
        )
        assert status == 404 and body == b"Request rejected\n"
        assert headers["Content-Security-Policy"].startswith("default-src 'none';")
        assert "script-src" not in headers["Content-Security-Policy"]

    _serve(project, dist, check)


def test_traversal_and_symlinks_never_leave_the_build(
    project: Path, dist: Path, tmp_path: Path
) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("secret outside dist")
    try:
        (dist / "assets" / "link.txt").symlink_to(secret)
    except OSError:
        if sys.platform == "win32":
            pytest.skip("Windows symlink privilege unavailable")
        raise

    async def check(port: int) -> None:
        host = f"Host: 127.0.0.1:{port}\r\n".encode()
        for target in (
            b"/../secret.txt",
            b"/assets/../../secret.txt",
            b"/%2e%2e/secret.txt",
        ):
            answer = await _raw(
                port, b"GET " + target + b" HTTP/1.1\r\n" + host + b"\r\n"
            )
            assert answer.startswith(b"HTTP/1.1 404 "), target
            assert b"secret outside dist" not in answer
        status, _, body = await asyncio.to_thread(
            _request, port, "GET", "/assets/link.txt"
        )
        assert status == 404 and b"secret" not in body

    _serve(project, dist, check)


def test_other_methods_on_static_paths_get_405(project: Path, dist: Path) -> None:
    async def check(port: int) -> None:
        for path in ("/assets/app.js", "/"):
            status, headers, _ = await asyncio.to_thread(
                _request, port, "POST", path, b"x"
            )
            assert (status, headers["Allow"]) == (405, "GET, HEAD")

    _serve(project, dist, check)


def test_health_and_websocket_routes_keep_priority_over_the_build(
    project: Path, dist: Path
) -> None:
    async def check(port: int) -> None:
        status, headers, body = await asyncio.to_thread(
            _request, port, "GET", "/health/live"
        )
        assert (status, body) == (200, b"Console server\n")
        assert headers["Content-Security-Policy"].startswith("default-src 'none';")
        answer = await _raw(
            port,
            f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
            "Connection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n".encode(),
        )
        assert answer.startswith(b"HTTP/1.1 401 ")

    _serve(project, dist, check)


def test_without_a_build_the_plain_text_page_is_served(
    project: Path, tmp_path: Path
) -> None:
    async def check(port: int) -> None:
        status, headers, body = await asyncio.to_thread(_request, port, "GET", "/")
        assert (status, body) == (200, b"Console server\n")
        assert headers["content-type"].startswith("text/plain")
        assert headers["Content-Security-Policy"].startswith("default-src 'none';")
        missing = await asyncio.to_thread(_request, port, "GET", "/assets/app.js")
        assert missing[0] == 404

    _serve(project, tmp_path / "no-build", check)


def test_the_default_build_lives_in_the_frontend_directory() -> None:
    root = Path(__file__).resolve().parents[2]
    assert DEFAULT_STATIC_ROOT == root / "harness" / "console" / "frontend" / "dist"
