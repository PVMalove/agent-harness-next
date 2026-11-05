"""The /ws route: a thin adapter between Starlette's WebSocket and the request router."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from . import Runtime


def register_websocket(app: FastAPI, runtime: Runtime) -> None:
    @app.websocket("/ws")
    async def console_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        closing: set[asyncio.Task[None]] = set()

        async def send(reply: str) -> bool:
            try:
                await websocket.send_text(reply)
            except (WebSocketDisconnect, RuntimeError):
                return False
            return True

        async def abort() -> None:
            try:
                await websocket.close(1011)
            except (WebSocketDisconnect, RuntimeError):
                pass

        def on_failure() -> None:
            task = asyncio.create_task(abort())
            closing.add(task)
            task.add_done_callback(closing.discard)

        connection = runtime.router.open(send, on_failure)
        runtime.client_opened()
        try:
            while True:
                message = await websocket.receive()
                if message["type"] != "websocket.receive":
                    return
                text = message.get("text")
                if text is None:
                    async with connection.lock:
                        await websocket.close(1003, "No application protocol")
                    return
                await connection.submit(text)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            runtime.client_closed()
            await connection.aclose()
            await asyncio.gather(*closing, return_exceptions=True)
