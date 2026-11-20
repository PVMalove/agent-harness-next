"""A real console server for the Playwright specs, run as `python -m tests.web.serve_console`.

It serves `harness/console/frontend/dist` for a temporary empty Git project with the real
admission, CSP, cookie and WebSocket. It prints one JSON line `{"port": ..., "token": ...}` and
stops on stdin EOF or SIGTERM. Not a pytest module."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading

from harness.console.backend.server import ConsoleServer

DIST = Path(__file__).resolve().parents[2] / "harness" / "console" / "frontend" / "dist"
# The specs keep no WebSocket open between tests: the idle rule must not end the server.
IDLE_GRACE_SECONDS = 24 * 3600


async def serve(dist: Path = DIST) -> None:
    if not (dist / "index.html").is_file():
        raise SystemExit(
            f"no build in {dist}: run `npm run build` in harness/console/frontend"
        )
    with tempfile.TemporaryDirectory(prefix="harness-web-e2e-") as temporary:
        project = Path(temporary) / "project"
        project.mkdir()
        subprocess.run(["git", "init", "-q", str(project)], check=True)
        server = ConsoleServer(
            project, idle_grace_seconds=IDLE_GRACE_SECONDS, static_root=dist
        )
        await server.start()
        try:
            print(json.dumps({"port": server.port, "token": server.token}), flush=True)
            loop = asyncio.get_running_loop()
            stop = asyncio.Event()
            loop.add_signal_handler(signal.SIGTERM, stop.set)
            # A daemon thread: a blocked read never delays the exit after SIGTERM.
            threading.Thread(
                target=lambda: (sys.stdin.read(), loop.call_soon_threadsafe(stop.set)),
                daemon=True,
            ).start()
            await stop.wait()
        finally:
            await server.close()


if __name__ == "__main__":
    asyncio.run(serve())
