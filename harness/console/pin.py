"""Единый источник истины для версии textual, запрашиваемой `harness console` через `uv run
--with` (ADR 0009). Секция `[dependency-groups].dev` в `pyproject.toml` фиксирует ту же версию,
чтобы локальные TUI-тесты выполнялись с ней без перезапуска; tests/console/test_console_pin.py проверяет их равенство."""

TEXTUAL_PIN = "6.5.0"

# Сервер консоли (ADR 0028, ADR 0029): FastAPI и Uvicorn через тот же механизм `uv run --with`. Dev-группа
# повторяет эти версии, а tests/console/test_console_pin.py проверяет их равенство.
FASTAPI_PIN = "0.162.0"
STARLETTE_PIN = "1.10.0"
UVICORN_PIN = "0.54.0"
PYDANTIC_PIN = "2.14.3"
WEBSOCKETS_PIN = "17.3"
CONSOLE_SERVER_REQUIREMENTS = (
    f"fastapi=={FASTAPI_PIN}",
    f"starlette=={STARLETTE_PIN}",
    f"uvicorn=={UVICORN_PIN}",
    f"pydantic=={PYDANTIC_PIN}",
    f"websockets=={WEBSOCKETS_PIN}",
)
