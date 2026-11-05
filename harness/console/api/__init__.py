"""FastAPI transport of the console server; the only console package that imports FastAPI,
Starlette, Uvicorn or Pydantic. ConsoleServer imports it lazily at startup."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..request_router import RequestRouter


class Runtime(Protocol):
    """What the transport reads from the server that owns it."""

    @property
    def port(self) -> int: ...

    @property
    def token(self) -> str: ...

    @property
    def closing(self) -> bool: ...

    @property
    def router(self) -> RequestRouter: ...

    def client_opened(self) -> None: ...

    def client_closed(self) -> None: ...
