"""The Red-Green-Refactor cycle protocol: its markers stay in the prose and the scenario stays wired."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

import importlib

isolated_test_runner = importlib.import_module(
    "scripts.clean_room.isolated_test_runner"
)
test_author_cycle = importlib.import_module("scripts.clean_room.test_author_cycle")

ROOT = Path(__file__).resolve().parents[2]
DEVELOPER = ROOT / "harness" / "orchestration" / "roles" / "developer.md"
COMMON = ROOT / "harness" / "orchestration" / "roles" / "common.md"
# Since #1216 the role keeps its test-author rules in a conditional reference.
DEVELOPER_AUTHOR = DEVELOPER.parent / "references" / "developer-test-author.md"
AGENT = ROOT / "harness" / "project" / "agents" / "test-author.md"
IMPLEMENT = (
    ROOT
    / "skills"
    / "first-party"
    / "engineering"
    / "implement"
    / "references"
    / "test-author.md"
)
CHANGELOG = ROOT / "CHANGELOG.md"
FAST_IMPLEMENT = (
    ROOT / "skills" / "first-party" / "engineering" / "fast-implement" / "SKILL.md"
)
TDD = ROOT / "skills" / "first-party" / "engineering" / "tdd" / "SKILL.md"
TDD_AUTHOR = TDD.parent / "references" / "test-author.md"
GUIDE = ROOT / "harness" / "project" / "instructions" / "test-author.md"

DEVELOPER_MARKERS = (
    "Red-Green-Refactor",
    "needs_skeleton",
    "contract_gap",
    "never weakened",
    "three consecutive failed author calls",
    "no new dispatch",
    "no ledger state",
    "Not a behavioral Red",
    "immediately",
    "ordinary blocker path",
)
FULL_ROUTE_MARKERS = (
    "test-author-preflight.sh",
    "--worktree",
    "checkout_mismatch",
    "external",
    "agent_tool_unavailable",
    "ordinary TDD",
    "never creates a blocker",
)
# The /implement route has one editable source: the developer role reference.
ROLE_ROUTE = ".harness/orchestration/roles/references/developer-test-author.md"
ROUTE_RESTATEMENT_MARKERS = (
    "checkout_mismatch",
    "agent_tool_unavailable",
    "test_author.py run --repo <worker_worktree>",
    "test_author.py run --repo <send.worker_worktree>",
    "test_author.py preflight --repo <worker_worktree>",
)
FULL_ROUTE_DESCRIPTION_MARKERS = (
    "--worktree",
    "`checkout_mismatch`",
    "`agent_tool_unavailable`",
    "external",
    "обычный TDD",
)
FAST_MARKERS = (
    "Agree the seams before the first test",
    "Neither route adds a coordinator, architect or QA step",
    "../tdd/references/test-author.md",
    "## Test author",
    "Fallback to the usual route.",
    ".harness/instructions/test-author.md",
)
# The short route is owned by the fast-implement skill; the guide keeps a pointer.
FAST_ROUTE = ".harness/skills/fast-implement/SKILL.md"
# One protocol shared by /tdd, /fast-implement and /developer (issue #1210).
AUTHOR_PROTOCOL_MARKERS = (
    "test-author-preflight.sh",
    '{"status":"ok"}',
    "algorithm or implementation snippet",
    "needs_skeleton",
    "contract_gap",
    "never weakened",
    "Not a behavioral Red",
    "Green immediately",
    "three consecutive failed author calls",
    "no dispatch and no ledger state",
)
SHORT_ROUTE_MARKERS = ("/fast-implement", "short route")
AGENT_MARKERS = (
    "`status`",
    "needs_skeleton",
    "contract_gap",
    "failed assertion",
    "already Green",
)
GUIDE_MARKERS = (
    "needs_skeleton",
    "contract_gap",
    "three failed calls",
    "is not weakened",
    "ledger",
    "short `/fast-implement` route",
    "### Opt-in",
    "### Protected environment",
    "bubblewrap 0.9.0+",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("path", "markers"),
    [
        (DEVELOPER_AUTHOR, DEVELOPER_MARKERS),
        (DEVELOPER_AUTHOR, FULL_ROUTE_MARKERS),
        (TDD, SHORT_ROUTE_MARKERS),
        (FAST_IMPLEMENT, FAST_MARKERS),
        (TDD_AUTHOR, AUTHOR_PROTOCOL_MARKERS),
        (TDD_AUTHOR, SHORT_ROUTE_MARKERS),
        (AGENT, AGENT_MARKERS),
        (GUIDE, GUIDE_MARKERS),
    ],
    ids=lambda value: value.parent.name if isinstance(value, Path) else "",
)
def test_protocol_markers(path: Path, markers: tuple[str, ...]) -> None:
    text = " ".join(_text(path).split())
    missing = [marker for marker in markers if marker not in text]
    assert not missing, f"{path.name} lost cycle markers: {missing}"


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start:] if end < 0 else text[start:end]


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            lambda: _section(_text(GUIDE), "## 7. The full `/implement` route"),
            id="guide-section-7",
        ),
        pytest.param(lambda: _text(IMPLEMENT), id="implement-reference"),
        pytest.param(lambda: _text(TDD_AUTHOR), id="tdd-reference"),
    ],
)
def test_full_route_points_to_the_developer_role(text: Callable[[], str]) -> None:
    body = " ".join(text().split())
    assert ROLE_ROUTE in body
    restated = [marker for marker in ROUTE_RESTATEMENT_MARKERS if marker in body]
    assert not restated, f"the /implement route is restated: {restated}"


def test_short_route_section_points_to_the_skill() -> None:
    text = _text(GUIDE)
    short = " ".join(_section(text, "## 6. The short `/fast-implement` route").split())
    assert FAST_ROUTE in short
    assert "Fallback to the usual route" not in short
    configuration = _section(text, "## 2. Configuration")
    for heading in (
        "### Opt-in",
        "### Protected environment",
        "### Supported versions and environments",
    ):
        assert heading in configuration
    assert "see section 6" not in text


def test_changelog_records_the_full_route_worktree_fix() -> None:
    # The release cut moves the entry from Unreleased into the newest release section.
    unreleased = "".join(_text(CHANGELOG).split("\n## [", 3)[1:3])
    assert "#768" in unreleased
    assert "checkout_mismatch" in unreleased


def test_common_contract_points_to_the_cycle() -> None:
    assert "Red-Green-Refactor cycle in `developer.md`" in " ".join(
        _text(COMMON).split()
    )


def test_cycle_scenario_passes_on_a_minimal_project(tmp_path: Path) -> None:
    for package in ("src", "tests"):
        (tmp_path / package).mkdir()
        (tmp_path / package / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / ".harness").mkdir()
    (tmp_path / ".harness" / "project.json").write_text("{}", encoding="utf-8")
    test_author_cycle.verify_cycle(
        tmp_path, isolated_test_runner._direct_execute(tmp_path)
    )
    assert not list((tmp_path / "src").glob("cyc_*.py"))
    assert not list((tmp_path / "tests").glob("cyc_*.py"))


def test_cycle_scenario_limit_matches_the_protocol() -> None:
    assert test_author_cycle.MAX_FAILED_CALLS == 3
