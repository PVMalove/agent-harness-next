"""The Harness page facts of the Runtime and Adapters tabs: the runtime status probe (one empty
`state.read`, the runtime is never started) and the Claude Code, Codex and tracker adapters."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from harness.console.backend.infrastructure import screen_facts
from harness.console.kernel import data as console_data
from harness.console.kernel.home_snapshot import StoreFacts
from harness.health.project_tracker import ProjectTracker
from harness.orchestration.runtime_client import RuntimeClientError


def test_a_runtime_that_answers_is_online_with_its_revision(tmp_path: Path) -> None:
    status = screen_facts.runtime_status(tmp_path, read=lambda: 42)
    assert status == {"state": "online", "revision": 42, "reason": ""}


def test_a_runtime_that_does_not_answer_is_offline_with_the_reason(tmp_path: Path) -> None:
    def refuse() -> int | None:
        raise RuntimeClientError("runtime_unavailable", "no socket", remedy="start it", domain="transport")

    status = screen_facts.runtime_status(tmp_path, read=refuse)
    assert status == {
        "state": "offline",
        "revision": None,
        "reason": "runtime не отвечает (runtime_unavailable)",
    }


def test_the_real_probe_of_a_project_without_a_runtime_is_offline(tmp_path: Path) -> None:
    status = screen_facts.runtime_status(tmp_path)
    assert status["state"] == "offline"
    assert status["revision"] is None
    assert str(status["reason"]).startswith("runtime не отвечает (")


def _which(found: set[str]) -> Callable[[str], str | None]:
    return lambda name: f"/usr/bin/{name}" if name in found else None


ADAPTERS: list[dict[str, object]] = [
    {"path": ".harness/adapters/claude_worker.py", "status": "current", "problem": None},
    {"path": ".harness/adapters/codex_worker.py", "status": "outdated", "problem": None},
]
GITHUB = ProjectTracker("github", "github.com", "owner/repo", "config")


def test_claude_code_codex_and_the_tracker_are_the_three_adapters() -> None:
    facts = screen_facts.integration_facts(
        ADAPTERS, GITHUB, which=_which({"claude", "gh"})
    )
    assert facts == [
        {"name": "Claude Code", "kind": "runtime", "status": "current", "cli": True, "detail": ".harness/adapters/claude_worker.py"},
        {"name": "Codex", "kind": "runtime", "status": "outdated", "cli": False, "detail": ".harness/adapters/codex_worker.py"},
        {"name": "GitHub", "kind": "tracker", "status": "current", "cli": True, "detail": "github.com/owner/repo"},
    ]


def test_unknown_adapter_files_and_a_tracker_without_its_cli() -> None:
    gitlab = ProjectTracker("gitlab", "gitlab.example", "team/app", "config")
    facts = screen_facts.integration_facts(None, gitlab, which=_which(set()))
    assert [(item["name"], item["status"], item["cli"]) for item in facts] == [
        ("Claude Code", "unknown", False),
        ("Codex", "unknown", False),
        ("GitLab", "missing", False),
    ]
    local = ProjectTracker("local", None, None, "default")
    assert screen_facts.integration_facts([], local, which=_which(set()))[2] == {
        "name": "Local",
        "kind": "tracker",
        "status": "current",
        "cli": None,
        "detail": "",
    }


def test_harness_facts_carry_the_runtime_status_and_the_adapters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(screen_facts, "container_facts", lambda repo: {})
    monkeypatch.setattr(console_data, "drift_report", lambda repo: None)
    monkeypatch.setattr(screen_facts, "resolve_project_tracker", lambda repo: type("R", (), {"effective": GITHUB})())
    monkeypatch.setattr(screen_facts, "runtime_status", lambda repo: {"state": "online", "revision": 7, "reason": ""})
    facts = screen_facts.harness_facts(tmp_path)
    assert facts["runtime"] == {"state": "online", "revision": 7, "reason": ""}
    integrations = facts["integrations"]
    assert isinstance(integrations, list)
    names = [item["name"] for item in integrations]
    assert names[:2] == ["Claude Code", "Codex"]


def _harness_without_side_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(screen_facts, "container_facts", lambda repo: {})
    monkeypatch.setattr(console_data, "drift_report", lambda repo: None)
    monkeypatch.setattr(screen_facts, "resolve_project_tracker", lambda repo: type("R", (), {"effective": GITHUB})())


def test_a_cold_runtime_store_snapshot_waits_for_one_probe_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _harness_without_side_reads(monkeypatch)
    reason = "runtime не отвечает (runtime_unavailable)"
    monkeypatch.setattr(
        screen_facts, "store_facts", lambda repo: StoreFacts("runtime-store", 4, "g", None, reason=reason)
    )

    def second_probe(repo: Path) -> dict[str, object]:
        raise AssertionError("the runtime was probed twice")

    monkeypatch.setattr(screen_facts, "runtime_status", second_probe)
    facts = screen_facts.harness_facts(tmp_path)
    assert facts["runtime"] == {"state": "offline", "revision": None, "reason": reason}


@pytest.mark.parametrize(
    "store",
    [
        StoreFacts("runtime-store", 4, "g", 11, reason=""),
        StoreFacts("runtime-store", 4, "g", None, reason="runtime не сообщил число записей аудита"),
        StoreFacts("file-ledger", 3, "g", 2),
    ],
)
def test_the_runtime_is_probed_when_the_store_read_did_not_wait_for_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, store: StoreFacts
) -> None:
    _harness_without_side_reads(monkeypatch)
    monkeypatch.setattr(screen_facts, "store_facts", lambda repo: store)
    monkeypatch.setattr(screen_facts, "runtime_status", lambda repo: {"state": "online", "revision": 9, "reason": ""})
    assert screen_facts.harness_facts(tmp_path)["runtime"] == {"state": "online", "revision": 9, "reason": ""}
