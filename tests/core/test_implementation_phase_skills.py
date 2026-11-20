"""Контракт навыков фазы реализации: вход из /to-tickets, гейты, ссылки и поставка (#1210)."""

import re
from pathlib import Path

import pytest

from harness.bin.harness import package_files, seed_template_files
from scripts.clean_room.install_and_update import check_workflow_procedures
from tests.core.test_developer_skill import _frontmatter, _section

ROOT = Path(__file__).resolve().parents[2]
ENGINEERING = ROOT / "skills/first-party/engineering"
TICKET_SCOPE = (
    "`## Relevant Files (Discovery Context)`",
    "`## Contract touchpoints`",
    "`## Out of scope`",
)


def _skill(name: str) -> Path:
    return ENGINEERING / name / "SKILL.md"


def _text(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


@pytest.mark.parametrize(
    "name",
    ["fast-implement", "to-guide", "architect", "to-pull-requests", "setup-labels"],
)
def test_explicit_skills_need_an_explicit_codex_call(name: str) -> None:
    assert _frontmatter(_skill(name))["disable-model-invocation"] == "true"
    metadata = (ENGINEERING / name / "agents/openai.yaml").read_text(encoding="utf-8")
    assert "allow_implicit_invocation: false" in metadata
    assert f'default_prompt: "Use ${name} ' in metadata


@pytest.mark.parametrize("name", ["fast-implement", "to-guide", "code-review"])
def test_reworked_cores_stay_compact(name: str) -> None:
    assert len(_skill(name).read_text(encoding="utf-8").splitlines()) <= 90


@pytest.mark.parametrize("name", ["fast-implement", "developer", "to-guide"])
def test_ticket_scope_sections_bound_the_change(name: str) -> None:
    text = _text(_skill(name))
    for section in TICKET_SCOPE:
        assert section in text


def test_fast_implement_reads_the_ticket_and_leaves_the_full_suite_to_qa_gate() -> None:
    preflight = _section(_skill("fast-implement"), "Pre-flight")
    assert "`**Integration branch:**` line on the local tracker" in preflight
    assert "`Action -> Verify` criteria are its checks" in preflight
    implement = _section(_skill("fast-implement"), "Implement")
    assert "the full suite runs in `/qa-gate` before the PR" in implement
    assert "full test suite once at the end" not in _text(_skill("fast-implement"))
    resolve = _section(_skill("fast-implement"), "Resolve the ticket")
    assert "`/to-spec`, `/publish-epic` and `/to-tickets`" in resolve
    assert "lowest execution wave" in resolve


def test_developer_runs_every_verify_command() -> None:
    completion = _section(_skill("developer"), "Completion")
    assert "its `Verify` command" in completion


def test_implement_maps_the_ticket_and_never_loops_back() -> None:
    text = _text(_skill("implement"))
    assert "each `## Acceptance criteria` item → `--definition-of-done`" in text
    assert "each `## Out of scope` item → `--prohibited-change`" in text
    assert "For a `pipeline::full` ticket, say that this route needs" in text
    assert "`**Integration branch:**` line on the local tracker" in text


def test_to_guide_uses_the_current_spec_template() -> None:
    template = ENGINEERING / "to-guide/references/guide-template.md"
    assert "Read `references/guide-template.md`" in _text(_skill("to-guide"))
    assert "Testing Decisions" not in template.read_text(encoding="utf-8")
    assert "`## Acceptance & Verification Criteria`" in _text(template)


def test_code_review_spec_axis_reads_the_parent_epic() -> None:
    text = _text(_skill("code-review"))
    assert "When the ticket names `## Parent: #<epic>`, also fetch the epic" in text
    assert "`## Non-Goals & Rejected Alternatives`" in text
    assert "Read `references/smell-baseline.md`" in text
    smells = (ENGINEERING / "code-review/references/smell-baseline.md").read_text(
        encoding="utf-8"
    )
    assert "**Feature Envy**" in smells and "**Refused Bequest**" in smells


def test_architect_keeps_settled_decisions_settled() -> None:
    frame = _section(_skill("architect"), "1. Frame the decision")
    assert "treat its `## Architecture & Selected Approach` as settled" in frame
    assert "reopen one only with new evidence" in frame


def test_engineering_suite_ships_the_new_references() -> None:
    files = package_files(["engineering-suite"])
    for relative in (
        "tdd/references/test-author.md",
        "to-guide/references/guide-template.md",
        "to-guide/agents/openai.yaml",
        "code-review/references/smell-baseline.md",
        "code-review/references/gated-route.md",
        "to-pull-requests/agents/openai.yaml",
    ):
        assert (
            files[f".harness/skills/{relative}"]
            == (ENGINEERING / relative).read_bytes()
        )


IMPLEMENT_REFERENCES = (
    "auto-path",
    "claude-code-runtime",
    "commit-plan",
    "issue-worktree",
    "recovery",
    "test-author",
    "workers",
)


def test_issue_worktree_procedure_lives_in_the_implement_reference() -> None:
    reference = _text(ENGINEERING / "implement/references/issue-worktree.md")
    for marker in (
        "coordinator.py worktree create --repo .",
        "harness worktree-venv",
        "**Session write access.**",
        "**Recovery after a partial failure.**",
        "`.harness/instructions/git-workflow.md`",
    ):
        assert marker in reference, marker
    core = _text(_skill("implement"))
    assert "`.harness/instructions/worktrees.md` → Coordinator issue worktree" not in core
    assert "`.harness/instructions/worktrees.md` → Session write access" not in core


def test_implement_core_names_each_reference_with_its_condition() -> None:
    """#1211: conditional procedures live in references/, each named once in the core."""
    core = _text(_skill("implement"))
    for name in IMPLEMENT_REFERENCES:
        assert f"`references/{name}.md`" in core
    assert "## Phase 1:" not in core
    headings = [
        line
        for line in _skill("implement").read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]
    assert headings.index("## Coordinator contract") < headings.index(
        "## Batch preparation"
    )
    metadata = (ENGINEERING / "implement/agents/openai.yaml").read_text(
        encoding="utf-8"
    )
    assert 'default_prompt: "Use $implement ' in metadata


def test_moved_procedures_keep_their_rules() -> None:
    references = ENGINEERING / "implement/references"
    recovery = _text(references / "recovery.md")
    assert "batch abandon" in recovery and "tooling-retry" in recovery
    assert "accept-conditional --infrastructure-failure" in recovery
    assert "batch auto-decide" in _text(references / "auto-path.md")
    assert "ledger release-lock" in _text(references / "workers.md")
    assert "`commit_plan`" in _text(references / "commit-plan.md")
    assert "in-process" in _text(references / "claude-code-runtime.md")


def test_engineering_suite_ships_the_implement_references() -> None:
    files = package_files(["engineering-suite"])
    for name in IMPLEMENT_REFERENCES:
        relative = f"implement/references/{name}.md"
        assert (
            files[f".harness/skills/{relative}"]
            == (ENGINEERING / relative).read_bytes()
        )


TRACKER_COPIES = (
    "--add-label status::in-progress",
    "--label status::in-progress",
    "--add-assignee @me",
    "--assignee @me",
    "gh issue close",
    "glab issue close",
    "defaultBranchRef",
)


@pytest.mark.parametrize("name", ["fast-implement", "to-guide", "implement"])
def test_skills_reference_the_tracker_contract_instead_of_copying_it(name: str) -> None:
    """#1162: status swap and claim commands live in .harness/instructions/issue-tracker.md."""
    text = _text(_skill(name))
    copied = [marker for marker in TRACKER_COPIES if marker in text]
    assert not copied, copied
    if name != "implement":
        assert "`.harness/instructions/issue-tracker.md` → Replace the status label" in text
        assert "`.harness/instructions/issue-tracker.md` → Wayfinding operations → Claim" in text


def test_skills_name_no_worktree_commands_outside_the_reference() -> None:
    for name in ("fast-implement", "to-guide", "implement", "to-pull-requests"):
        assert "worktree create --repo" not in _text(_skill(name)), name
    preflight = _section(_skill("fast-implement"), "Pre-flight")
    assert "`.harness/instructions/git-workflow.md` §2 steps 1–2" in preflight


INSTALLED_PATH = re.compile(r"`((?:docs/agents|\.harness)/[A-Za-z0-9_./-]+\.(?:md|py|json|sh))`")


def test_named_installed_paths_are_delivered() -> None:
    """Every .harness/instructions/*.md or .harness/... path these skills name ships with the install."""
    shipped = set(package_files(["backend-orchestration"]))
    shipped |= set(seed_template_files(ROOT, orchestration_enabled=True))
    shipped.add(".harness/project.json")  # written by `harness init`, not a template
    sources = [
        path
        for name in ("fast-implement", "to-guide", "implement", "to-pull-requests", "tdd")
        for path in (ENGINEERING / name).rglob("*.md")
    ]
    missing = {
        f"{source.relative_to(ENGINEERING)}: {match}"
        for source in sources
        for match in INSTALLED_PATH.findall(source.read_text(encoding="utf-8"))
        if "<" not in match and match not in shipped
    }
    assert not missing, sorted(missing)


def test_clean_room_checks_the_procedure_routes(tmp_path: Path) -> None:
    """Fresh install and update keep the Claude Code and Codex procedure routes (#1162)."""
    check_workflow_procedures(tmp_path)
