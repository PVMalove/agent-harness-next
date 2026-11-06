"""Английская версия сайта: конфиг i18n, пинованная зависимость и паритет страниц."""

from __future__ import annotations

import re
from pathlib import Path

from scripts.verification.paths import SITE_DOCS

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
I18N_VERSION = "mkdocs-static-i18n==1.3.1"
CYRILLIC = re.compile(r"[А-Яа-яЁё]")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE = re.compile(r"`[^`\n]*`")


def _config() -> str:
    return (SITE / "mkdocs.yml").read_text(encoding="utf-8")


def _russian_pages() -> list[Path]:
    return sorted(
        path for path in SITE_DOCS.rglob("*.md") if not path.name.endswith(".en.md")
    )


def _english_twin(path: Path) -> Path:
    return path.with_name(path.stem + ".en.md")


def test_i18n_plugin_is_configured() -> None:
    config = _config()

    assert re.search(r"^plugins:\s*\n\s+- search\b", config, re.MULTILINE)
    assert re.search(r"^\s+- i18n:", config, re.MULTILINE)
    assert "docs_structure: suffix" in config
    assert "fallback_to_default: true" in config
    assert re.search(r"- locale: ru\n\s+default: true\b", config)
    assert re.search(r"- locale: en\b", config)


def test_i18n_dependency_is_pinned() -> None:
    requirements = (SITE / "requirements.txt").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert I18N_VERSION in requirements.splitlines()
    for target in ("docs-build", "docs-serve"):
        recipe = re.search(rf"^{target}:.*\n\t(.*)$", makefile, re.MULTILINE)
        assert recipe is not None
        assert f"--with {I18N_VERSION}" in recipe.group(1)


def test_every_russian_page_has_an_english_twin() -> None:
    missing = [
        path.relative_to(SITE_DOCS).as_posix()
        for path in _russian_pages()
        if not _english_twin(path).is_file()
    ]

    assert missing == [], f"нет английской пары ({len(missing)}):\n" + "\n".join(missing)


def test_english_pages_have_no_russian_prose() -> None:
    found: list[str] = []
    for path in sorted(SITE_DOCS.rglob("*.en.md")):
        fence: str | None = None
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            marker = FENCE.match(line)
            if marker:
                fence = marker.group(1)[0] if fence is None else None
                continue
            if fence is not None or 'lang="ru"' in line:
                continue
            if CYRILLIC.search(INLINE_CODE.sub("", line)):
                found.append(f"{path.relative_to(SITE_DOCS).as_posix()}:{number}")

    assert found == [], f"кириллица в английских страницах ({len(found)}):\n" + "\n".join(found[:50])
