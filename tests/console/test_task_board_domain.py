"""The pure task-board rules: ticket body parsing, the column table, the launch command, the agent
prompt, the batch stages of the ledger and the bounded board payloads."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from harness.console.backend.domain.task_board import (
    BODY_READ_BYTES,
    CRITERIA_MAX,
    COLUMNS,
    MAX_TICKETS,
    TITLE_BYTES,
    WHAT_BYTES,
    BatchStage,
    BlockerFact,
    PullRef,
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


def test_agent_prompt_exact_text() -> None:
    card: dict[str, object] = {
        "id": "#913",
        "title": "Task board snapshot",
        "command": "/fast-implement",
        "branch": "integration/web-console",
        "what": "Build it.",
        "criteria": ["First", "Second"],
        "blockers": [
            {"id": "#882", "n": 882, "why": "shell", "state": "open"},
            {"id": "#880", "n": 880, "why": "", "state": "closed"},
        ],
        "files": [{"path": "a.py", "why": "rules"}, {"path": "b/", "why": ""}],
    }
    spec: dict[str, object] = {"id": "#862", "title": "Web console", "branch": None}

    assert agent_prompt(card, spec) == "\n".join(
        [
            "/fast-implement #913",
            "",
            "TICKET: #913 — Task board snapshot",
            "EPIC: #862 — Web console",
            "BRANCH: integration/web-console",
            "",
            "WHAT TO BUILD:",
            "Build it.",
            "",
            "ACCEPTANCE:",
            "1. First",
            "2. Second",
            "",
            "BLOCKERS:",
            "- #882 — shell",
            "- #880 (closed)",
            "",
            "DISCOVERY:",
            "- a.py — rules",
            "- b/",
        ]
    )


def test_agent_prompt_without_blockers_files_or_branch() -> None:
    card: dict[str, object] = {
        "id": "#5",
        "title": "T",
        "command": "/to-guide",
        "branch": None,
        "what": "",
        "criteria": [],
        "blockers": [],
        "files": [],
    }
    prompt = agent_prompt(card, {"id": "#1", "title": "S", "branch": None})

    assert prompt.startswith("/to-guide #5\n")
    assert "BRANCH: not recorded" in prompt
    assert prompt.endswith("BLOCKERS:\n- None\n\nDISCOVERY:\n- None")


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
    assert payload["columns"] == [{"id": column_id} for column_id in COLUMNS]
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
        ("#880", "done"),
        ("#882", "ready"),
        ("#886", "review"),
        ("#913", "progress"),
    ]
    assert payload["kpis"] == {
        "open": 3,
        "total": 4,
        "with_open_blockers": 1,
        "active_batch": 1,
    }
    card = tickets[3]
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
    assert prompt.startswith("/fast-implement #913\n\nTICKET: #913 — Ticket #913\n")
    assert "EPIC: #862 — Web console" in prompt
    assert "BRANCH: integration/web-console" in prompt
    assert payload["truncated"] is False


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
