"""The console FastAPI application: plain-text pages, /ws and the security middleware."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from starlette.exceptions import HTTPException

from . import Runtime
from .security import REJECTED, SecurityMiddleware
from .static import mount_static
from .websocket import register_websocket

PAGE = "Console server\n"


def create_app(runtime: Runtime) -> FastAPI:
    app = FastAPI(
        title="Harness console server",
        version="1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        debug=False,
    )

    @app.exception_handler(HTTPException)
    async def rejected(request: Request, exc: HTTPException) -> PlainTextResponse:
        return PlainTextResponse(REJECTED.decode(), status_code=exc.status_code)

    async def page() -> PlainTextResponse:
        return PlainTextResponse(PAGE)

    app.add_api_route(
        "/health/live",
        page,
        methods=["GET"],
        response_class=PlainTextResponse,
        summary="Liveness of the console server",
        operation_id="health_live",
    )
    app.add_api_route("/health/live", page, methods=["HEAD"], include_in_schema=False)
    register_websocket(app, runtime)
    # Registered last: /health/live and /ws keep priority over the build mounted at "/".
    if not mount_static(app, runtime):
        app.add_api_route("/", page, methods=["GET", "HEAD"], include_in_schema=False)
    app.add_middleware(SecurityMiddleware, runtime=runtime)
    return app
