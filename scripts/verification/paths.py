"""Пути репозитория, общие для проверок."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS_AGENTS_TEMPLATE = ROOT / "harness" / "project" / "instructions"
# Instructions the CLI installs as managed `.harness/instructions/` files, not into `docs/agents/`.
MANAGED_INSTRUCTIONS = frozenset(
    {"technical-english.md", "project-memory.md", "container-executor.md"}
)
CAPABILITIES = ROOT / "harness" / "CAPABILITIES.json"
SITE_DOCS = ROOT / "site" / "docs"
SITE_REFERENCE_SKILLS = ROOT / "site" / "docs" / "reference" / "skills.md"
SITE_PROJECT_STRUCTURE = ROOT / "site" / "docs" / "project" / "structure.md"
