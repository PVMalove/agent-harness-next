"""The pure task-board rules: ticket body parsing, the column table, the launch command, the agent
prompt, the batch stages of the ledger and the bounded board payloads."""

from __future__ import annotations

import json
import time
from typing import cast
from dataclasses import dataclass, field

import pytest

from harness.console.backend.domain.task_board import (
    BOARD_BYTES,
    BODY_READ_BYTES,
    CRITERIA_MAX,
    COLUMNS,
    MAX_TICKETS,
    TITLE_BYTES,
    WHAT_BYTES,
    BatchStage,
    BlockerFact,
    PromptTemplate,
    PullRef,
    SpecList,
    SpecTickets,
    TrackerSpec,
    TrackerTicket,
    agent_prompt,
    batch_stages,
    build_board_payload,
    build_specs_payload,
    column,
    launch_command,
    parse_body,
)
from harness.console.kernel.protocol import _wire_cost

HOSTED_BODY = """## Parent: #862

## Integration Branch

The exact branch: `integration/web-console`

## What to build

A read-only snapshot of the board.
Second line.

## Story Points

5

## Relevant Files (Discovery Context)
- `harness/console/backend/domain/` — pure rules
- docs/rfc/web-console-task-board.html - reference
- `README.md`

## Acceptance criteria
- [ ] Specs are listed
- [x] Columns follow the table,
  even for review
1. Numbered criterion

## Blocked by
- Blocked by #882 — needs the shell
- Blocked by #880: mockups
"""

LOCAL_BODY = """# 02 — Second ticket

**What to build:** The local behaviour.
**Blocked by:** 01 — needs the first
**Integration branch:** `integration/local`

## Relevant Files (Discovery Context)
- `harness/x.py` — why

**Category:** type::feature
**Workflow:** status::blocked
**Execution:** afk
**Story Points:** 3
**Pipeline:** pipeline::fast

- [ ] First local criterion
- [x] Second local criterion
"""


def test_parse_body_reads_every_hosted_section() -> None:
    body = parse_body(HOSTED_BODY)

    assert body.what == "A read-only snapshot of the board.\nSecond line."
    assert body.branch == "integration/web-console"
    assert body.story_points == 5
    assert body.criteria == (
        "Specs are listed",
        "Columns follow the table, even for review",
        "Numbered criterion",
    )
    assert body.files == (
        ("harness/console/backend/domain/", "pure rules"),
        ("docs/rfc/web-console-task-board.html", "reference"),
        ("README.md", ""),
    )
    assert body.blocked_by == (
        ("#882", 882, "needs the shell"),
        ("#880", 880, "mockups"),
    )


def test_parse_body_reads_the_local_template_fields() -> None:
    body = parse_body(LOCAL_BODY)

    assert body.what == "The local behaviour."
    assert body.branch == "integration/local"
    assert body.story_points == 3
    assert body.blocked_by == (("01", 1, "needs the first"),)
    assert body.files == (("harness/x.py", "why"),)
    assert body.criteria == ("First local criterion", "Second local criterion")


def test_parse_body_without_sections_is_empty() -> None:
    body = parse_body("just text\n\n### nested heading\n")

    assert body.what == ""
    assert body.criteria == ()
    assert body.files == ()
    assert body.blocked_by == ()
    assert body.branch is None
    assert body.story_points is None


# Hostile ticket bodies that a backtracking section parser reads in seconds to minutes.
PARSE_SECONDS = 1.0


@pytest.mark.parametrize(
    "hostile",
    [
        "## a" + " " * 60000 + "x",
        "## a" + " " * 30000 + "#####" + " " * 30000 + "x",
        "## Blocked by\n- #1" + " " * 60000 + "x",
        "## Blocked by\n- #1" + " " * 60000 + "\u2014x",
        "## Discovery Context\n- a" + " " * 60000 + "x",
        "## Discovery Context\n- a" + " " * 60000 + ":x",
    ],
    ids=["heading", "heading-hashes", "blocked-by", "blocked-by-dash", "files", "files-colon"],
)
def test_parse_body_reads_hostile_whitespace_in_linear_time(hostile: str) -> None:
    started = time.perf_counter()
    parse_body(hostile)

    assert time.perf_counter() - started < PARSE_SECONDS


def test_parse_body_heading_ignores_closing_hashes_and_spaces() -> None:
    body = parse_body("## Blocked by ##  \n- #7 \u2014 waits\n## Story Points\t#\n3\n")

    assert body.blocked_by == (("#7", 7, "waits"),)
    assert body.story_points == 3


def test_parse_body_none_blockers_give_nothing() -> None:
    body = parse_body("## Blocked by\n- None — can start immediately\n")

    assert body.blocked_by == ()


def test_parse_body_gitlab_blocked_by_lines() -> None:
    body = parse_body("## Blocked by\nBlocked by #12 — schema first\nBlocked by #13\n")

    assert body.blocked_by == (("#12", 12, "schema first"), ("#13", 13, ""))


@pytest.mark.parametrize(
    "hostile",
    [
        "x" * 1_000_000,
        "## What to build\n" + "\x00\ud800\r\n" * 300_000,
        "## Acceptance criteria\r\n" + "- [ ] \ud800 crit\r\n" * 5000,
        "## What to build\n### nested\n## Blocked by\n#1 #2 #3\n## ## ##\n",
    ],
)
def test_parse_body_never_raises_and_is_capped(hostile: str) -> None:
    body = parse_body(hostile)

    assert sum(_wire_cost(char) for char in body.what) <= WHAT_BYTES
    assert len(body.criteria) <= CRITERIA_MAX


def _ticket(
    *labels: str,
    closed: bool = False,
    pr: PullRef | None = None,
    body: str = "",
    ref: str = "#1",
    n: int | None = 1,
    blockers: tuple[BlockerFact, ...] = (),
) -> TrackerTicket:
    return TrackerTicket(
        ref=ref,
        n=n,
        title=f"Ticket {ref}",
        url=f"https://example.test/issues/{n}",
        closed=closed,
        labels=labels,
        body=body,
        native_blockers=blockers,
        pr=pr,
    )


PR = PullRef("#958", "https://example.test/pull/958")


def _stage(role: str) -> BatchStage:
    return BatchStage("batch-1", "active", role, "working")


@pytest.mark.parametrize(
    ("ticket", "stage", "expected"),
    [
        (_ticket("status::blocked"), None, "backlog"),
        (_ticket(), None, "backlog"),
        (_ticket("status::specs"), None, "backlog"),
        (_ticket("status::ready"), None, "ready"),
        (_ticket("status::ready", pr=PR), None, "ready"),
        (_ticket("status::in-progress"), _stage("developer"), "progress"),
        (_ticket("status::in-progress"), None, "progress"),
        (_ticket("status::in-progress"), _stage("code-review"), "review"),
        (_ticket("status::in-progress"), _stage("qa"), "review"),
        (_ticket("status::in-progress", pr=PR), None, "review"),
        (_ticket("status::in-progress", closed=True), None, "done"),
        (_ticket("resolution::wontfix", closed=True), None, None),
    ],
)
def test_column_follows_the_table(
    ticket: TrackerTicket, stage: BatchStage | None, expected: str | None
) -> None:
    assert column(ticket, stage) == expected


@pytest.mark.parametrize(
    ("labels", "command"),
    [
        (("afk", "pipeline::fast"), "/fast-implement"),
        (("afk", "pipeline::full"), "/implement"),
        (("afk",), "/implement"),
        (("hitl",), "/to-guide"),
        (("hitl", "pipeline::fast"), "/to-guide"),
        ((), "/implement"),
    ],
)
def test_launch_command_from_labels(labels: tuple[str, ...], command: str) -> None:
    assert launch_command(labels) == command


SPEC = TrackerSpec(
    ref="#862",
    n=862,
    title="Web console",
    url="https://example.test/issues/862",
    body="## Integration Branch\n`integration/web-console`\n",
    tickets_total=3,
    tickets_open=2,
)


def _release_card(**fields: object) -> dict[str, object]:
    card: dict[str, object] = {
        "id": "#814",
        "title": "chore(release): cutover и релиз 2.0.0",
        "url": "https://tracker.example.test/acme/app/issues/814",
        "labels": ["hitl", "status::blocked"],
        "command": "/to-guide",
        "branch": None,
        "what": "Cut over and release.",
        "criteria": ["Release is tagged", "Changelog is final"],
        "files": [
            {"path": "CHANGELOG.md", "why": "release notes"},
            {"path": "harness/VERSION", "why": ""},
        ],
        "blockers": [
            {"id": f"#{n}", "n": n, "why": "", "state": state}
            for n, state in (
                (803, "closed"),
                (806, "open"),
                (812, "closed"),
                (802, "unknown"),
                (799, "closed"),
                (809, "open"),
                (813, "closed"),
                (811, "closed"),
                (795, "closed"),
            )
        ],
    }
    card.update(fields)
    return card


EPIC: dict[str, object] = {"id": "#784", "title": "Harness Next", "branch": None}
TEMPLATE = PromptTemplate(
    invariants="- Target architecture only.\n- One writer per entity.",
    discipline="Read the approved ADR first.",
)


def test_agent_prompt_is_the_planner_prompt_of_a_hitl_ticket() -> None:
    sut = agent_prompt(_release_card(), EPIC, template=TEMPLATE)

    assert sut == "\n".join(
        [
            "/to-guide #814",
            "",
            "REPOSITORY: https://tracker.example.test/acme/app",
            "EPIC: #784 Harness Next",
            "TASK: #814 — chore(release): cutover и релиз 2.0.0",
            "ISSUES: #814, #784",
            "DEPENDENCIES: #803, #806, #812, #802, #799, #809, #813, #811, #795",
            "PIPELINE: hitl → /to-guide",
            "",
            "ARCHITECTURE INVARIANTS (MANDATORY):",
            "- Target architecture only.",
            "- One writer per entity.",
            "",
            "SPECIFIC SCOPE:",
            "Cut over and release.",
            "",
            "CODE DISCOVERY (verify current paths/branches first):",
            "- CHANGELOG.md — release notes",
            "- harness/VERSION",
            "",
            "ACCEPTANCE CRITERIA:",
            "1. Release is tagged",
            "2. Changelog is final",
            "",
            "TESTS / ADVERSARIAL SCENARIOS:",
            "- Release is tagged",
            "- Changelog is final",
            "",
            "IMPLEMENTATION DISCIPLINE:",
            "Read the approved ADR first.",
        ]
    )


def test_agent_prompt_of_an_afk_ticket_without_blockers_lists_its_own_tests() -> None:
    card = _release_card(
        labels=["afk", "pipeline::fast"], command="/fast-implement", blockers=[]
    )

    sut = agent_prompt(card, EPIC, tests=("Retry after a crash",), template=TEMPLATE)

    assert sut.startswith("/fast-implement #814\n\n")
    assert "\nDEPENDENCIES: None\nPIPELINE: afk → /fast-implement\n" in sut
    assert "\nTESTS / ADVERSARIAL SCENARIOS:\n- Retry after a crash\n\n" in sut


def test_agent_prompt_leaves_out_every_block_without_data() -> None:
    card: dict[str, object] = {
        "id": "#5",
        "title": "T",
        "url": None,
        "labels": [],
        "command": "/implement",
        "what": "",
        "criteria": [],
        "files": [],
        "blockers": [],
    }

    sut = agent_prompt(card, {"id": "#1", "title": "S", "branch": None})

    assert sut == "\n".join(
        [
            "/implement #5",
            "",
            "EPIC: #1 S",
            "TASK: #5 — T",
            "ISSUES: #5, #1",
            "DEPENDENCIES: None",
            "PIPELINE: /implement",
        ]
    )


@pytest.mark.parametrize(
    ("url", "repository"),
    [
        (
            "https://github.example.test/acme/app/issues/814",
            "https://github.example.test/acme/app",
        ),
        (
            "https://gitlab.example.test/grp/sub/app/-/issues/12",
            "https://gitlab.example.test/grp/sub/app",
        ),
    ],
)
def test_agent_prompt_repository_is_the_tracker_of_the_ticket(
    url: str, repository: str
) -> None:
    sut = agent_prompt(_release_card(url=url), EPIC)

    assert f"\nREPOSITORY: {repository}\n" in sut


@dataclass
class _Batch:
    batch_id: str
    ticket: str
    state: str
    created_at: str


@dataclass
class _Stage:
    batch_id: str
    role: str
    state: str
    at: str


@dataclass
class _View:
    batches: list[_Batch] = field(default_factory=list)
    stages: list[_Stage] = field(default_factory=list)
    unavailable: str | None = None


def test_batch_stages_take_the_newest_open_batch_and_latest_dispatch() -> None:
    view = _View(
        batches=[
            _Batch("b-old", "#913", "active", "2026-11-01T00:00:00Z"),
            _Batch("b-new", "#913", "active", "2026-11-05T00:00:00Z"),
            _Batch("b-done", "#914", "completed", "2026-11-05T00:00:00Z"),
            _Batch("b-gone", "#915", "abandoned", "2026-11-05T00:00:00Z"),
            _Batch("b-blocked", "#916", "blocked", "2026-11-05T00:00:00Z"),
        ],
        stages=[
            _Stage("b-new", "architect", "completed", "2026-11-05T01:00:00Z"),
            _Stage("b-new", "code-review", "working", "2026-11-05T03:00:00Z"),
            _Stage("b-new", "developer", "completed", "2026-11-05T02:00:00Z"),
            _Stage("b-old", "qa", "working", "2026-11-06T00:00:00Z"),
            _Stage("b-done", "qa", "working", "2026-11-06T00:00:00Z"),
        ],
    )

    stages = batch_stages(view)

    assert stages == {
        "#913": BatchStage("b-new", "active", "code-review", "working"),
        "#916": BatchStage("b-blocked", "blocked", None, None),
    }


def test_batch_stages_of_an_unavailable_ledger_are_empty() -> None:
    view = _View(
        batches=[_Batch("b", "#1", "active", "2026-11-01T00:00:00Z")],
        unavailable="no ledger",
    )

    assert batch_stages(view) == {}


def _board() -> SpecTickets:
    tickets = (
        _ticket(
            "afk",
            "pipeline::fast",
            "status::in-progress",
            "priority::p0",
            ref="#913",
            n=913,
            body=HOSTED_BODY,
            blockers=(BlockerFact("#882", 882, "Shell", False),),
        ),
        _ticket("status::ready", ref="#882", n=882),
        _ticket("status::in-progress", ref="#886", n=886, pr=PR),
        _ticket("hitl", ref="#880", n=880, closed=True),
        _ticket("resolution::wontfix", ref="#870", n=870, closed=True),
    )
    return SpecTickets(SPEC, tickets, {"#880": True, "#882": False})


def test_board_payload_columns_kpis_and_cards() -> None:
    stages = {"#913": BatchStage("b-913", "active", "developer", "working")}

    payload = build_board_payload("github", _board(), stages, ledger_ok=True)

    assert payload["tracker"] == "github"
    assert payload["ledger"] == "ok"
    cards = cast(list[dict[str, object]], payload["tickets"])
    assert payload["columns"] == [
        {
            "id": column_id,
            "count": sum(card["column"] == column_id for card in cards),
        }
        for column_id in COLUMNS
    ]
    assert [COLUMNS.index(str(card["column"])) for card in cards] == sorted(
        COLUMNS.index(str(card["column"])) for card in cards
    )
    assert payload["spec"] == {
        "id": "#862",
        "n": 862,
        "title": "Web console",
        "url": "https://example.test/issues/862",
        "branch": "integration/web-console",
    }
    tickets = payload["tickets"]
    assert isinstance(tickets, list)
    assert [(t["id"], t["column"]) for t in tickets] == [
        ("#882", "ready"),
        ("#913", "progress"),
        ("#886", "review"),
        ("#880", "done"),
    ]
    assert payload["kpis"] == {
        "open": 3,
        "total": 4,
        "with_open_blockers": 1,
        "active_batch": 1,
    }
    card = tickets[1]
    assert card["command"] == "/fast-implement"
    assert card["priority"] == "priority::p0"
    assert card["sp"] == 5
    assert card["batch"] == "b-913"
    assert card["dispatch"] == "developer"
    assert card["blockers"] == [
        {"id": "#882", "n": 882, "why": "needs the shell", "state": "open"},
        {"id": "#880", "n": 880, "why": "mockups", "state": "closed"},
    ]
    assert card["open_blockers"] == 1
    assert card["pr"] is None
    assert tickets[2]["pr"] == {"ref": "#958", "url": "https://example.test/pull/958"}
    prompt = card["prompt"]
    assert isinstance(prompt, str)
    assert prompt.startswith(
        "/fast-implement #913\n\nREPOSITORY: https://example.test\n"
        "EPIC: #862 Web console\nTASK: #913 — Ticket #913\nISSUES: #913, #862\n"
        "DEPENDENCIES: #882, #880\nPIPELINE: afk → /fast-implement\n"
    )
    assert payload["truncated"] is False


def test_board_payload_prompt_takes_tests_and_the_project_template() -> None:
    body = HOSTED_BODY + "\n## Tests\n- Two moves at once\n- A closed blocker\n"
    board = SpecTickets(SPEC, (_ticket("hitl", ref="#913", n=913, body=body),), {})

    payload = build_board_payload("github", board, {}, True, template=TEMPLATE)

    cards = cast(list[dict[str, object]], payload["tickets"])
    prompt = str(cards[0]["prompt"])
    assert (
        "\nTESTS / ADVERSARIAL SCENARIOS:\n- Two moves at once\n- A closed blocker\n\n"
        "IMPLEMENTATION DISCIPLINE:\nRead the approved ADR first."
    ) in prompt
    assert (
        "\nARCHITECTURE INVARIANTS (MANDATORY):\n- Target architecture only.\n"
        in prompt
    )


def test_board_payload_without_ledger_marks_it_unavailable() -> None:
    payload = build_board_payload("github", _board(), {}, ledger_ok=False)

    assert payload["ledger"] == "unavailable"


def test_board_payload_caps_hostile_tickets() -> None:
    hostile = "## What to build\n" + "\ud800\x00é" * 200_000
    tickets = tuple(
        _ticket("status::ready", ref=f"#{n}", n=n, body=hostile)
        for n in range(MAX_TICKETS + 5)
    )
    title = "t" * (TITLE_BYTES * 3)
    spec = TrackerSpec("#1", 1, title, None, "x" * (BODY_READ_BYTES * 2), None, None)

    payload = build_board_payload("github", SpecTickets(spec, tickets, {}), {}, True)

    cards = payload["tickets"]
    assert isinstance(cards, list)
    assert len(cards) == MAX_TICKETS
    assert payload["truncated"] is True
    assert all(card["truncated"] for card in cards)
    what = cards[0]["what"]
    assert sum(_wire_cost(char) for char in what) <= WHAT_BYTES
    spec_out = payload["spec"]
    assert isinstance(spec_out, dict)
    assert sum(_wire_cost(char) for char in spec_out["title"]) <= TITLE_BYTES


def test_specs_payload_lists_specs_with_branch() -> None:
    payload = build_specs_payload("gitlab", (SPEC,))

    assert payload == {
        "tracker": "gitlab",
        "stale": None,
        "age_seconds": None,
        "specs": [
            {
                "id": "#862",
                "n": 862,
                "title": "Web console",
                "url": "https://example.test/issues/862",
                "branch": "integration/web-console",
                "tickets_total": 3,
                "tickets_open": 2,
            }
        ],
        "truncated": False,
    }


def test_specs_payload_without_specs() -> None:
    assert build_specs_payload("local", ())["specs"] == []


def test_specs_payload_flags_a_truncated_tracker_listing() -> None:
    payload = build_specs_payload("gitlab", SpecList((SPEC,), truncated=True))

    assert payload["truncated"] is True
    assert build_specs_payload("gitlab", SpecList((SPEC,)))["truncated"] is False


def test_board_payload_flags_a_truncated_tracker_listing() -> None:
    board = _board()
    listed = SpecTickets(board.spec, board.tickets, board.blocker_states, truncated=True)

    assert build_board_payload("github", listed, {}, True)["truncated"] is True


def test_board_payload_total_size_is_bounded() -> None:
    body = (
        "## What to build\n"
        + "w" * WHAT_BYTES
        + "\n## Acceptance criteria\n"
        + "".join(f"- {'c' * 590}\n" for _ in range(CRITERIA_MAX))
        + "## Relevant Files (Discovery Context)\n"
        + "".join(f"- `{'p' * 290}` \u2014 {'y' * 290}\n" for _ in range(40))
    )
    tickets = tuple(
        _ticket("status::ready", ref=f"#{n}", n=n, body=body)
        for n in range(1, MAX_TICKETS + 1)
    )

    payload = build_board_payload("github", SpecTickets(SPEC, tickets, {}), {}, True)

    size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8", "surrogatepass"))
    assert size <= BOARD_BYTES
    assert payload["truncated"] is True
    cards = payload["tickets"]
    assert isinstance(cards, list)
    assert 0 < len(cards) < MAX_TICKETS


def test_order_cards_sorts_by_column_then_priority_then_number() -> None:
    from harness.console.backend.domain.task_board import order_cards

    def card(n: int | None, column: str, priority: str | None) -> dict[str, object]:
        return {"id": f"#{n}", "n": n, "column": column, "priority": priority}

    ordered = order_cards(
        [
            card(5, "done", "priority::p0"),
            card(4, "ready", None),
            card(3, "ready", "priority::p1"),
            card(2, "ready", "priority::p0"),
            card(1, "backlog", "priority::p3"),
            card(None, "ready", "priority::p0"),
        ]
    )
    assert [item["id"] for item in ordered] == ["#1", "#2", "#None", "#3", "#4", "#5"]


def test_board_payload_prompt_prefers_the_blocks_of_the_epic_body() -> None:
    epic = TrackerSpec(
        ref="#862",
        n=862,
        title="Web console",
        url=None,
        body=(
            "## Integration Branch\n`integration/web-console`\n\n"
            "## Architecture invariants\n- The server owns every board rule.\n"
        ),
        tickets_total=1,
        tickets_open=1,
    )
    board = SpecTickets(epic, (_ticket("hitl", ref="#913", n=913),), {})

    payload = build_board_payload("github", board, {}, True, template=TEMPLATE)

    prompt = str(cast(list[dict[str, object]], payload["tickets"])[0]["prompt"])
    assert (
        "\n\nARCHITECTURE INVARIANTS (MANDATORY):\n- The server owns every board rule.\n\n"
    ) in prompt
    assert "Target architecture only." not in prompt
    assert prompt.endswith(
        "\n\nIMPLEMENTATION DISCIPLINE:\nRead the approved ADR first."
    )
