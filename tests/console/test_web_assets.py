"""Public packaged-resource delivery contracts for the browser shell."""
from __future__ import annotations

import asyncio
from importlib.resources import files
from pathlib import Path

import pytest

from harness.console.server import ConsoleServer
from tests.console.test_web import http, token_for


def test_console_css_is_byte_identical_to_accepted_mockup() -> None:
    source = Path(__file__).resolve().parents[2] / 'docs/design/web-console-mockups/execution-console.css'
    packaged = files('harness.console').joinpath('static', 'execution-console.css')
    assert packaged.is_file(), 'The accepted CSS must be included in the console package'
    assert packaged.read_bytes() == source.read_bytes()


def test_package_assets_work_outside_repository_cwd(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(project)

    async def scenario() -> None:
        server = ConsoleServer(project)
        await server.start()
        try:
            issued = await http(server, '/?token=' + token_for(project))
            cookie = issued[1]['Set-Cookie'].split(';', 1)[0]
            auth = {'Cookie': cookie}
            status, _, page = await http(server, headers=auth)
            assert status == 200
            assert b'href="/static/execution-console.css"' in page
            assert b'src="/static/harness-icons.js"' in page
            for name, mime in (
                ('execution-console.css', 'text/css; charset=utf-8'),
                ('harness-icons.js', 'text/javascript; charset=utf-8'),
                ('home.js', 'text/javascript; charset=utf-8'),
            ):
                path = '/static/' + name
                status, headers, body = await http(server, path, headers=auth)
                assert status == 200 and headers['Content-Type'] == mime
                assert body == files('harness.console').joinpath('static', name).read_bytes()
                head = await http(server, path, method='HEAD', headers=auth)
                assert head == (200, headers, b'')
                assert headers['Cache-Control'] == 'no-store'
        finally:
            await server.close()

    asyncio.run(scenario())
