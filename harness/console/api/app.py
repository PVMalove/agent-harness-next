"""The console FastAPI application: plain-text pages, /ws and the security middleware."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from starlette.exceptions import HTTPException

from . import Runtime
from .security import REJECTED, SecurityMiddleware
from .websocket import register_websocket

PAGE = "Console server\n"


def create_app(runtime: Runtime) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, debug=False)

    @app.exception_handler(HTTPException)
    async def rejected(request: Request, exc: HTTPException) -> PlainTextResponse:
        return PlainTextResponse(REJECTED.decode(), status_code=exc.status_code)

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    @app.api_route("/health/live", methods=["GET", "HEAD"], include_in_schema=False)
    async def page() -> PlainTextResponse:
        return PlainTextResponse(PAGE)

    register_websocket(app, runtime)
    app.add_middleware(SecurityMiddleware, runtime=runtime)
    return app
