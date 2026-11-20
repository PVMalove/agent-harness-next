"""Маршруты и настройка из аудита фазы 5 доходят до скилов, которые их потребляют."""

import re
from pathlib import Path

import pytest

from harness.health.labels_table import parse_canonical_labels
from tests.core.test_developer_skill import _harness

ROOT = Path(__file__).resolve().parents[2]
ENGINEERING = ROOT / "skills/first-party/engineering"
START_PROJECT = ROOT / "global-skills/start-project"
LABELS = (
    "harness/project/instructions/triage-labels.md",
    "docs/agents/triage-labels.md",
)
TYPE_LABELS = (
    "type::bug",
    "type::feature",
    "type::refactoring",
    "type::chore",
    "type::security",
    "type::performance",
    "type::hotfix",
)
MODEL_INVOKED_BUDGET = 1445
DIAGNOSING_BUGS_LIMIT = 176


def _text(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def _description(path: Path) -> str:
    frontmatter = path.read_text(encoding="utf-8").split("---")[1]
    match = re.search(r"^description: (.*)$", frontmatter, re.MULTILINE)
    assert match, path
    return match.group(1).strip().strip('"')


@pytest.mark.parametrize("relative", LABELS)
def test_setup_labels_has_a_colour_for_every_type_and_route(relative: str) -> None:
    labels = dict(parse_canonical_labels((ROOT / relative).read_text(encoding="utf-8")))
    for label in (*TYPE_LABELS, "pipeline::fast", "pipeline::full"):
        assert re.fullmatch(r"#[0-9a-f]{6}", labels.get(label, "")), label


def test_setup_labels_reads_the_type_and_pipeline_tables() -> None:
    text = _text(ENGINEERING / "setup-labels/SKILL.md")
    assert "the type, execution mode, status and context-label tables" in text
    assert "the pipeline hint (`pipeline::*`)" in text
    assert "Skip a table without a `Color` column" in text


def test_triage_agrees_the_route_of_an_afk_ticket() -> None:
    text = _text(ENGINEERING / "triage/SKILL.md")
    assert "for `afk`, the route (`pipeline::fast`" in text
    assert "`status::ready` + `afk` + the agreed `pipeline::*`" in text
    assert "Triage computes no story points." in text
    labels = _text(ROOT / LABELS[0])
    assert "`/triage` is the second source" in labels


def test_ask_matt_routes_through_the_harness_setup() -> None:
    text = _text(ENGINEERING / "ask-matt/SKILL.md")
    assert "**`harness update`** seeds `docs/agents/`" in text
    assert "run **`/setup-labels`** once" in text
    assert "Don't run `/setup-matt-pocock-skills` here" in text
    assert "(`hitl`) → **`/to-guide`**" in text
    assert "(needs the `backend-orchestration` capability)" in text
    for skill in ("/architect", "/developer", "/qa-gate", "/delivery-stats"):
        assert f"- **`{skill}`** —" in text, skill
    assert "**`/fast-implement`** for `pipeline::fast`" in text


def test_wayfinder_hands_the_cleared_map_to_to_spec() -> None:
    text = _text(ENGINEERING / "wayfinder/SKILL.md")
    assert (
        "run `/to-spec` with the map as its input, then `/publish-epic` and `/to-tickets`"
        in text
    )


def test_start_project_offers_every_capability() -> None:
    text = _text(START_PROJECT / "SKILL.md")
    for capability in (
        "project-foundation",
        "mattpocock-suite",
        "engineering-suite",
        "backend-orchestration",
    ):
        assert f"- `{capability}`" in text, capability
    assert (
        "For `engineering-suite` and `backend-orchestration`, install `hook_policy`"
        in text
    )
    assert "that action is `/setup-labels`" in text
    assert (
        "For `engineering-suite` or `backend-orchestration`, read "
        "[references/engineering-setup.md](references/engineering-setup.md)" in text
    )


def test_start_project_names_only_real_init_flags() -> None:
    help_text = _harness("init", "--help").stdout
    sources = (
        START_PROJECT / "SKILL.md",
        START_PROJECT / "references/engineering-setup.md",
    )
    flags = {
        flag
        for path in sources
        for flag in re.findall(r"`(--[a-z-]+)", path.read_text())
    }
    init_flags = {
        "--language",
        "--pr-base-branch",
        "--branch-pattern",
        "--qa-gate-command",
        "--tracker-type",
        "--tracker-host",
        "--tracker-project",
        "--test-path",
        "--no-model-invocation",
    }
    assert init_flags <= flags
    for flag in init_flags:
        assert flag in help_text, flag


def test_engineering_setup_names_only_real_subcommands() -> None:
    help_text = _harness("--help").stdout
    text = (START_PROJECT / "references/engineering-setup.md").read_text(
        encoding="utf-8"
    )
    commands = set(re.findall(r"`harness ([a-z-]+)", text))
    assert {
        "presets",
        "catalogs",
        "runtime-events",
        "inventory",
        "workflow-overlays",
    } <= commands
    for command in commands:
        assert command in help_text, command
    for term in ("pr_checklist", "pre_qa_commands", "harness-runtime init"):
        assert term in text, term


def test_global_skills_carry_no_inline_translation() -> None:
    for path in (ROOT / "global-skills").rglob("*.md"):
        assert "Перевод:" not in path.read_text(encoding="utf-8"), path


def test_model_invoked_descriptions_stay_in_budget() -> None:
    total = 0
    for path in sorted(ENGINEERING.glob("*/SKILL.md")):
        if "disable-model-invocation: true" not in path.read_text(encoding="utf-8"):
            total += len(_description(path))
    assert total <= MODEL_INVOKED_BUDGET
    assert (
        len(_description(ENGINEERING / "diagnosing-bugs/SKILL.md"))
        <= DIAGNOSING_BUGS_LIMIT
    )
