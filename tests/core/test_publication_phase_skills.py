"""Контракт навыков фазы публикации: релиз, вход из фаз 1–2, повторный вход и очистка (#1214)."""

from pathlib import Path

from harness.bin.harness import package_files
from tests.core.test_developer_skill import _frontmatter, _section

ROOT = Path(__file__).resolve().parents[2]
ENGINEERING = ROOT / "skills/first-party/engineering"
PR_SKILL = ENGINEERING / "to-pull-requests/SKILL.md"
REFERENCES = ENGINEERING / "to-pull-requests/references"
INSTRUCTIONS = ROOT / "harness/project/instructions"


def _text(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def test_pr_core_names_each_reference_and_stays_compact() -> None:
    core = _text(PR_SKILL)
    assert "`references/integration-route.md`" in core
    assert "`references/release.md`" in core
    assert len(core.split()) <= 2300


def test_engineering_suite_ships_the_pr_references() -> None:
    files = package_files(["engineering-suite"])
    for name in ("integration-route", "release"):
        relative = f"to-pull-requests/references/{name}.md"
        assert files[f".harness/skills/{relative}"] == (ENGINEERING / relative).read_bytes()


def test_release_mode_closes_the_epic_and_leaves_the_changelog_alone() -> None:
    assert "`--release <epic>`" in _frontmatter(PR_SKILL)["description"]
    release = _text(REFERENCES / "release.md")
    for rule in (
        "sub_issues",
        "every child ticket is closed",
        "`Closes #<epic>`",
        "separate confirmation",
        "Never merge it",
        "`/delivery-stats <epic>`",
        "never edits `CHANGELOG.md` or the project version",
    ):
        assert rule in release


def test_release_verifies_every_epic_criterion_on_the_release_candidate() -> None:
    release = REFERENCES / "release.md"
    verify = _section(release, "3. Verify the integration branch")
    assert (
        "Record the full `HEAD` SHA as the release candidate before running checks"
        in verify
    )
    assert "For each row of `## Acceptance & Verification Criteria`" in verify
    assert "the exact check" in verify
    assert "evidence for that criterion on the release candidate" in verify
    assert "run the spec's check on that SHA" in verify
    assert "including scenarios that span several tickets" in verify
    assert "a closed ticket or a merged child PR" in verify
    assert "`resolution::wontfix`" in verify
    assert "stop before requesting release confirmation" in verify
    body = _section(release, "4. Prepare the body")
    assert "the results by epic criterion and the release candidate SHA" in body
    assert "list unverified criteria" in body


def test_release_acceptance_supports_legacy_tickets_and_the_local_tracker() -> None:
    release = REFERENCES / "release.md"
    verify = _section(release, "3. Verify the integration branch")
    assert "For older tickets without IDs, match the observable scenario" in verify
    assert (
        "If the epic has no structured criteria, record epic acceptance as unverified"
        in verify
    )
    local = _section(release, "Local markdown tracker")
    assert "`.scratch/<feature>/spec.md`" in local
    assert "show the criterion results before asking for confirmation" in local


def test_release_confirmation_only_covers_the_tested_sha() -> None:
    confirm = _section(REFERENCES / "release.md", "5. Confirm and open")
    assert (
        "recheck that both the local and remote integration refs match the release candidate SHA"
        in confirm
    )
    assert "repeat verification and request fresh confirmation" in confirm
    assert confirm.index("recheck that both") < confirm.index("gh pr create")


def test_git_workflow_names_the_release_step_and_runs_qa_before_confirmation() -> None:
    text = _text(INSTRUCTIONS / "git-workflow.md")
    assert "**Release (integration → base_branch):**" in text
    assert "`/to-pull-requests --release <epic>`" in text
    assert text.index("run the `qa-gate` skill") < text.index("**Confirm before opening:**")


def test_pr_metadata_follows_the_git_workflow_rule() -> None:
    core = _text(PR_SKILL)
    assert '§1 "Project-Only Metadata"' in core
    assert "model names or `Co-Authored-By`" not in core


def test_step_zero_resumes_from_the_pr_state() -> None:
    core = _text(PR_SKILL)
    assert "gh pr list --head <branch> --state all" in core
    assert "--source-branch <branch>" in core
    assert "Merged: run the merge checks of step 7" in core


def test_pr_body_reads_the_ticket_and_the_verification_evidence() -> None:
    core = _text(PR_SKILL)
    composer = _text(ROOT / "harness/project/agents/pr-composer.md")
    for text in (core, composer):
        assert "`Action -> Verify`" in text
        assert "`Out of scope`" in text
        assert "`handoff`" in text
    assert "if no qa-gate was run this session, say so plainly" not in composer


def test_completion_report_has_one_source_in_the_memory_format() -> None:
    assert "`## Completion report` format of `.harness/instructions/project-memory.md`" in _text(PR_SKILL)
    guide = _text(ENGINEERING / "to-guide/references/guide-template.md")
    assert "`/to-pull-requests` step 6" in guide
    assert "gh issue comment" not in guide


def test_guide_hands_the_pr_and_the_closure_to_to_pull_requests() -> None:
    """The hitl guide routes the PR/MR and the ticket closure through `/to-pull-requests`."""
    guide = _text(ENGINEERING / "to-guide/references/guide-template.md")
    assert "Run `/to-pull-requests <ID>` from the issue branch" in guide
    for copy in ("gh pr create", "glab mr create", "pr_body/"):
        assert copy not in guide, copy


TICKET_PR_GITHUB = (
    "`gh pr create --base <target-branch> --title '<title>' "
    "--label pr::ticket --label <type-label> --body-file <path>`"
)
TICKET_PR_GITLAB = (
    "`glab mr create -R <project-url> --target-branch <target-branch> --title '<title>' "
    "--label 'pr::ticket,<type-label>' --description-file <path> --yes`"
)


def _step(path: Path, number: int) -> str:
    """Нормализованный текст нумерованного шага верхнего уровня до следующего шага."""
    text = path.read_text(encoding="utf-8")
    start = text.index(f"\n{number}. ")
    end = text.find(f"\n{number + 1}. ", start)
    return " ".join(text[start : end if end != -1 else None].split())


def test_ticket_pr_carries_pr_ticket_and_the_ticket_type() -> None:
    """Both PR creation forms label a ticket PR with `pr::ticket` and the ticket's `type::*`."""
    for path in (PR_SKILL, INSTRUCTIONS / "git-workflow.md"):
        step = _step(path, 6)
        assert TICKET_PR_GITHUB in step, path.name
        assert TICKET_PR_GITLAB in step, path.name


def test_ticket_pr_type_label_is_read_from_the_ticket_or_asked() -> None:
    """The type label comes from the ticket; a missing or ambiguous one stops the skill."""
    resolve = _step(PR_SKILL, 1)
    assert "`<type-label>` is the ticket's one `type::*` label" in resolve
    assert "If the ticket has no `type::*` label or more than one" in resolve
    assert "stop and ask the developer which type to use; never infer it" in resolve
    guide = _step(INSTRUCTIONS / "git-workflow.md", 6)
    assert "If the ticket has no `type::*` label or more than one" in guide
    assert "The agent must not infer the type from the title or the diff" in guide


def test_epic_less_ticket_pr_also_gets_pr_ticket() -> None:
    """A ticket PR into `base_branch` is labeled like one into `integration/*`."""
    for path in (PR_SKILL, INSTRUCTIONS / "git-workflow.md"):
        assert (
            "`pr::ticket` labels every ticket PR, whether it targets `integration/*` "
            "or, for an epic-less ticket, `base_branch`"
        ) in _step(path, 6), path.name


def test_guide_names_the_pr_labels() -> None:
    """The hitl guide says which labels `/to-pull-requests` puts on the ticket PR."""
    guide = _text(ENGINEERING / "to-guide/references/guide-template.md")
    assert "labels it `pr::ticket` and the ticket's `type::*`" in guide


def test_unblocking_and_cleanup_follow_the_tracker_and_worktree_contracts() -> None:
    core = _text(PR_SKILL)
    assert "`docs/tasks/*.md`" not in core
    assert "worktree remove --repo . --path <path>" in core
    assert "remove it using `git worktree remove <path>`" not in core
    worktrees = _text(INSTRUCTIONS / "worktrees.md")
    assert "its PR is merged (or the ticket is abandoned)" in worktrees


def test_delivery_stats_states_when_to_call_it() -> None:
    skill = ENGINEERING / "delivery-stats"
    description = _frontmatter(skill / "SKILL.md")["description"]
    assert "Use explicitly after the epic's release PR is merged" in description
    metadata = (skill / "agents/openai.yaml").read_text(encoding="utf-8")
    assert 'default_prompt: "Use $delivery-stats ' in metadata


TICKET_FOOTER = "`.harness/instructions/git-workflow.md` §2 step 6 → Ticket footer"
CLOSE_AFTER_MERGE = "`.harness/instructions/git-workflow.md` §2 step 7 → Close the ticket after merge"


def test_publication_skills_reference_the_footer_and_closure_contract() -> None:
    """#1162: the footer choice and the closure check have one source, git-workflow.md §2."""
    core = _text(PR_SKILL)
    release = _text(REFERENCES / "release.md")
    guide = _text(ENGINEERING / "to-guide/references/guide-template.md")
    for text in (core, release, guide):
        assert TICKET_FOOTER in text
        assert CLOSE_AFTER_MERGE in text
        for copy in ("defaultBranchRef", "gh issue close", "glab issue close"):
            assert copy not in text, copy
    assert "**Check the tree.**" in core
    workflow = _text(INSTRUCTIONS / "git-workflow.md")
    assert "* **Ticket footer:**" in workflow
    assert "* **Close the ticket after merge:**" in workflow


def test_artifacts_procedure_is_its_own_section() -> None:
    text = (INSTRUCTIONS / "artifacts.md").read_text(encoding="utf-8")
    headings = [line for line in text.splitlines() if line.startswith("#")]
    assert headings[0] == "# Artifacts & Scratchpads"
    assert headings.index("## Task artifacts and scratchpads") < headings.index(
        "## Local runtime storage"
    )
    procedure = _section(INSTRUCTIONS / "artifacts.md", "Task artifacts and scratchpads")
    assert "docs/tasks/" in procedure
    assert "harness cleanup" not in procedure
