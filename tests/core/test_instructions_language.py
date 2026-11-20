"""Agent instructions and agent definitions are English (#814).

Russian descriptions live only on the site (`site/docs/agents/`). Code spans and fenced blocks may
hold output data in the project language — the `language: ru` PR headings of `git-workflow.md` are
an example — so they are not instruction text.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCES = sorted(
    [
        *(ROOT / "harness" / "project" / "instructions").glob("*.md"),
        *(ROOT / "harness" / "project" / "rules").glob("*.md"),
        *(ROOT / "harness" / "project" / "agents").glob("*.md"),
    ]
)
# Technical Russian teaches Russian style: its quoted examples are Russian by design (#1249).
RUSSIAN_EXAMPLES = {"technical-russian.md"}
CYRILLIC = re.compile(r"[А-Яа-яЁё]")
FENCE = re.compile(r"^(`{3,}|~{3,}).*?^\1\s*$", re.MULTILINE | re.DOTALL)
CODE_SPAN = re.compile(r"`[^`\n]*`")


def _prose(text: str) -> str:
    return CODE_SPAN.sub("", FENCE.sub("", text))


def test_the_instruction_sources_exist() -> None:
    assert len(SOURCES) >= 14


@pytest.mark.parametrize("source", SOURCES, ids=lambda path: path.name)
def test_an_instruction_is_written_in_english(source: Path) -> None:
    text = _prose(source.read_text(encoding="utf-8"))
    if source.name in RUSSIAN_EXAMPLES:
        text = re.sub(r"«[^»]*»", "", text)
    lines = [line for line in text.splitlines() if CYRILLIC.search(line)]

    assert lines == []
