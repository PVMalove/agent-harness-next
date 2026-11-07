"""The console server serves a React build from dist/ over GET and HEAD only."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.console.backend.server import DEFAULT_STATIC_ROOT

INDEX = b"<!doctype html><title>Console</title><script src=/assets/app.js></script>"
ASSET = b"console.log('console');\n"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_bytes(INDEX)
    (root / "assets" / "app.js").write_bytes(ASSET)
    return root


def test_the_default_build_lives_in_the_frontend_directory() -> None:
    root = Path(__file__).resolve().parents[2]
    assert DEFAULT_STATIC_ROOT == root / "harness" / "console" / "frontend" / "dist"
