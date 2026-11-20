"""Внутренние ссылки публичного сайта, которые не проверяет MkDocs.

MkDocs валидирует ссылки Markdown, но не `src`/`href` в raw HTML (iframe демо, картинки,
кнопки-карточки). Здесь проверяются оба вида: Markdown-ссылка разрешается от исходного файла,
raw HTML — от URL собранной страницы, потому что MkDocs атрибуты HTML не переписывает.
"""

from __future__ import annotations

import posixpath
import re
import sys
from pathlib import Path
from urllib.parse import unquote

from scripts.verification.paths import SITE_DOCS

MARKDOWN_LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HTML_ATTRIBUTE = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "data:", "//", "{{", "{%")
CHECKED_SUFFIXES = {".md", ".html"}


def _target(raw: str) -> str:
    """Цель без якоря и query, с раскодированными percent-escape."""
    return unquote(raw.split("#", 1)[0].split("?", 1)[0])


def _skipped(target: str) -> bool:
    return not target or target.startswith(SKIP_PREFIXES) or target.startswith("/")


def _is_english(path: Path) -> bool:
    """Английская пара `x.en.md` / `x.en.html` (mkdocs-static-i18n, `docs_structure: suffix`)."""
    return path.stem.endswith(".en")


def _default_name(path: Path) -> str:
    """Имя русского файла-пары: `index.en.md` -> `index.md`."""
    return (
        path.name.replace(f".en{path.suffix}", path.suffix)
        if _is_english(path)
        else path.name
    )


def _page_base(path: Path, docs_dir: Path) -> str:
    """Каталог URL страницы относительно корня сайта при `use_directory_urls: true`.

    Английская Markdown-пара публикуется под `en/`: её raw HTML разрешается от этого URL.
    Статический `.en.html` — самостоятельный документ в корне сайта, а не страница i18n,
    поэтому его ссылки разрешаются от собственного каталога.
    """
    relative = path.relative_to(docs_dir)
    name = _default_name(path)
    if path.suffix != ".md" or name == "index.md":
        base = relative.parent.as_posix()
    else:
        base = (relative.parent / Path(name).stem).as_posix()
    if path.suffix == ".md" and _is_english(path):
        return posixpath.normpath(posixpath.join("en", base))
    return base


def _page_exists(normalized: str, docs_dir: Path) -> bool:
    """Страница сайта: `X.md`, `X/index.md` или `X.html` с `X.md` (без статических файлов)."""
    candidate = docs_dir / normalized
    if candidate.suffix == ".html" and candidate.with_suffix(".md").is_file():
        return True
    if (candidate / "index.md").is_file():
        return True
    return candidate.suffix == "" and candidate.with_suffix(".md").is_file()


def _english_exists(rest: str, docs_dir: Path) -> bool:
    """Цель под `en/`: локализованный файл `X.en.Y` либо страница (её отдаёт fallback на русскую)."""
    if rest in ("", "."):
        return (docs_dir / "index.md").is_file()
    candidate = docs_dir / rest
    if candidate.suffix and candidate.with_suffix(f".en{candidate.suffix}").is_file():
        return True
    if candidate.suffix not in ("", ".md", ".html"):
        return False
    return _page_exists(rest, docs_dir)


def _exists(relative: str, docs_dir: Path) -> bool:
    """Существует ли цель: файл, страница `X.md` или каталог с `index.md`."""
    normalized = posixpath.normpath(relative)
    if normalized == "en" or normalized.startswith("en/"):
        return _english_exists(normalized.removeprefix("en").lstrip("/"), docs_dir)
    if normalized in ("", "."):
        return (docs_dir / "index.md").is_file()
    if normalized.startswith(".."):
        return False
    candidate = docs_dir / normalized
    if candidate.is_file():
        return True
    if candidate.suffix == ".html" and candidate.with_suffix(".md").is_file():
        return True
    if (candidate / "index.md").is_file():
        return True
    return candidate.suffix == "" and candidate.with_suffix(".md").is_file()


def _source_link(path: Path, target: str, docs_dir: Path) -> bool:
    """Markdown-ссылка: MkDocs разрешает её от файла и сам переписывает URL."""
    source = (path.parent / target).resolve()
    if not source.is_relative_to(docs_dir):
        return False
    if source.is_file() or (source / "index.md").is_file():
        return True
    if source.suffix == ".html" and source.with_suffix(".md").is_file():
        return True
    return source.suffix == "" and source.with_suffix(".md").is_file()


def _html_link(path: Path, target: str, docs_dir: Path) -> bool:
    """Raw HTML: относительная ссылка считается от URL собранной страницы."""
    return _exists(posixpath.join(_page_base(path, docs_dir), target), docs_dir)


def find_broken_links(docs_dir: Path) -> list[str]:
    """Относительные ссылки, ведущие на несуществующий файл публичного сайта."""
    docs_root = docs_dir.resolve()
    broken: list[str] = []
    for path in sorted(docs_dir.rglob("*")):
        if not path.is_file() or path.suffix not in CHECKED_SUFFIXES:
            continue
        if path.suffix == ".html" and _is_english(path):
            # Статический `.en.html` — самостоятельный документ, который i18n публикует
            # как `en/X.html`; его ссылки проверяются собственным инструментом экспорта.
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        links: list[tuple[str, bool]] = []
        if path.suffix == ".md":
            links += [(raw, True) for raw in MARKDOWN_LINK.findall(text)]
        links += [(raw, False) for raw in HTML_ATTRIBUTE.findall(text)]
        for raw, from_markdown in links:
            target = _target(raw)
            if _skipped(target):
                continue
            valid = (
                _source_link(path, target, docs_root)
                if from_markdown
                else _html_link(path, target, docs_root)
            )
            if not valid:
                broken.append(f"{path.relative_to(docs_dir)}: {target}")
    return broken


def check_site_links() -> None:
    """Остановить `make verify` на первой битой внутренней ссылке сайта."""
    broken = find_broken_links(SITE_DOCS)
    if broken:
        sys.exit("site: broken internal links:\n" + "\n".join(broken))
