"""Контракты из Spec Kit доходят до скилов, которые их потребляют (#1237)."""

from pathlib import Path

from tests.core.test_developer_skill import _section

ROOT = Path(__file__).resolve().parents[2]
ENGINEERING = ROOT / "skills/first-party/engineering"


def _text(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def test_to_spec_honours_the_grilling_verdict() -> None:
    handoff = _section(ENGINEERING / "to-spec/SKILL.md", "Load the handoff")
    assert "On a `kill` verdict, stop and report its decisive reason; write no spec." in handoff
    assert "On `needs-clarification`, carry each blocking unknown" in handoff


def test_triage_maps_the_grilling_verdict_to_an_outcome() -> None:
    text = _text(ENGINEERING / "triage/SKILL.md")
    assert "`kill` → Rejected" in text
    assert "`needs-clarification` → `status::blocked`" in text
    assert "`go` → `status::ready` or `status::specs`" in text


def test_spec_axis_reports_a_status_for_every_criterion() -> None:
    agent = _text(ROOT / "harness/project/agents/code-review-spec.md")
    assert "a status (`met`, `missing` or `unverified`) and the evidence" in agent
    assert "`[R<n>]` IDs" in agent
    skill = _text(ENGINEERING / "code-review/SKILL.md")
    assert "The ticket's `## Acceptance criteria` verbatim" in skill


def test_developer_checks_are_listed_by_criterion() -> None:
    evidence = _section(ENGINEERING / "developer/SKILL.md", "Evidence")
    assert "each acceptance criterion with its `[R<n>]` IDs and `Verify` command" in evidence


def test_fast_route_states_that_pre_qa_commands_do_not_apply() -> None:
    for name in ("qa-gate", "fast-implement"):
        text = _text(ENGINEERING / name / "SKILL.md")
        assert "`pre_qa_commands`" in text, name
        assert "`/implement`" in text, name
