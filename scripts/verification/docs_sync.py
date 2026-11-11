"""Согласованность документации с каталогом capability и зеркалом docs-agents.

Каждая проверка ловит расхождение, которое уже однажды попадало в релиз: текст, продублированный
вручную в нескольких документах, расходится с источником правды.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from scripts.verification.paths import (
    CAPABILITIES,
    DOCS_AGENTS_TEMPLATE,
    ROOT,
    SITE_PROJECT_STRUCTURE,
    SITE_REFERENCE_SKILLS,
)
from scripts.verification.text_checks import normalized_text

RETIRED_PATH_INVENTORY_TERM = re.compile(r"filtered\s+Repo\s+Map", re.IGNORECASE)
DIAGRAM_PREVIEW_LINK = re.compile(r"\]\(([^)]*diagrams/previews/[^)]+\.png)\)")
STATIC_IMAGE_ROOTS = (ROOT / "docs", ROOT / "site" / "docs")
PATH_INVENTORY_ROOTS = (
    ROOT / "skills" / "first-party" / "engineering" / "to-tickets",
    ROOT / "docs" / "agents",
    DOCS_AGENTS_TEMPLATE,
    ROOT / "site" / "docs",
    ROOT / "README.md",
)


@dataclass(frozen=True)
class EngineeringSuite:
    """Состав engineering-suite из CAPABILITIES.json: переопределённые и добавленные скиллы."""

    overrides: frozenset[str]
    additions: frozenset[str]


def load_engineering_suite() -> EngineeringSuite:
    """Прочитать состав engineering-suite из CAPABILITIES.json — источника правды для документации."""
    suite = json.loads(CAPABILITIES.read_text(encoding="utf-8"))["engineering-suite"]
    return EngineeringSuite(
        overrides=frozenset(suite["overrides"].keys()),
        additions=frozenset(
            entry.removeprefix("first-party/engineering/")
            for entry in suite["additions"]
        ),
    )


def _documented(pattern: str, text: str) -> set[str]:
    """Имена в обратных кавычках, найденные в тексте по шаблону строки таблицы или списка."""
    return set(re.findall(pattern, text, re.MULTILINE))


# Шаблоны-заготовки, которые проект заполняет сам: с копией сверяются текст до первого `## `
# и список заголовков `## `, а тела секций у этого репозитория свои.
PROJECT_FILLED_TEMPLATES = frozenset({"agent-prompt.md"})


def _filled_template_shape(text: str) -> tuple[str, list[str]]:
    """Вводный текст до первого заголовка `## ` и сами заголовки `## ` по порядку."""
    lines = text.split("\n")
    headings = [line for line in lines if line.startswith("## ")]
    first = next(
        (i for i, line in enumerate(lines) if line.startswith("## ")), len(lines)
    )
    return "\n".join(lines[:first]).strip(), headings


def check_docs_agents_mirror() -> None:
    """Проверить, что docs/agents/*.md совпадают с harness/project/docs-agents/*.md.

    docs/agents — собственная копия файлов, которые scaffold_engineering_extras разворачивает в каждый
    проект engineering-suite. Обе копии правятся вручную, поэтому расхождение ловится здесь.
    У заготовок из PROJECT_FILLED_TEMPLATES сверяются только вводный текст и заголовки секций.
    """
    for template in sorted(DOCS_AGENTS_TEMPLATE.glob("*.md")):
        counterpart = ROOT / "docs" / "agents" / template.name
        if not counterpart.is_file():
            sys.exit(f"{template} has no docs/agents counterpart: {counterpart}")
        if template.name in PROJECT_FILLED_TEMPLATES:
            if _filled_template_shape(
                normalized_text(template)
            ) != _filled_template_shape(normalized_text(counterpart)):
                sys.exit(
                    f"docs/agents/{template.name} intro or sections have drifted from "
                    f"harness/project/docs-agents/{template.name}"
                )
            continue
        if normalized_text(template) != normalized_text(counterpart):
            sys.exit(
                f"docs/agents/{template.name} has drifted from harness/project/docs-agents/{template.name}"
            )


def check_diagram_previews() -> None:
    """Проверить, что каждая ссылка на превью диаграммы ведёт на существующий PNG.

    Превью лежат в site/docs/diagrams/previews/. Проверка покрывает и корневой docs/, и site/docs:
    битая картинка ловится там, где она появилась.
    """
    for base in STATIC_IMAGE_ROOTS:
        for path in sorted(base.rglob("*.md")) if base.is_dir() else []:
            for link in DIAGRAM_PREVIEW_LINK.findall(
                path.read_text(encoding="utf-8", errors="replace")
            ):
                if "://" in link:
                    continue
                if not (path.parent / link).resolve().is_file():
                    sys.exit(f"{path}: diagram preview link is broken: {link}")


def check_no_retired_path_inventory_term() -> None:
    """Не допустить возврата термина «filtered Repo Map».

    Артефакт /to-tickets только с путями называется «Path inventory»; «Repo Map» — только
    семантическая карта (CONTEXT.md).
    """
    for base in PATH_INVENTORY_ROOTS:
        for path in sorted(base.rglob("*") if base.is_dir() else [base]):
            if path.is_file() and RETIRED_PATH_INVENTORY_TERM.search(
                path.read_text(encoding="utf-8", errors="replace")
            ):
                sys.exit(
                    f'{path}: retired term "filtered Repo Map"; use "Path inventory"'
                )


def check_docs_agents_enumeration() -> None:
    """Проверить перечисление docs/agents/{...}.md в README.md и на странице структуры.

    Оба документа вручную перечисляют файлы, которые разворачивает scaffold_engineering_extras.
    Однажды список в документе разошёлся с шаблонами.
    """
    names = {path.stem for path in DOCS_AGENTS_TEMPLATE.glob("*.md")}
    for doc in (ROOT / "README.md", SITE_PROJECT_STRUCTURE):
        match = re.search(r"docs/agents/\{([a-z0-9,-]+)\}\.md", normalized_text(doc))
        if not match:
            sys.exit(f"{doc}: no docs/agents/{{...}}.md enumeration found")
        listed = set(match.group(1).split(","))
        if listed != names:
            sys.exit(
                f"{doc}: docs/agents/{{...}}.md enumeration {sorted(listed)} does not match "
                f"harness/project/docs-agents/*.md {sorted(names)}"
            )


def _site_section(path: Path, pattern: str, missing: str) -> str:
    """Раздел страницы сайта по регулярному выражению или завершение с ошибкой."""
    section = re.search(pattern, normalized_text(path), re.DOTALL)
    if not section:
        sys.exit(missing)
    return section.group(1)


def check_pvmalove_override_docs_sync() -> None:
    """Сверить таблицу переопределений на сайте с engineering-suite.overrides.

    Однажды wayfinder попал в overrides без строки в таблице.
    """
    expected = set(load_engineering_suite().overrides)
    section = _site_section(
        SITE_REFERENCE_SKILLS,
        r"\n## Проектные переопределения\n(.*?)\n## ",
        f"{SITE_REFERENCE_SKILLS}: could not find the 'Проектные переопределения' section",
    )
    documented = _documented(r"^\| `([a-z0-9-]+)` \|", section)
    if documented != expected:
        sys.exit(
            f"{SITE_REFERENCE_SKILLS}: overrides table is out of sync with engineering-suite "
            f"overrides in CAPABILITIES.json: missing={sorted(expected - documented)} "
            f"extra={sorted(documented - expected)}"
        )


def check_pvmalove_additions_docs_sync() -> None:
    """Сверить таблицу проектных скиллов на сайте с engineering-suite.additions.

    Однажды setup-labels попал в additions без строки в таблице.
    """
    expected = set(load_engineering_suite().additions)
    section = _site_section(
        SITE_REFERENCE_SKILLS,
        r"\n### Проектные скиллы \(first-party\)\n(.*?)\n## ",
        f"{SITE_REFERENCE_SKILLS}: could not find the first-party skill catalog table",
    )
    documented = _documented(r"^\| `([a-z0-9-]+)` \(skill\) \|", section)
    if documented != expected:
        sys.exit(
            f"{SITE_REFERENCE_SKILLS}: first-party skill table is out of sync with "
            f"engineering-suite additions in CAPABILITIES.json: "
            f"missing={sorted(expected - documented)} extra={sorted(documented - expected)}"
        )


def _check_listed(
    doc: Path, text: str, pattern: str, kind: str, expected: frozenset[str]
) -> None:
    """Сверить список имён в прозе документа с ожидаемым набором из CAPABILITIES.json."""
    match = re.search(pattern, text)
    if not match:
        sys.exit(f"{doc}: no engineering-suite {kind} list found")
    documented = set(re.findall(r"`([a-z0-9-]+)`", match.group(1)))
    if documented != expected:
        sys.exit(
            f"{doc}: {kind} list {sorted(documented)} does not match "
            f"CAPABILITIES.json {kind} {sorted(expected)}"
        )


def check_pvmalove_suite_summary_sync() -> None:
    """Сверить списки переопределений и дополнений в прозе README.md и CONTEXT.md.

    Однажды устаревшие счётчики «5 overrides, 1 addition» прожили три дня после правки только
    таблицы переопределений.
    """
    suite = load_engineering_suite()
    for doc in (ROOT / "README.md", ROOT / "CONTEXT.md"):
        text = normalized_text(doc)
        _check_listed(
            doc,
            text,
            r"переопределены в `skills/first-party/engineering/`:\s*(.+?);",
            "overrides",
            suite.overrides,
        )
        _check_listed(
            doc, text, r"доп\. скиллы:\s*(.+?)\.", "additions", suite.additions
        )
