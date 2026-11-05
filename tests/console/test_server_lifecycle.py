"""Graceful shutdown, the idle rule and active jobs of the FastAPI console server."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from harness.console.kernel.discovery import discovery_path
from harness.console.backend import composition
from harness.console.backend.server import ConsoleServer
from tests.console.test_jobs import FakeExecutor, start
from tests.console.test_server import _connect, _raw

_BIN_HARNESS = Path(__file__).resolve().parents[2] / "harness" / "bin" / "harness.py"


def _upgrade(port: int, token: str) -> bytes:
    return (
        f"GET /ws HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
        "Connection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
        f"Sec-WebSocket-Version: 13\r\nAuthorization: Bearer {token}\r\n\r\n"
    ).encode()


def test_close_with_a_connected_client_sends_close_and_releases_everything(
    project: Path,
) -> None:
    from websockets.exceptions import ConnectionClosed

    async def scenario() -> None:
        server = ConsoleServer(project)
        await server.start()
        port = server.port
        async with _connect(server, project) as client:
            started = asyncio.get_running_loop().time()
            await asyncio.wait_for(server.close(), 3)
            assert asyncio.get_running_loop().time() - started < 3
            with pytest.raises(ConnectionClosed):
                await asyncio.wait_for(client.recv(), 2)
            assert client.close_code is not None and client.close_code != 1006
        assert not discovery_path(project).exists()
        with pytest.raises(OSError):
            await asyncio.open_connection("127.0.0.1", port)

    asyncio.run(scenario())


def test_the_idle_rule_waits_for_the_last_client_and_then_the_grace(
    project: Path,
) -> None:
    async def scenario() -> None:
        server = ConsoleServer(project, idle_grace_seconds=0.4)
        await server.start()
        try:
            async with _connect(server, project):
                async with _connect(server, project):
                    await asyncio.sleep(0.6)
                await asyncio.sleep(0.6)
                assert not server._closed.is_set()
            disconnected = asyncio.get_running_loop().time()
            await asyncio.wait_for(server.wait_closed(), 3)
            assert asyncio.get_running_loop().time() - disconnected >= 0.3
            assert not discovery_path(project).exists()
        finally:
            await server.close()

    asyncio.run(scenario())


def test_an_active_job_keeps_the_server_until_it_ends(project: Path) -> None:
    async def scenario() -> None:
        fake = FakeExecutor()
        jobs = composition.job_service(project, executor=fake)
        server = ConsoleServer(project, jobs=jobs, idle_grace_seconds=0.1)
        await server.start()
        try:
            async with _connect(server, project) as client:
                assert (await start(client, command_id="diff"))["ok"] is True
                await asyncio.wait_for(fake.started.wait(), 3)
            await asyncio.sleep(0.5)
            assert jobs.active_count == 1
            assert not server._closed.is_set()
            fake.finish.set()
            await asyncio.wait_for(server.wait_closed(), 3)
            assert jobs.active_count == 0
        finally:
            fake.finish.set()
            await server.close()

    asyncio.run(scenario())


def test_a_handshake_while_closing_gets_503(project: Path) -> None:
    async def scenario() -> None:
        server = ConsoleServer(project)
        await server.start()
        token = json.loads(discovery_path(project).read_text())["token"]
        try:
            # close() marks the server closing before it stops the listener; hold that state.
            server._closing = True
            answer = await _raw(server.port, _upgrade(server.port, token))
            assert answer.startswith(b"HTTP/1.1 503 ")
            assert answer.endswith(b"Console is closing\n")
        finally:
            await server.close()

    asyncio.run(scenario())


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal delivery")
def test_console_server_command_exits_on_sigint_and_removes_discovery(
    project: Path,
) -> None:
    record = discovery_path(project)
    process = subprocess.Popen(
        [sys.executable, str(_BIN_HARNESS), "console-server", str(project)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONPATH": str(_BIN_HARNESS.parents[2])},
    )
    try:
        deadline = time.monotonic() + 10
        while not record.exists():
            assert process.poll() is None, process.communicate()
            assert time.monotonic() < deadline, "discovery record never appeared"
            time.sleep(0.05)
        port = json.loads(record.read_text())["port"]

        async def live() -> bytes:
            return await _raw(
                port,
                f"GET /health/live HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\r\n".encode(),
            )

        assert asyncio.run(live()).startswith(b"HTTP/1.1 200 ")
        process.send_signal(signal.SIGINT)
        _, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr
        assert not record.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
