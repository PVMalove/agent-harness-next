"""Пути репозитория, общие для проверок."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTRUCTION_TEMPLATES = ROOT / "harness" / "project" / "instructions"
# Instructions the CLI installs as managed files with their capability, not as seed guides.
MANAGED_INSTRUCTIONS = frozenset({"project-memory.md", "container-executor.md"})
CAPABILITIES = ROOT / "harness" / "CAPABILITIES.json"
SITE_DOCS = ROOT / "site" / "docs"
SITE_REFERENCE_SKILLS = ROOT / "site" / "docs" / "reference" / "skills.md"
SITE_PROJECT_STRUCTURE = ROOT / "site" / "docs" / "project" / "structure.md"
