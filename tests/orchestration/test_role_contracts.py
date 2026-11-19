"""Тексты ролей оркестрации согласованы с кодом и навыками (#1216)."""

from pathlib import Path

from harness.orchestration.core.constants import (
    NEXT_ACTION_DISPATCH_ROLE,
    REPORT_FIELDS,
)
from harness.orchestration.runtime_attestation import (
    WORKER_ROLES_REQUIRING_ISSUE_WORKTREE,
)

ROOT = Path(__file__).resolve().parents[2]
ROLES = ROOT / "harness/orchestration/roles"
REFERENCES = ROLES / "references"
SKILLS = ROOT / "skills/first-party/engineering"
AGENTS = ROOT / "harness/project/agents"


def _text(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def _role(name: str) -> str:
    return _text(ROLES / f"{name}.md")


def test_qa_role_is_the_qa_run_lane_without_a_model_worker() -> None:
    qa = _role("qa")
    assert "`qa run`" in qa
    assert "related_tests" not in qa
    assert "incomplete_items" not in qa


def test_specialist_roles_without_a_route_say_so() -> None:
    for name in ("database-migrations", "messaging-integration"):
        assert name not in NEXT_ACTION_DISPATCH_ROLE.values()
        assert "no dispatch route" in _role(name)
        assert "#1159" in _role(name)
    assert "belong to their respective roles" not in _role("developer")


def test_common_contract_names_every_attested_role_once() -> None:
    common = _role("common")
    sentence = common[common.index("Worktree attestation is mandatory for") :].split(
        ";"
    )[0]
    for name in WORKER_ROLES_REQUIRING_ISSUE_WORKTREE:
        assert f"`{name}`" in sentence
    assert common.count("dispatch self-report") == 1


def test_common_contract_lists_every_required_report_field() -> None:
    common = _role("common")
    for field in REPORT_FIELDS:
        assert f"`{field}`" in common
    assert "`not applicable — read-only role`" in common


def test_roles_call_the_brief_list_definition_of_done() -> None:
    for name in ("common", "developer", "architect"):
        text = _role(name)
        assert "acceptance criteria" not in text
        assert "`definition_of_done`" in text


def test_architect_writes_the_decision_into_output() -> None:
    architect = _role("architect")
    assert "`accepted_design.output`" in architect
    assert "does not repeat its narrative" not in architect
    assert "Under `approval_policy: auto`" in architect


def test_uncommitted_files_live_inside_the_tooling_blocker() -> None:
    assert "inside that `tooling_blocker` object" in _role("developer")
    assert "exactly three non-empty strings" not in _role("common")


DEVELOPER_REFERENCES = {
    "developer-test-author": "preflight",
    "developer-retry": "`developer-retry`",
    "developer-carried-items": "`carried_items`",
    "developer-rerun-failed-tests": "`scripts/verify.py`",
}


def test_developer_core_is_compact_and_names_each_reference_with_its_condition() -> (
    None
):
    core = _role("developer")
    assert len(core.split()) <= 900
    for name, condition in DEVELOPER_REFERENCES.items():
        assert f"`references/{name}.md`" in core
        assert condition in _text(REFERENCES / f"{name}.md")
    assert "scripts/verify.py --worktree-cache" not in core
    assert "/fast-implement" not in core
    assert "`risk_triggers`" in core


def test_developer_texts_cite_no_repository_adr_and_one_preflight() -> None:
    texts = [_role("developer")] + [
        _text(REFERENCES / f"{name}.md") for name in DEVELOPER_REFERENCES
    ]
    for text in texts:
        assert "ADR 00" not in text
    author = _text(REFERENCES / "developer-test-author.md")
    assert "tdd/references/test-author.md" in author
    assert author.count("test_author.py preflight") == 1
    assert (
        "Run `<brief worker_worktree>/.claude/hooks/test-author-preflight.sh"
        not in author
    )
    rerun = _text(REFERENCES / "developer-rerun-failed-tests.md")
    assert (
        rerun.startswith("# ")
        and "only when the project has `scripts/verify.py`" in rerun
    )


def test_code_review_role_names_its_sources_and_the_real_wrapper() -> None:
    review = _role("code-review")
    for source in (
        "`definition_of_done`",
        "`prohibited_changes`",
        "`allowed_paths`",
        "smell-baseline.md",
    ):
        assert source in review
    assert "python .harness/skills/qa-gate" not in review
    assert "<harness-root>" in review and "`shell`" in review
    assert "so the coordinator can record `override-warning`" not in review
    assert "`references/code-review-delta.md`" in review
    assert "`delta_review_of`" in _text(REFERENCES / "code-review-delta.md")
    assert "## Delta-review" not in (ROLES / "code-review.md").read_text(
        encoding="utf-8"
    )


def test_review_agents_use_ticket_bounds_and_one_smell_rule() -> None:
    spec = _text(AGENTS / "code-review-spec.md")
    assert (
        "`## Out of scope`" in spec and "`## Non-Goals & Rejected Alternatives`" in spec
    )
    rule = "documented repo standard"
    owners = [
        path
        for path in (
            AGENTS / "code-review-standards.md",
            SKILLS / "code-review/SKILL.md",
            SKILLS / "code-review/references/smell-baseline.md",
        )
        if rule in _text(path)
    ]
    assert owners == [SKILLS / "code-review/references/smell-baseline.md"]


def test_code_review_skill_has_no_dangling_section_and_full_delta_rule() -> None:
    assert "_Runtime boundary_" not in _text(SKILLS / "code-review/SKILL.md")
    assert "Spec Warning or Blocker" in _text(
        SKILLS / "code-review/references/gated-route.md"
    )


def test_backend_orchestration_ships_the_role_references() -> None:
    from harness.bin.harness import package_files

    files = package_files(["backend-orchestration"])
    for path in sorted(REFERENCES.glob("*.md")):
        relative = f".harness/orchestration/roles/references/{path.name}"
        assert files[relative] == path.read_bytes()


def test_no_report_hands_an_item_to_qa() -> None:
    """#1234: qa run has no worker that could finish an item, so no report may target it."""
    import pytest

    from harness.orchestration.core.constants import INCOMPLETE_ITEM_TARGET_ROLES
    from harness.orchestration.core.utils import CoordinatorError
    from harness.orchestration.workflow import reports

    assert "qa" not in INCOMPLETE_ITEM_TARGET_ROLES
    assert all("qa" not in targets for targets in INCOMPLETE_ITEM_TARGET_ROLES.values())
    report = {
        "role": "code-review",
        "incomplete_items": [
            {"brief_item": "Run the e2e suite", "reason": "No browser", "target_role": "qa"}
        ],
    }
    with pytest.raises(CoordinatorError, match="target_role 'qa'"):
        reports._validate_incomplete_items(report, {"mode": "read-only"})
    for name in ("architect", "code-review", "verification", "common"):
        assert "or `qa`" not in _role(name)
        assert "`code-review`, `qa`" not in _role(name)


def test_placeholder_risk_triggers_are_gone() -> None:
    for name in ("qa", "verification", "rebaser", "conflict-resolver"):
        assert "risk_triggers:" not in (ROLES / f"{name}.md").read_text(encoding="utf-8")
