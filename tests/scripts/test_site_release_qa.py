"""Контент-QA публичного сайта: нет внутренних номеров задач; маскот на месте."""

from __future__ import annotations

import re
from pathlib import Path

from scripts.verification.paths import SITE_DOCS

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"

ISSUE_NUMBER = re.compile(r"(?<![\w&/])#\d{3,5}\b")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE = re.compile(r"`[^`\n]*`")
# Номера-заглушки из примеров команд (`--ticket '#123'`), не ссылки на задачи.
ALLOWED_PLACEHOLDERS = {"#123", "#443", "#456"}
# releases/ — журнал версий со ссылками на GitHub; skills/vendor/ — снимок upstream.
SKIPPED_DIRS = ("releases", "skills/vendor")


def _prose_lines(text: str) -> list[tuple[int, str]]:
    """Строки вне fenced-блоков, без inline-кода."""
    lines: list[tuple[int, str]] = []
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        marker = FENCE.match(line)
        if marker:
            if fence is None:
                fence = marker.group(1)[0]
            elif marker.group(1)[0] == fence:
                fence = None
            continue
        if fence is None:
            lines.append((number, INLINE_CODE.sub("", line)))
    return lines


def _markdown_pages() -> list[Path]:
    pages = []
    for path in sorted(SITE_DOCS.rglob("*.md")):
        relative = path.relative_to(SITE_DOCS).as_posix()
        if relative.startswith(tuple(f"{name}/" for name in SKIPPED_DIRS)):
            continue
        pages.append(path)
    return pages


def test_public_pages_have_no_internal_issue_numbers() -> None:
    found: list[str] = []
    for path in _markdown_pages():
        text = path.read_text(encoding="utf-8")
        for number, line in _prose_lines(text):
            for match in ISSUE_NUMBER.finditer(line):
                if match.group(0) in ALLOWED_PLACEHOLDERS:
                    continue
                relative = path.relative_to(SITE_DOCS).as_posix()
                found.append(f"{relative}:{number}: {line.strip()[:120]}")

    assert found == [], "внутренние номера задач на публичных страницах:\n" + "\n".join(found)
