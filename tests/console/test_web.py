"""The browser enters the console through the launch URL: the token query is traded for a
port-scoped HttpOnly cookie, and that cookie opens the WebSocket that serves Home."""

from __future__ import annotations

import asyncio
from http.client import HTTPConnection
import json
from pathlib import Path
import subprocess

import pytest

from harness.console.backend import composition
from harness.console.backend.server import ConsoleServer
from tests.console.test_server import GatedCollect


@pytest.fixture(autouse=True)
def isolated_language_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARNESS_CONSOLE_LANG", raising=False)


def _server(project: Path) -> ConsoleServer:
    return ConsoleServer(
        project,
        snapshots=composition.snapshot_service(
            project, collect=GatedCollect(open_gate=True)
        ),
    )


async def http(
    server: ConsoleServer,
    path: str = "/",
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    def request() -> tuple[int, dict[str, str], bytes]:
        client = HTTPConnection("127.0.0.1", server.port, timeout=3)
        try:
            client.request(method, path, headers=headers or {})
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            client.close()

    return await asyncio.to_thread(request)


async def home_over_cookie(server: ConsoleServer, cookie: str) -> dict[str, object]:
    from websockets.asyncio.client import connect
    from websockets.typing import Origin

    async with connect(
        f"ws://127.0.0.1:{server.port}/ws",
        proxy=None,
        origin=Origin(f"http://127.0.0.1:{server.port}"),
        additional_headers={"Cookie": cookie},
        open_timeout=2,
        close_timeout=1,
    ) as client:
        await client.send(json.dumps({"id": "home", "type": "home.snapshot"}))
        reply: dict[str, object] = json.loads(await asyncio.wait_for(client.recv(), 5))
        return reply


def test_the_launch_url_sets_the_cookie_that_opens_home_on_the_websocket(
    project: Path,
) -> None:
    async def scenario() -> None:
        server = _server(project)
        await server.start()
        try:
            status, headers, body = await http(server, "/?token=" + server.token)
            assert (status, body) == (303, b"")
            assert headers["Location"] == "/#/?lang=ru"
            assert headers["Set-Cookie"] == (
                f"console_token_{server.port}={server.token}; HttpOnly; SameSite=Strict; Path=/"
            )
            assert headers["Referrer-Policy"] == "no-referrer"
            assert headers["Cache-Control"] == "no-store"
            assert headers["X-Frame-Options"] == "DENY"
            assert server.token not in headers["Location"]

            cookie = headers["Set-Cookie"].split(";", 1)[0]
            reply = await home_over_cookie(server, "theme=dark; " + cookie)
            assert (reply["id"], reply["ok"]) == ("home", True)
            snapshot = reply["snapshot"]
            assert isinstance(snapshot, dict) and snapshot["version"] == 1

            # Redemption is stateless: the same launch URL works again.
            assert (await http(server, "/?token=" + server.token))[0] == 303
        finally:
            await server.close()

    asyncio.run(scenario())


def test_the_redirect_lands_on_the_configured_language(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HARNESS_CONSOLE_LANG", "en")

    async def scenario() -> None:
        server = _server(project)
        await server.start()
        try:
            status, headers, _ = await http(server, "/?token=" + server.token)
            assert (status, headers["Location"]) == (303, "/#/?lang=en")
        finally:
            await server.close()

    asyncio.run(scenario())


def test_a_wrong_token_or_another_request_shape_never_sets_a_cookie(
    project: Path,
) -> None:
    async def scenario() -> None:
        server = _server(project)
        await server.start()
        token = server.token
        try:
            cases = [
                ("GET", "/?token=wrong", {}, 401),
                ("HEAD", "/?token=" + token, {}, 404),
                ("GET", f"/?token={token}&lang=en", {}, 404),
                ("GET", f"/?token={token}&token={token}", {}, 404),
                ("GET", "/health/live?token=" + token, {}, 404),
                ("GET", "/?token=" + token, {"Authorization": "Bearer " + token}, 404),
            ]
            for method, target, headers, expected in cases:
                status, answer, body = await http(
                    server, target, method=method, headers=headers
                )
                assert status == expected, target
                assert "Set-Cookie" not in answer
                assert token.encode() not in body
                assert all(token not in value for value in answer.values())
        finally:
            await server.close()

    asyncio.run(scenario())


def test_a_duplicate_or_foreign_port_cookie_is_refused_on_the_websocket(
    project: Path, tmp_path: Path
) -> None:
    from websockets.exceptions import InvalidStatus

    other_project = tmp_path / "other"
    other_project.mkdir()
    subprocess.run(["git", "init", "-q", str(other_project)], check=True)

    async def scenario() -> None:
        first, second = _server(project), _server(other_project)
        await first.start()
        await second.start()
        try:
            both = (
                f"console_token_{first.port}={first.token}; "
                f"console_token_{second.port}={second.token}"
            )
            for server in (first, second):
                reply = await home_over_cookie(server, both)
                assert reply["ok"] is True

            own = f"console_token_{first.port}={first.token}"
            for cookie in (
                own + "; " + own,
                f"console_token_{first.port}={second.token}",
                f"console_token_{second.port}={second.token}",
            ):
                with pytest.raises(InvalidStatus) as rejected:
                    await home_over_cookie(first, cookie)
                assert rejected.value.response.status_code == 401
        finally:
            await first.close()
            await second.close()

    asyncio.run(scenario())
