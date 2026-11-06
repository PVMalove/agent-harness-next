"""Демо-страница сайта: переключатель, iframe и пустое состояние с маскотом."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "site" / "docs" / "demo"
SCREENS = ["home", "board", "orchestration", "reports"]


def _demo() -> tuple[str, str]:
    return (
        (DEMO / "index.md").read_text(encoding="utf-8"),
        (DEMO / "execution-console.js").read_text(encoding="utf-8"),
    )


def test_switcher_targets_the_console_screens() -> None:
    page, console = _demo()
    targets = re.findall(r'data-screen="([a-z]+)"', page)

    assert targets == SCREENS
    assert all(f"id:'{screen}'" in console for screen in targets)


def test_demo_loads_the_console_lazily_with_a_fallback() -> None:
    page, _ = _demo()

    assert 'title="Демонстрация веб-консоли"' in page
    assert 'loading="lazy"' in page
    assert 'href="console.html"' in page
    assert "console.html#" in page


def test_empty_state_uses_the_site_mascot() -> None:
    page, _ = _demo()

    assert 'class="ah-demo-empty"' in page
    assert 'src="../assets/mascot.svg"' in page
    assert (ROOT / "site" / "docs" / "assets" / "mascot.svg").is_file()


def test_404_page_keeps_the_mascot_and_a_way_back() -> None:
    page = (ROOT / "site" / "overrides" / "404.html").read_text(encoding="utf-8")

    assert '{% extends "main.html" %}' in page
    assert "ah-404" in page
    assert "'assets/mascot.svg' | url" in page
    assert "'getting-started/' | url" in page
