"""Browser Home contracts through the real loopback HTTP and WebSocket listener."""

from __future__ import annotations

import asyncio
from http.client import HTTPConnection
import json
from pathlib import Path

import pytest

from harness.console.discovery import discovery_path
from harness.console.server import ConsoleServer


@pytest.fixture(autouse=True)
def isolated_language_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HARNESS_CONSOLE_LANG", raising=False)


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


def token_for(project: Path) -> str:
    return str(json.loads(discovery_path(project).read_text())["token"])


def test_bootstrap_redirects_to_authenticated_escaped_home(project: Path) -> None:
    project = project.rename(project.with_name("project & credential"))

    async def scenario() -> None:
        server = ConsoleServer(project)
        await server.start()
        try:
            assert (await http(server))[0] == 401
            token = token_for(project)
            status, headers, body = await http(server, "/?token=" + token)
            assert status == 303
            assert headers["Location"] == "/?lang=ru"
            cookie = headers["Set-Cookie"]
            assert cookie == f"console_token_{server.port}={token}; HttpOnly; SameSite=Strict; Path=/"
            assert token.encode() not in body
            assert headers["Referrer-Policy"] == "no-referrer"

            status, headers, body = await http(
                server, "/?lang=ru", headers={"Cookie": cookie.split(";", 1)[0]}
            )
            assert status == 200
            assert headers["Content-Type"] == "text/html; charset=utf-8"
            page = body.decode()
            assert '<html lang="ru">' in page
            assert "project &amp; credential" in page
            assert "project & credential" not in page
            assert token not in page
            assert page.count("data-nav-route=") == 13
            for block in (
                "home",
                "home-attention",
                "home-context",
                "home-tasks",
                "home-health",
                "home-areas",
                "home-checks",
                "home-contour",
            ):
                assert f'id="{block}"' in page
            assert page.index('id="home-context"') < page.index('id="home-tasks"')
            assert 'src="/static/home.js"' in page
        finally:
            await server.close()

    asyncio.run(scenario())


def test_head_never_redeems_and_browser_issuance_preserves_native_bearer(
    project: Path,
) -> None:
    from websockets.asyncio.client import connect
    from websockets.typing import Origin

    async def scenario() -> None:
        server = ConsoleServer(project)
        await server.start()
        token = token_for(project)
        bootstrap = "/?token=" + token
        try:
            status, headers, body = await http(server, bootstrap, method="HEAD")
            assert status == 401 and "Set-Cookie" not in headers and not body

            first = await http(server, bootstrap)
            assert first[0] == 303
            cookie = first[1]["Set-Cookie"].split(";", 1)[0]
            assert (await http(server, bootstrap))[0] == 401
            repeated = await http(server, bootstrap, headers={"Cookie": cookie})
            assert repeated[0] == 303 and "Set-Cookie" not in repeated[1]
            assert repeated[1]["Location"] == "/?lang=ru"
            for credentials, origin in (
                ({"Authorization": "Bearer " + token}, None),
                ({"Cookie": cookie}, Origin(f"http://127.0.0.1:{server.port}")),
            ):
                async with connect(
                    f"ws://127.0.0.1:{server.port}/ws",
                    proxy=None,
                    origin=origin,
                    additional_headers=credentials,
                    open_timeout=2,
                    close_timeout=1,
                ) as client:
                    await asyncio.wait_for(await client.ping(b"still-authorized"), 2)
                    await client.send(json.dumps({"id": "native-and-cookie", "type": "home.snapshot"}))
                    reply = json.loads(await asyncio.wait_for(client.recv(), 3))
                    assert reply["id"] == "native-and-cookie" and reply["ok"] is True
        finally:
            await server.close()

    asyncio.run(scenario())


def test_browser_home_uses_real_snapshot_cache_force_and_explicit_online(
    project: Path,
) -> None:
    from websockets.asyncio.client import connect
    from websockets.typing import Origin

    from harness.console.snapshots import (
        HealthCounters,
        HomeSnapshot,
        MemoryCard,
        RepoMapCard,
        SnapshotService,
    )

    def offline(repo: Path) -> HomeSnapshot:
        return HomeSnapshot(
            1,
            HealthCounters(0, 0, 0, 0),
            (),
            0,
            "test-build",
            "unknown",
            None,
            RepoMapCard(None, "no HEAD map", None),
            MemoryCard(None, None),
        )

    def online(repo: Path) -> HomeSnapshot:
        return HomeSnapshot(
            1,
            HealthCounters(1, 0, 0, 2),
            (),
            0,
            "online-build",
            "unknown",
            3,
            RepoMapCard("full", "no HEAD map", None),
            MemoryCard(None, None),
        )

    async def scenario() -> None:
        server = ConsoleServer(
            project,
            snapshots=SnapshotService(project, collect=offline, collect_online=online),
        )
        await server.start()
        try:
            issued = await http(server, "/?token=" + token_for(project))
            cookie = issued[1]["Set-Cookie"].split(";", 1)[0]
            async with connect(
                f"ws://127.0.0.1:{server.port}/ws",
                proxy=None,
                origin=Origin(f"http://127.0.0.1:{server.port}"),
                additional_headers={"Cookie": cookie},
                open_timeout=2,
                close_timeout=1,
            ) as client:
                for request, expected_cached, version in (
                    ({"id": "first"}, False, "test-build"),
                    ({"id": "cached"}, True, "test-build"),
                    ({"id": "force", "force": True}, False, "test-build"),
                    ({"id": "online", "online": True}, False, "online-build"),
                    ({"id": "offline-again"}, True, "test-build"),
                ):
                    await client.send(json.dumps({"type": "home.snapshot", **request}))
                    reply = json.loads(await asyncio.wait_for(client.recv(), 3))
                    assert (
                        reply["v"],
                        reply["id"],
                        reply["type"],
                        reply["ok"],
                        reply["cached"],
                    ) == (
                        1,
                        request["id"],
                        "home.snapshot",
                        True,
                        expected_cached,
                    )
                    assert reply["snapshot"]["harness_version"] == version
                snapshot = reply["snapshot"]
                assert snapshot["health"] == {
                    "ok": 0,
                    "warn": 0,
                    "fail": 0,
                    "skipped": 0,
                }
                assert snapshot["active_batches"] is None
                assert snapshot["repo_map"]["head_map"] is None
                assert snapshot["memory"] == {"state": None, "policy": None}
        finally:
            await server.close()

    asyncio.run(scenario())


def test_invalid_bootstrap_requests_do_not_consume_browser_issuance(project: Path) -> None:
    async def scenario() -> None:
        server = ConsoleServer(project)
        await server.start()
        token = token_for(project)
        try:
            for path in (
                "/?token=", "/?token=wrong", "/?token=%D1%82",
                f"/?token={token}&token={token}",
                f"/?token={token}&lang=ru&lang=en",
                f"/?token={token}&unknown=value",
            ):
                status, headers, _ = await http(server, path)
                assert status == 401 and "Set-Cookie" not in headers
            missing = await http(server, "/unknown?token=" + token)
            assert missing[0] == 404 and "Set-Cookie" not in missing[1]
            first = await http(server, "/?token=" + token)
            assert first[0] == 303 and "Set-Cookie" in first[1]
        finally:
            await server.close()

    asyncio.run(scenario())


def test_browser_reconnect_restores_snapshot_with_stale_warning(project: Path) -> None:
    from websockets.asyncio.client import connect
    from websockets.typing import Origin

    async def scenario() -> None:
        server = ConsoleServer(project)
        await server.start()
        try:
            issued = await http(server, '/?token=' + token_for(project))
            cookie = issued[1]['Set-Cookie'].split(';', 1)[0]
            page = (await http(server, headers={'Cookie': cookie}))[2].decode()
            assert 'id="snapshot-stale"' in page
            assert 'Последний снимок устарел' in page
            for request_id in ('before-disconnect', 'after-reconnect'):
                async with connect(
                    f'ws://127.0.0.1:{server.port}/ws', proxy=None,
                    origin=Origin(f'http://127.0.0.1:{server.port}'),
                    additional_headers={'Cookie': cookie}, open_timeout=2, close_timeout=1,
                ) as client:
                    await client.send(json.dumps({'id': request_id, 'type': 'home.snapshot'}))
                    reply = json.loads(await asyncio.wait_for(client.recv(), 3))
                    assert reply['id'] == request_id and reply['ok'] is True
                    assert reply['snapshot']['version'] == 1
        finally:
            await server.close()

    asyncio.run(scenario())


def test_web_language_query_default_and_shared_labels(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from harness.console import i18n

    monkeypatch.setenv('HARNESS_CONSOLE_LANG', 'en')

    async def scenario() -> None:
        server = ConsoleServer(project)
        await server.start()
        try:
            issued = await http(server, '/?token=' + token_for(project))
            assert issued[1]['Location'] == '/?lang=en'
            cookie = issued[1]['Set-Cookie'].split(';', 1)[0]
            for query, language, title, unavailable in (
                ('', 'en', 'Harness health', 'Unavailable in the current snapshot'),
                ('?lang=invalid', 'en', 'Harness health', 'Unavailable in the current snapshot'),
                ('?lang=en', 'en', 'Harness health', 'Unavailable in the current snapshot'),
                ('?lang=ru', 'ru', 'Состояние харнесса', 'Недоступно в текущем снимке'),
            ):
                status, _, body = await http(server, '/' + query, headers={'Cookie': cookie})
                page = body.decode()
                assert status == 200 and f'<html lang="{language}">' in page
                assert title in page and unavailable in page
                if language == "en":
                    for fixed_label in ("Name", "Tracker", "Package"):
                        assert f"<dt>{fixed_label}</dt>" in page
                assert f'aria-label="{i18n.tr(language, "Открыть меню")}"' in page
                for label in ('Home', 'Diagnostics', 'Update Harness', 'Help'):
                    assert i18n.section_label(language, label) in page
                assert 'href="/?lang=ru"' in page and 'href="/?lang=en"' in page
                assert token_for(project) not in page
        finally:
            await server.close()

    asyncio.run(scenario())


def test_browser_bootstrap_rejects_get_body_before_consuming_cookie(project: Path) -> None:
    from tests.console.test_server import _raw

    async def scenario() -> None:
        server = ConsoleServer(project)
        await server.start()
        try:
            token = token_for(project)
            reply = await _raw(server.port, (
                f'GET /?token={token} HTTP/1.1\r\nHost: 127.0.0.1:{server.port}\r\n'
                'Content-Length: 1\r\nConnection: close\r\n\r\nx'
            ).encode())
            assert reply.startswith(b'HTTP/1.1 400 ')
            assert b'Set-Cookie:' not in reply
            assert (await http(server, '/?token=' + token))[0] == 303
        finally:
            await server.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ('path', 'method', 'credential', 'status'),
    [
        ('/', 'GET', 'absent', 401),
        ('/static/home.js', 'GET', 'absent', 401),
        ('/', 'GET', 'wrong-origin', 403),
        ('/', 'GET', 'wrong-host', 403),
        ('/', 'GET', 'mixed', 401),
        ('/', 'GET', 'duplicate-cookie', 401),
        ('/', 'GET', 'duplicate-bearer', 401),
        ('/', 'GET', 'malformed-cookie', 401),
        ('/', 'GET', 'duplicate-selected', 401),
        ('/', 'GET', 'invalid-selected-valid-legacy', 401),
        ('/', 'POST', 'cookie', 405),
        ('/static/../server.py', 'GET', 'cookie', 404),
        ('/static/%2e%2e/server.py', 'GET', 'cookie', 404),
        ('/static/home.js?file=server.py', 'GET', 'cookie', 404),
        ('/static/unknown.css', 'GET', 'cookie', 404),
    ],
)
def test_web_rejections_keep_security_headers(
    project: Path, path: str, method: str, credential: str, status: int,
) -> None:
    from tests.console.test_server import _raw

    async def scenario() -> None:
        server = ConsoleServer(project)
        await server.start()
        try:
            token = token_for(project)
            issued = await http(server, '/?token=' + token)
            cookie = issued[1]['Set-Cookie'].split(';', 1)[0]
            headers = [('Host', f'127.0.0.1:{server.port}')]
            if credential != 'absent':
                headers.append(('Cookie', cookie))
            if credential == 'wrong-origin':
                headers.append(('Origin', 'http://example.invalid'))
            if credential == 'wrong-host':
                headers[0] = ('Host', 'localhost')
            if credential in ('mixed', 'duplicate-bearer'):
                headers.append(('Authorization', 'Bearer ' + token))
            if credential == 'duplicate-bearer':
                headers.remove(('Cookie', cookie))
                headers.append(('Authorization', 'Bearer ' + token))
            if credential == 'duplicate-cookie':
                headers.append(('Cookie', cookie))
            if credential == 'malformed-cookie':
                headers[-1] = ('Cookie', cookie + '; malformed')
            if credential == 'duplicate-selected':
                headers[-1] = ('Cookie', cookie + '; ' + cookie)
            if credential == 'invalid-selected-valid-legacy':
                headers[-1] = ('Cookie', f'console_token_{server.port}=wrong; console_token={token}')
            body = 'Content-Length: 1\r\n\r\nx' if method == 'POST' else '\r\n'
            wire = (f'{method} {path} HTTP/1.1\r\n'
                    + ''.join(f'{key}: {value}\r\n' for key, value in headers)
                    + 'Connection: close\r\n' + body)
            response = await _raw(server.port, wire.encode())
            head = response.split(b'\r\n\r\n', 1)[0].decode()
            assert head.startswith(f'HTTP/1.1 {status} ')
            assert 'Cache-Control: no-store' in head
            assert 'Referrer-Policy: no-referrer' in head
            assert 'X-Content-Type-Options: nosniff' in head
            assert 'X-Frame-Options: DENY' in head
            assert "default-src 'none'" in head and "frame-ancestors 'none'" in head
            assert 'Set-Cookie:' not in head and token not in head
            if status == 405:
                assert 'Allow: GET, HEAD' in head
        finally:
            await server.close()

    asyncio.run(scenario())


def test_home_head_matches_get_and_allows_only_local_csp(project: Path) -> None:
    async def scenario() -> None:
        server = ConsoleServer(project)
        await server.start()
        try:
            issued = await http(server, '/?token=' + token_for(project))
            auth = {'Cookie': issued[1]['Set-Cookie'].split(';', 1)[0]}
            get = await http(server, '/?lang=en', headers=auth)
            head = await http(server, '/?lang=en', method='HEAD', headers=auth)
            assert head == (200, get[1], b'')
            policy = get[1]['Content-Security-Policy']
            assert "script-src 'self'" in policy and "style-src 'self'" in policy
            assert f'connect-src ws://127.0.0.1:{server.port}' in policy
            assert 'unsafe-inline' not in policy and 'unsafe-eval' not in policy
            assert b'<script>' not in get[2] and b' style=' not in get[2]
        finally:
            await server.close()

    asyncio.run(scenario())


def test_two_browser_servers_share_unrelated_cookies_without_losing_sessions(project: Path) -> None:
    from websockets.asyncio.client import connect
    from websockets.typing import Origin

    other = project.parent / 'other-browser-project'
    other.mkdir()
    import subprocess
    subprocess.run(['git', '-C', str(other), 'init', '-q'], check=True)

    async def scenario() -> None:
        first = ConsoleServer(project)
        second = ConsoleServer(other)
        await first.start()
        await second.start()
        try:
            # Browsers share their host cookie jar across loopback ports.
            cookie = 'unrelated=keep; console_token=stale'
            for server, repo in ((first, project), (second, other)):
                issued = await http(server, '/?token=' + token_for(repo), headers={'Cookie': cookie})
                assert issued[0] == 303
                issued_cookie = issued[1]['Set-Cookie'].split(';', 1)[0]
                assert issued_cookie.startswith(f'console_token_{server.port}=')
                cookie += '; ' + issued_cookie
            for server in (first, second):
                assert (await http(server, headers={'Cookie': cookie}))[0] == 200
                async with connect(
                    f'ws://127.0.0.1:{server.port}/ws', proxy=None,
                    origin=Origin(f'http://127.0.0.1:{server.port}'),
                    additional_headers={'Cookie': cookie}, open_timeout=2, close_timeout=1,
                ) as client:
                    await client.send(json.dumps({'id': 'shared-jar', 'type': 'home.snapshot'}))
                    reply = json.loads(await asyncio.wait_for(client.recv(), 3))
                    assert reply['ok'] is True and reply['id'] == 'shared-jar'
        finally:
            await first.close()
            await second.close()

    asyncio.run(scenario())
