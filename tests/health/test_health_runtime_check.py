"""`orchestration.runtime` reports whether the runtime of a runtime-store repository answers."""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

import pytest

from harness.health.checks import orchestration as checks
from harness.health.context import HealthContext
from harness.orchestration.ledger.lifecycle import STORE_LEDGER_VERSION
from harness.orchestration.runtime_client import (
    RuntimeClient,
    RuntimeClientError,
    RuntimeReply,
)


def _context(repo: Path, *, store: bool) -> HealthContext:
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    state = repo / ".harness" / "orchestration" / "state"
    state.mkdir(parents=True)
    pointer = {"version": STORE_LEDGER_VERSION} if store else {"version": 3}
    (state / "ledger.json").write_text(json.dumps(pointer), encoding="utf-8")
    return HealthContext(
        repo=repo, lock={"capabilities": ["backend-orchestration"]}, online=False
    )


class _Refuse:
    """A `RuntimeClient.call` stand-in that refuses with one runtime error code."""

    def __init__(self, code: str, remedy: str) -> None:
        self.code = code
        self.remedy = remedy

    def __call__(self, *args: object, **kwargs: object) -> RuntimeReply:
        raise RuntimeClientError(self.code, "refused", remedy=self.remedy, domain="infrastructure")


def test_a_runtime_that_answers_is_ok_with_its_pid_version_and_protocol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path, store=True)

    def answer(self: RuntimeClient, operation: str, **kwargs: object) -> RuntimeReply:
        assert operation == "status"
        return RuntimeReply(
            hello={"protocol": {"major": 1, "minor": 7}, "server_version": "2.0.0"},
            result={"pid": 4242},
            revision=None,
        )

    monkeypatch.setattr(RuntimeClient, "call", answer)

    result = checks.check_runtime(context)

    assert (result.id, result.group, result.status) == (
        "orchestration.runtime",
        "orchestration",
        "ok",
    )
    assert "4242" in result.message
    assert "2.0.0" in result.message
    assert "1.7" in result.message


def test_a_runtime_that_does_not_answer_fails_with_the_serve_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path, store=True)
    monkeypatch.setattr(RuntimeClient, "call", _Refuse("runtime_unavailable", "start it"))

    result = checks.check_runtime(context)
    summary = checks.check_ledger_summary(context)

    expected = f"harness-runtime serve --repo {shlex.quote(str(tmp_path.resolve()))}"
    assert result.status == "fail"
    assert result.fix is not None and result.fix.command == expected
    assert summary.status == "fail"
    assert summary.fix is not None and summary.fix.command == expected


def test_an_incompatible_protocol_fails_with_the_client_remedy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path, store=True)
    remedy = "update harness and harness-runtime to the same release"
    monkeypatch.setattr(RuntimeClient, "call", _Refuse("protocol_unsupported", remedy))

    result = checks.check_runtime(context)

    assert result.status == "fail"
    assert "protocol_unsupported" in result.message
    assert result.fix is not None and remedy in result.fix.text


def test_a_file_ledger_skips_the_runtime_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path, store=False)
    monkeypatch.setattr(RuntimeClient, "call", _Refuse("runtime_unavailable", "start it"))

    assert checks.check_runtime(context).status == "skipped"


def test_health_probes_unavailable_runtime_once_across_all_orchestration_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path, store=True)
    (tmp_path / ".harness" / "orchestration.json").write_text(
        json.dumps({"extensions": {"runtime_access": "docker"}}), encoding="utf-8"
    )
    calls: list[str] = []

    def refuse(self: RuntimeClient, operation: str, **kwargs: object) -> RuntimeReply:
        calls.append(operation)
        raise RuntimeClientError(
            "runtime_unavailable",
            "harness-runtime does not answer",
            remedy="start it",
            domain="infrastructure",
        )

    monkeypatch.setattr(RuntimeClient, "call", refuse)

    results = {
        check_id: fn(context)
        for check_id, fn in (
            ("orchestration.runtime", checks.check_runtime),
            ("orchestration.ledger_summary", checks.check_ledger_summary),
            ("orchestration.unfinished_batches", checks.check_unfinished_batches),
            ("orchestration.blocked_batches", checks.check_blocked_batches),
            ("orchestration.stale_dispatches", checks.check_stale_dispatches),
            ("orchestration.orphaned_worktrees", checks.check_orphaned_worktrees),
            ("orchestration.disposable_data", checks.check_disposable_data),
            ("orchestration.worker_binaries", checks.check_worker_binaries),
            ("orchestration.rebaser_route", checks.check_rebaser_route),
        )
    }

    assert calls == ["status"]
    assert results["orchestration.runtime"].status == "fail"
    assert results["orchestration.ledger_summary"].status == "fail"
    assert results["orchestration.ledger_summary"].fix is not None
    assert results["orchestration.unfinished_batches"].status == "fail"
    assert results["orchestration.blocked_batches"].status == "fail"
    assert results["orchestration.stale_dispatches"].status == "fail"
    assert results["orchestration.orphaned_worktrees"].status == "skipped"
    assert results["orchestration.worker_binaries"].status == "skipped"
