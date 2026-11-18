"""Контракт инструкций /to-spec и поставка шаблонов."""

from pathlib import Path

import pytest

from harness.bin.harness import package_files
from tests.core.test_developer_skill import _frontmatter, _section

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "skills/first-party/engineering/to-spec"
SKILL = SOURCE / "SKILL.md"
SPEC_TEMPLATE = "references/spec-template.md"
DRILL_DOWN_TEMPLATE = "references/drill-down-template.md"


def test_explicit_invocation_and_lazy_references() -> None:
    fields = _frontmatter(SKILL)
    assert fields["name"] == "to-spec"
    assert fields["disable-model-invocation"] == "true"
    assert "allow_implicit_invocation: false" in (
        SOURCE / "agents/openai.yaml"
    ).read_text(encoding="utf-8")
    text = SKILL.read_text(encoding="utf-8")
    assert 60 <= len(text.splitlines()) <= 90
    assert f"Read `{SPEC_TEMPLATE}` when assembling the specification." in text
    assert (
        f"Read `{DRILL_DOWN_TEMPLATE}` ONLY when the user requests `подробнее <N>` (or `details <N>`)."
        in text
    )
    assert text.count(SPEC_TEMPLATE) == text.count(DRILL_DOWN_TEMPLATE) == 1


def test_handoff_preserves_accepted_options_and_rejected_alternatives() -> None:
    handoff = _section(SKILL, "Load the handoff")
    for marker in (
        "final grilling summary in chat",
        "decision IDs and selected option numbers",
        "rejected alternatives and their reasons",
        "Preserve the approved lines in order",
    ):
        assert marker in handoff
    template = (SOURCE / SPEC_TEMPLATE).read_text(encoding="utf-8")
    assert [line for line in template.splitlines() if line.startswith("## ")] == [
        "## Goal & Scope",
        "## Non-Goals & Rejected Alternatives",
        "## Architecture & Selected Approach",
        "## Surgical File & Contract Changes",
        "## Edge Cases & Failure Modes",
        "## Acceptance & Verification Criteria",
        "## Open Questions & Risks",
        "## Relevant Files (Discovery Context)",
    ]


@pytest.mark.parametrize("artifact_state", ["missing", "empty"])
def test_cold_start_waits_for_path_approval(artifact_state: str) -> None:
    handoff = _section(SKILL, "Load the handoff")
    assert f"{artifact_state} or" in handoff
    paths = _section(SKILL, "Approve evidence paths")
    assert "List candidate paths without reading file contents" in paths
    assert "Wait for explicit approval before reading or citing a candidate" in paths
    assert "Run key unresolved architectural choices through the protocol" in paths


def test_partial_handoff_requires_a_choice_or_an_explicit_draft() -> None:
    protocol = _section(SKILL, "Decision & Clarity Protocol")
    for marker in (
        "architecture or contract blockers from a partial handoff",
        "2–3 sentences",
        "[1] Рекомендуемое (Recommended)",
        "[2] Компромиссное (Fast-Track)",
        "[3] Полное (Full / Clean Architecture)",
        "fewer than three technically distinct options",
        "stop assembling the specification",
        "Wait for an explicit choice or an explicit instruction to save a Draft",
    ):
        assert marker in protocol
    gate = _section(SKILL, "Approve and write the specification")
    assert "Draft — has open blockers" in gate
    assert "explicitly approves writing to the proposed path" in gate
    assert "every functional requirement has a verifiable acceptance criterion" in gate


def test_declined_path_requires_fresh_approval() -> None:
    paths = _section(SKILL, "Approve evidence paths")
    assert "Keep declined paths out of repository reads and the change plan" in paths
    assert "Get fresh approval before using a previously declined path" in paths
    assert "Keep newly approved paths in chat" in paths
    gate = _section(SKILL, "Approve and write the specification")
    assert "every repository file cited in the spec is approved" in gate


def test_details_returns_to_the_same_choice_without_writing() -> None:
    protocol = _section(SKILL, "Decision & Clarity Protocol")
    assert "`все` / `all` expands every displayed option" in protocol
    assert "Reply in chat without writing any files" in protocol
    assert "show the same choices again and wait" in protocol
    completion = _section(SKILL, "Finish")
    assert "return the complete specification in chat" in completion
    assert "Never invoke either skill automatically" in completion


def test_engineering_suite_packages_the_complete_skill() -> None:
    prefix = ".harness/skills/to-spec/"
    files = package_files(["engineering-suite"])
    installed = {
        path.removeprefix(prefix): data
        for path, data in files.items()
        if path.startswith(prefix)
    }
    assert installed == {
        name: (SOURCE / name).read_bytes()
        for name in (
            "SKILL.md",
            "agents/openai.yaml",
            SPEC_TEMPLATE,
            DRILL_DOWN_TEMPLATE,
        )
    }
    registry = (ROOT / "skills/REGISTRY.md").read_text(encoding="utf-8")
    description = _frontmatter(SKILL)["description"]
    assert (
        f"| `to-spec` | `skills/first-party/engineering/to-spec` | {description} |"
        in registry
    )
