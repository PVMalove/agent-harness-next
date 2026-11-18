"""Контракт инструкций /to-tickets и /publish-epic и поставка их ресурсов."""

from pathlib import Path

from harness.bin.harness import package_files
from harness.console.backend.domain.task_board import parse_body
from tests.core.test_developer_skill import _frontmatter, _section

ROOT = Path(__file__).resolve().parents[2]
ENGINEERING = ROOT / "skills/first-party/engineering"
TICKETS = ENGINEERING / "to-tickets"
EPIC = ENGINEERING / "publish-epic"
TEMPLATE = "references/ticket-template.md"
PUBLISH = "references/publish.md"


def _text(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def test_both_skills_need_an_explicit_call_and_load_references_lazily() -> None:
    for source, name in ((TICKETS, "to-tickets"), (EPIC, "publish-epic")):
        fields = _frontmatter(source / "SKILL.md")
        assert fields["name"] == name
        assert fields["disable-model-invocation"] == "true"
        metadata = (source / "agents/openai.yaml").read_text(encoding="utf-8")
        assert "allow_implicit_invocation: false" in metadata
        assert f'default_prompt: "Use ${name} ' in metadata
        assert (
            60
            <= len((source / "SKILL.md").read_text(encoding="utf-8").splitlines())
            <= 90
        )
    skill = (TICKETS / "SKILL.md").read_text(encoding="utf-8")
    assert (
        f"Read {TEMPLATE} when formatting the decomposition plan and ticket cards."
        in skill
    )
    assert f"read `{PUBLISH}` and follow it" in " ".join(skill.split())


def test_a_draft_or_unpublished_epic_blocks_decomposition() -> None:
    check = _section(TICKETS / "SKILL.md", "Check the input")
    assert "exactly `**Status** — Approved`" in check
    assert "`## Open Questions & Risks`" in check
    assert "return to `/to-spec`" in check
    assert "Never settle a blocker yourself" in check
    assert "stop and offer `/publish-epic`" in check
    assert "agree with the user on the missing requirements" in check


def test_non_goals_and_unapproved_paths_stay_out_of_tickets() -> None:
    scope = _section(TICKETS / "SKILL.md", "Keep to the approved scope")
    assert "`## Relevant Files (Discovery Context)`" in scope
    assert "`## Surgical File & Contract Changes`" in scope
    assert "never widen the allowlist from that file" in scope
    assert "only after the user explicitly approves it" in scope
    assert (
        "Never create a ticket for an item in `## Non-Goals & Rejected Alternatives`"
        in scope
    )
    template = _text(TICKETS / TEMPLATE)
    assert "as a new path that needs the user's approval" in template


def test_plan_is_traced_acyclic_and_approved_before_any_write() -> None:
    skill = TICKETS / "SKILL.md"
    approve = _section(skill, "Approve the plan")
    assert "every requirement `R<n>` and every acceptance criterion" in approve
    assert "the blocking graph has no cycles" in approve
    assert "no ticket names an unapproved path or implements a non-goal" in approve
    assert "Wait for explicit approval" in approve
    assert "Write nothing until the user approves the plan" in _text(skill)
    decompose = _section(skill, "Decompose")
    assert "minimum number of tickets" in decompose
    assert "vertical slice" in decompose
    assert "File overlap alone is not a blocker" in decompose
    assert "Wave 1 has no blockers" in decompose


def test_tickets_never_start_implementation() -> None:
    finish = _section(TICKETS / "SKILL.md", "Publish and finish")
    assert "leave the complete ticket cards in chat" in finish
    assert (
        "Never invoke either skill, create branches or worktrees, or change code"
        in finish
    )
    assert "never start `/implement`" in _text(TICKETS / "SKILL.md")


def test_ticket_template_keeps_the_board_and_frontier_contracts() -> None:
    template = (TICKETS / TEMPLATE).read_text(encoding="utf-8")
    issue = template.split("## Tracker issue body", 1)[1].split("```markdown", 1)[1]
    issue = issue.split("```", 1)[0]
    headings = [line for line in issue.splitlines() if line.startswith("## ")]
    for required in (
        "## Parent: #<epic>",
        "## Integration Branch",
        "## What to build",
        "## Story Points",
        "## Relevant Files (Discovery Context)",
        "## Acceptance criteria",
        "## Blocked by",
    ):
        assert required in headings
    body = parse_body(
        issue.replace("<exact branch recorded by the parent epic>", "`integration/x`")
    )
    assert body.criteria and body.files and body.blocked_by is not None
    local = template.split("## Local ticket file", 1)[1].split("```markdown", 1)[1]
    for field in (
        "**Workflow:**",
        "**Execution:**",
        "**Story Points:**",
        "**Pipeline:**",
    ):
        assert field in local.split("```", 1)[0]


def test_summary_table_shows_title_and_hours_from_the_project_scale() -> None:
    publish = (TICKETS / PUBLISH).read_text(encoding="utf-8")
    assert (
        "| Ticket | Title | Wave | What to build | Story Points | Estimate, h | Labels |"
        in publish
    )
    estimation = _text(TICKETS / TEMPLATE)
    assert "estimated hours for a person from `story_points.hours`" in estimation
    assert "Show `—` for a `hitl` ticket" in estimation


def test_publish_epic_owns_labels_branch_and_grill_docs() -> None:
    skill = EPIC / "SKILL.md"
    assert "exactly `**Status** — Approved`" in _section(skill, "Check the input")
    plan = _section(skill, "Approve the plan")
    for marker in (
        "wait for explicit approval before any tracker or Git command",
        "`status::specs`",
        "`task-report::required`",
        "Never guess the slug",
        "exclude any path with unrelated changes",
    ):
        assert marker in plan
    branch = _section(skill, "Set up the integration branch")
    assert "If it already contains changes outside the approved grill docs" in branch
    assert "never recreate the epic" in branch
    assert "never `git add -A`" in branch
    assert "Never invoke it" in _section(skill, "Finish")


def test_instructions_name_publish_epic_as_the_epic_owner() -> None:
    workflow = _text(ROOT / "harness/project/instructions/git-workflow.md")
    assert "First, `/publish-epic` may commit" in workflow
    assert "`/publish-epic` publishes the epic" in workflow
    labels = _text(ROOT / "harness/project/instructions/triage-labels.md")
    assert "`/publish-epic` applies `status::specs`" in labels
    assert "`/publish-epic`, `/to-tickets`" in labels
    assert "/publish-epic, /to-tickets" in (
        ROOT / "harness/project/hooks/tracker-issue.py"
    ).read_text(encoding="utf-8")
    assert "`/publish-epic` and then `/to-tickets`" in _text(
        ENGINEERING / "to-spec/SKILL.md"
    )


def test_engineering_suite_packages_both_complete_skills() -> None:
    files = package_files(["engineering-suite"])
    expected = {
        "to-tickets": ("SKILL.md", "agents/openai.yaml", TEMPLATE, PUBLISH),
        "publish-epic": ("SKILL.md", "agents/openai.yaml"),
    }
    registry = (ROOT / "skills/REGISTRY.md").read_text(encoding="utf-8")
    for name, relatives in expected.items():
        prefix = f".harness/skills/{name}/"
        installed = {
            path.removeprefix(prefix): data
            for path, data in files.items()
            if path.startswith(prefix)
        }
        source = ENGINEERING / name
        assert installed == {rel: (source / rel).read_bytes() for rel in relatives}
        description = _frontmatter(source / "SKILL.md")["description"]
        assert (
            f"| `{name}` | `skills/first-party/engineering/{name}` | {description} |"
            in registry
        )
