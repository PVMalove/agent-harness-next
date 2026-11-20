"""Keeps two textual pins equal: harness/console/pin.py (what `uv run --with` requests, ADR 0009)
and pyproject.toml's [dependency-groups].dev (what `uv sync` installs for local TUI tests)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from harness.console.pin import TEXTUAL_PIN

ROOT = Path(__file__).resolve().parents[2]


def test_dev_dependency_group_pins_the_same_textual_version_as_console_pin() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev_group = pyproject["dependency-groups"]["dev"]
    pinned = [entry for entry in dev_group if entry.startswith("textual==")]

    assert pinned == [f"textual=={TEXTUAL_PIN}"]


def test_dev_dependency_group_pins_every_console_server_requirement() -> None:
    from harness.console import pin

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev_group = pyproject["dependency-groups"]["dev"]

    assert pin.CONSOLE_SERVER_REQUIREMENTS == (
        "fastapi==0.162.0",
        "starlette==1.10.0",
        "uvicorn==0.54.0",
        "pydantic==2.14.3",
        "websockets==17.3",
    )
    names = ("fastapi==", "starlette==", "uvicorn==", "pydantic==", "websockets==")
    pinned = [entry for entry in dev_group if entry.startswith(names)]
    assert sorted(pinned) == sorted(pin.CONSOLE_SERVER_REQUIREMENTS)


def test_retired_transport_pins_are_gone() -> None:
    from harness.console import pin

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev_group = pyproject["dependency-groups"]["dev"]

    assert not hasattr(pin, "H11_PIN") and not hasattr(pin, "JINJA2_PIN")
    assert not [entry for entry in dev_group if entry.startswith(("h11", "jinja2"))]
