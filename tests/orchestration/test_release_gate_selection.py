"""The selection a Release Gate pair requires is decided by the pair record, never by the request
(ADR 0023, section 7; ADR 0026, section 4).

The request ``qa.evidence.verify`` carries exactly ``{candidate_sha, target_sha}``: the runtime
refuses any other field with ``malformed_request`` (pinned in the Rust tests), and the Python
client never sends one.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from harness.orchestration import runtime_client
from harness.orchestration.core.utils import JsonObject
from harness.orchestration.workflow import release_gate

CANDIDATE = "c" * 40
TARGET = "1" * 40


class RecordingClient:
    """Stands in for the transport only: it records what the coordinator would send."""

    calls: list[tuple[str, JsonObject]] = []

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def call(
        self, operation: str, *, payload: JsonObject, **_: object
    ) -> runtime_client.RuntimeReply:
        RecordingClient.calls.append((operation, payload))
        return runtime_client.RuntimeReply(
            hello={}, result={"verdict": "ok", "violations": []}, revision=None
        )


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, JsonObject]]:
    RecordingClient.calls = []
    monkeypatch.setattr(runtime_client, "RuntimeClient", RecordingClient)
    return RecordingClient.calls


def test_the_verify_request_carries_exactly_the_pair(
    recorded: list[tuple[str, JsonObject]], tmp_path: Path
) -> None:
    release_gate.qa_evidence_verify(
        tmp_path, {"candidate_sha": CANDIDATE, "target_sha": TARGET}
    )

    assert recorded == [
        (
            runtime_client.QA_EVIDENCE_VERIFY,
            {"candidate_sha": CANDIDATE, "target_sha": TARGET},
        )
    ]


def test_a_stray_requirement_in_the_pair_never_reaches_the_request(
    recorded: list[tuple[str, JsonObject]], tmp_path: Path
) -> None:
    release_gate.qa_evidence_verify(
        tmp_path,
        {
            "candidate_sha": CANDIDATE,
            "target_sha": TARGET,
            "requirement": release_gate.SELECTION_TICKET_DIFF,
            "selection": release_gate.SELECTION_TICKET_DIFF,
        },
    )

    ((_, payload),) = recorded
    assert set(payload) == {"candidate_sha", "target_sha"}


def test_the_client_cannot_ask_for_a_requirement() -> None:
    parameters = inspect.signature(release_gate.qa_evidence_verify).parameters

    assert list(parameters) == ["repo", "pair"]
    assert list(inspect.signature(release_gate.require_evidence).parameters) == [
        "repo",
        "root",
        "pair",
    ]
    assert list(inspect.signature(release_gate.handoff_gate).parameters) == [
        "repo",
        "root",
        "remote",
        "branch",
        "pair",
    ]
