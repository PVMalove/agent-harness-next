"""Контракты инструкций прожарки и поставка связанных ресурсов."""

from pathlib import Path

from harness.bin.harness import package_files

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills" / "first-party" / "engineering"
DRILL_DOWN = "references/drill-down-template.md"


def _skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def _section(skill: str, heading: str) -> str:
    return " ".join(skill.split(f" {heading}\n", 1)[1].split("\n##", 1)[0].split())


def test_declined_discovery_path_stays_out_of_the_handoff() -> None:
    discovery = _section(_skill("grilling"), "Discovery Context")
    assert "separate confirmation" in discovery
    assert "before asking design questions" in discovery
    assert "Only explicitly approved paths" in discovery
    assert "exclude declined paths" in discovery
    assert "line for line" in _section(_skill("grilling"), "Close the session")


def test_stopping_preserves_unresolved_dependencies() -> None:
    skill = _skill("grilling")
    rounds = _section(skill, "Run the interview")
    for marker in (
        "prerequisites are settled",
        "остановимся",
        "углубимся сюда",
        "отложим этот вопрос",
    ):
        assert marker in rounds
    closing = _section(skill, "Close the session")
    assert "Открытые вопросы и блокеры для спецификации" in closing
    assert "partial" in closing
    assert "Never invoke `/to-spec`" in closing


def test_decision_matrix_has_borders_and_room_for_technical_detail() -> None:
    protocol = _section(_skill("grilling"), "Decision & Clarity Protocol")
    assert "fenced `text` block with box-drawing borders" in protocol
    assert (
        "a full-width header and separate rows for Mechanism, Benefit, and Cost"
        in protocol
    )
    assert "which components or contracts change" in protocol
    assert (
        "Wrap paragraphs across lines and keep technical detail and identifiers intact"
        in protocol
    )


def test_drill_down_stays_read_only_and_returns_to_the_same_choice() -> None:
    skill = _skill("grilling")
    assert 60 <= len(skill.splitlines()) <= 90
    protocol = _section(skill, "Decision & Clarity Protocol")
    for choice in (
        "[1] Рекомендуемое (Recommended)",
        "[2] Компромиссное (Fast-Track)",
        "[3] Полное (Full / Clean Architecture)",
    ):
        assert choice in protocol
    assert "fewer than three" in protocol
    assert f"Read {DRILL_DOWN} ONLY when" in protocol
    assert "подробнее <N>" in protocol
    assert "show the same choice again" in protocol
    assert "no file writes" in protocol.lower()
    template = (SKILLS / "grilling" / DRILL_DOWN).read_text(encoding="utf-8")
    assert [line for line in template.splitlines() if line.startswith("## ")] == [
        "## Affected files and modules",
        "## Data flow and contracts",
        "## Verification plan",
        "## Risks and edge cases",
    ]


def test_to_spec_copies_the_approved_list_and_handles_an_unavailable_artifact() -> None:
    draft = _section(
        _skill("to-spec"), "Phase 2: Drafting & Publishing (After User Approval)"
    )
    assert "same folder's `artifacts/discovery-context.md`" in draft
    assert "could not be written or verified" in draft
    assert "from the final summary in chat" in draft
    assert "Preserve the approved lines verbatim, in order" in draft
    assert "## Relevant Files (Discovery Context)" in draft
    assert "Never rediscover paths" in draft


def test_wrappers_and_reference_are_delivered_by_the_engineering_suite() -> None:
    files = package_files(["engineering-suite"])
    for name in ("grill-me", "grill-with-docs", "grilling", "to-spec"):
        for filename in ("SKILL.md", "agents/openai.yaml"):
            source = SKILLS / name / filename
            assert files[f".harness/skills/{name}/{filename}"] == source.read_bytes()
    assert (
        files[f".harness/skills/grilling/{DRILL_DOWN}"]
        == (SKILLS / "grilling" / DRILL_DOWN).read_bytes()
    )


def test_glossary_and_adr_writes_have_separate_approval() -> None:
    interview_only = _skill("grill-me")
    assert "without editing CONTEXT.md or ADRs" in interview_only
    docs = " ".join(_skill("grill-with-docs").split())
    assert (
        "Confirm the term, its definition, and its owning context with the user before writing"
        in docs
    )
    assert (
        "Create a missing glossary only for the first explicitly approved term" in docs
    )
    assert "read-only file" in docs
    assert "staged, unstaged, or untracked edits from outside this session" in docs
    assert (
        "hard to reverse, the rationale is not obvious, and the user chose between genuine alternatives"
        in docs
    )
    assert "explicit approval to create the ADR" in docs


def test_to_spec_does_not_stage_unrelated_glossary_edits() -> None:
    text = " ".join(_skill("to-spec").split())
    assert "exclude any with unrelated changes" in text
    assert (
        "If it already contains changes outside the approved set, leave it intact"
        in text
    )
