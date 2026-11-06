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

    assert found == [], "внутренние номера задач на публичных страницах:\n" + "\n".join(
        found
    )


IMG_TAG = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
ALT = re.compile(r"""\balt\s*=\s*(["'])(.*?)\1""", re.IGNORECASE | re.DOTALL)


def _alt(tag: str) -> str:
    match = ALT.search(tag)
    return match.group(2).strip() if match else ""


def _mascot_tags() -> list[tuple[Path, str]]:
    tags: list[tuple[Path, str]] = []
    for path in sorted(SITE.rglob("*")):
        if path.suffix not in {".md", ".html"} or "node_modules" in path.parts:
            continue
        for tag in IMG_TAG.findall(path.read_text(encoding="utf-8")):
            if "mascot.svg" in tag:
                tags.append((path, tag))
    return tags


def test_hero_has_the_mascot_with_alt() -> None:
    page = (SITE_DOCS / "index.md").read_text(encoding="utf-8")

    block = re.search(r'class="ah-mascot ah-mascot--perch".*?</div>', page, re.DOTALL)
    assert block is not None
    image = re.search(r'<img[^>]*src="assets/mascot\.svg"[^>]*>', block.group(0))
    assert image is not None
    assert _alt(image.group(0))


def test_footer_has_the_mascot_with_alt() -> None:
    footer = (SITE / "overrides" / "partials" / "copyright.html").read_text(
        encoding="utf-8"
    )

    image = re.search(r"<img[^>]*assets/mascot\.svg[^>]*>", footer)
    assert image is not None
    assert _alt(image.group(0))


def test_every_mascot_image_has_alt() -> None:
    tags = _mascot_tags()

    assert tags, "маскот не найден ни на одной странице"
    missing = [path.relative_to(SITE).as_posix() for path, tag in tags if not _alt(tag)]
    assert missing == []


def test_mascot_asset_is_accessible() -> None:
    svg = (SITE_DOCS / "assets" / "mascot.svg").read_text(encoding="utf-8")

    assert 'role="img"' in svg
    assert "<title>" in svg
