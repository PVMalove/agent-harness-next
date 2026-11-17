"""The host reads a container worker's model from the init event of its saved stream (#1125)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.orchestration import container_attestation

INIT = json.dumps({"type": "system", "subtype": "init", "model": "sonnet"}) + "\n"


def _stream(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "stdout.log"
    path.write_text(text, encoding="utf-8")
    return path


def test_init_after_long_hook_output_is_found(tmp_path: Path) -> None:
    hook = json.dumps(
        {"type": "system", "subtype": "hook_response", "output": "x" * 70000}
    )
    path = _stream(tmp_path, f"{hook}\nnot json\n{INIT}")

    assert container_attestation.init_model(path) == "sonnet"


def test_an_incomplete_init_line_is_not_read_yet(tmp_path: Path) -> None:
    assert container_attestation.init_model(_stream(tmp_path, INIT[:-1])) is None


def test_an_init_event_beyond_the_bound_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(container_attestation, "INIT_SCAN_BYTES", 100)
    path = _stream(tmp_path, "y" * 120 + "\n" + INIT)

    assert container_attestation.init_model(path) is None


def test_an_init_event_without_a_model_proves_nothing(tmp_path: Path) -> None:
    path = _stream(
        tmp_path, json.dumps({"type": "system", "subtype": "init"}) + "\n" + INIT
    )

    assert container_attestation.init_model(path) is None
