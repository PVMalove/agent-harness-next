"""Serves the React build from dist/ with a self-only content security policy."""

from __future__ import annotations

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from starlette.types import Message, Receive, Scope, Send

from . import Runtime


def static_policy(port: int) -> bytes:
    return (
        "default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; "
        f"img-src 'self'; connect-src 'self' ws://127.0.0.1:{port}; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'none'"
    ).encode()


class _SecuredStatic(StaticFiles):
    """Static files with no-store and the build's policy; errors keep the strict text policy."""

    def __init__(self, runtime: Runtime) -> None:
        super().__init__(directory=runtime.static_root, html=True, follow_symlink=False)
        self._runtime = runtime

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        headers = [
            (b"Cache-Control", b"no-store"),
            (b"X-Content-Type-Options", b"nosniff"),
            (b"X-Frame-Options", b"DENY"),
            (b"Content-Security-Policy", static_policy(self._runtime.port)),
        ]

        async def secured(message: Message) -> None:
            if message["type"] == "http.response.start":
                message = {
                    **message,
                    "headers": [*headers, *message.get("headers", [])],
                }
            await send(message)

        await super().__call__(scope, receive, secured)


def mount_static(app: FastAPI, runtime: Runtime) -> bool:
    """Mount the build at "/" when <static_root>/index.html exists."""
    if not (runtime.static_root / "index.html").is_file():
        return False
    app.mount("/", _SecuredStatic(runtime), name="static")
    return True
