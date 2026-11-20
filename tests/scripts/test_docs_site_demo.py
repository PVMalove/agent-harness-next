"""Демо-страница сайта: встроенная консоль, описание экранов и 404."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "site" / "docs" / "demo"
SCREENS = [
    "home",
    "diagnostics",
    "update-harness",
    "open-project",
    "board",
    "agent-activity",
    "orchestration",
    "reports",
    "publish",
    "harness",
    "repo-map",
    "configuration",
    "help",
]


def _demo() -> tuple[str, str]:
    return (
        (DEMO / "index.md").read_text(encoding="utf-8"),
        (DEMO / "execution-console.js").read_text(encoding="utf-8"),
    )


def test_demo_embeds_the_console_without_a_switcher() -> None:
    page, _ = _demo()

    assert 'src="console.html#home"' in page
    assert 'title="Демонстрация веб-консоли"' in page
    assert 'loading="lazy"' in page
    assert 'href="console.html"' in page
    assert 'class="ah-demo-about"' in page
    assert 'id="ah-demo-title"' in page
    assert 'id="ah-demo-text"' in page
    assert 'data-screen=' not in page


def test_about_block_describes_every_console_screen() -> None:
    page, console = _demo()

    for screen in SCREENS:
        assert f"{screen}: [" in page or f'"{screen}": [' in page
        assert f"id:'{screen}'" in console
    assert 'src="../assets/mascot.svg"' in page


def test_404_page_keeps_the_mascot_and_a_way_back() -> None:
    page = (ROOT / "site" / "overrides" / "404.html").read_text(encoding="utf-8")

    assert '{% extends "main.html" %}' in page
    assert "ah-404" in page
    assert "'assets/mascot.svg' | url" in page
    assert "'getting-started/' | url" in page
