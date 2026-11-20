"""A ``state.read`` answer of the wrong shape is an error of every reader, never an empty store.

``runtime_client.read_state`` checks the answer once; each caller keeps its own handling of
``RuntimeClientError``. A well-formed answer without records still reads as an empty store.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from harness import cleanup
from harness.console.backend.application.ports import SourceUnavailable
from harness.console.backend.infrastructure import ledger as console_ledger
from harness.console.backend.infrastructure.orchestration_reader import ProjectReader
from harness.console.kernel import reports
from harness.orchestration import runtime_client
from harness.orchestration.core.utils import JsonObject
from harness.orchestration.ledger import ledger_ops
from harness.orchestration.runtime_client import RuntimeClientError, RuntimeReply
from harness.reporting import delivery_stats

MALFORMED: list[JsonObject] = [
    {},
    {"records": None},
    {"records": []},
    {"records": "batches"},
    {"records": {}, "revisions": []},
    {"records": {}, "snapshot": 7},
]
MALFORMED_IDS = [
    "no-records",
    "null-records",
    "list-records",
    "text-records",
    "list-revisions",
    "number-snapshot",
]
EMPTY: JsonObject = {"records": {}, "revisions": {}, "generation_revision": 1}


class _Runtime:
    """A runtime client whose every ``state.read`` answers ``result``."""

    result: JsonObject = {}

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def __enter__(self) -> _Runtime:
        return self

    def __exit__(self, *_exc: object) -> None:
        pass

    def call(self, operation: str, **_kwargs: object) -> RuntimeReply:
        assert operation == "state.read"
        return RuntimeReply(hello={}, result=self.result, revision=4)


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch) -> type[_Runtime]:
    class Runtime(_Runtime):
        pass

    monkeypatch.setattr(runtime_client, "RuntimeClient", Runtime)
    monkeypatch.setattr(cleanup, "RuntimeClient", Runtime)
    monkeypatch.setattr(console_ledger, "RuntimeClient", Runtime)
    monkeypatch.setattr(cleanup, "store_is_authority", lambda _state: True)
    monkeypatch.setattr(console_ledger, "store_is_authority", lambda _state: True)
    return Runtime


@pytest.mark.parametrize("result", MALFORMED, ids=MALFORMED_IDS)
def test_read_state_refuses_an_answer_of_the_wrong_shape(
    runtime: type[_Runtime], result: JsonObject
) -> None:
    runtime.result = result
    with pytest.raises(RuntimeClientError) as refused:
        runtime_client.read_state(
            runtime(), {}, operation_id="read-1", timeout_seconds=1
        )
    assert refused.value.code == "invalid_response"


def test_read_state_reads_an_answer_without_records_as_an_empty_store(
    runtime: type[_Runtime],
) -> None:
    runtime.result = EMPTY
    read = runtime_client.read_state(
        runtime(), {}, operation_id="read-1", timeout_seconds=1
    )
    assert (read.records, read.revisions, read.revision) == ({}, {}, 4)
    assert (read.snapshot, read.generation_revision) == (None, 1)


def _ledger_ops(tmp_path: Path) -> object:
    return ledger_ops._SnapshotRead(tmp_path)(["batches"], [], None)


def _orchestration_reader(tmp_path: Path) -> object:
    return ProjectReader(tmp_path)._runtime_fetch(["batches"], [])


def _reports(tmp_path: Path) -> object:
    return reports._runtime_read(tmp_path, 1)(["batches"], [])


def _console_ledger(tmp_path: Path) -> object:
    snapshot = console_ledger.collect_decisions(tmp_path)
    if snapshot.unavailable:
        raise RuntimeClientError(
            snapshot.error_code or "", "unavailable", remedy="-", domain="tooling"
        )
    return snapshot


def _cleanup(tmp_path: Path) -> object:
    (tmp_path / ".harness" / "orchestration" / "state").mkdir(parents=True)
    batches = cleanup._read_batches(tmp_path / ".harness")
    if isinstance(batches, cleanup._Unread):
        raise LookupError(batches.reason)
    return batches


READERS = [
    (_ledger_ops, RuntimeClientError),
    (_orchestration_reader, SourceUnavailable),
    (_reports, reports.StoreUnreadable),
    (_console_ledger, RuntimeClientError),
    (_cleanup, LookupError),
]
READER_IDS = [
    "ledger_ops",
    "orchestration_reader",
    "reports",
    "console_ledger",
    "cleanup",
]


@pytest.mark.parametrize(("reader", "error"), READERS, ids=READER_IDS)
@pytest.mark.parametrize("result", MALFORMED[:4], ids=MALFORMED_IDS[:4])
def test_every_reader_reports_a_malformed_answer_as_unavailable(
    runtime: type[_Runtime],
    tmp_path: Path,
    reader: Callable[[Path], object],
    error: type[Exception],
    result: JsonObject,
) -> None:
    runtime.result = result
    with pytest.raises(error) as refused:
        reader(tmp_path)
    if isinstance(refused.value, RuntimeClientError):
        assert refused.value.code == "invalid_response"
    if isinstance(refused.value, LookupError):
        assert refused.value.args == (cleanup.LEDGER_UNAVAILABLE,)


@pytest.mark.parametrize(("reader", "error"), READERS, ids=READER_IDS)
def test_every_reader_reads_an_empty_store_as_empty(
    runtime: type[_Runtime],
    tmp_path: Path,
    reader: Callable[[Path], object],
    error: type[Exception],
) -> None:
    runtime.result = EMPTY
    reader(tmp_path)


def _fake_tree(repo: Path, result: JsonObject) -> None:
    """The analysed repository's coordinator, whose runtime client answers ``result``."""
    coordinator = repo / ".harness" / "orchestration" / "coordinator.py"
    coordinator.parent.mkdir(parents=True)
    coordinator.write_text(
        "import sys, types\n"
        "for name in ('harness', 'harness.orchestration'):\n"
        "    sys.modules[name] = types.ModuleType(name)\n"
        "client = types.ModuleType('harness.orchestration.runtime_client')\n"
        "class RuntimeClientError(Exception):\n"
        "    code = 'internal'\n"
        "class Reply:\n"
        f"    result = {json.dumps(result)!s}\n"
        "class RuntimeClient:\n"
        "    def __init__(self, repo):\n"
        "        pass\n"
        "    def call(self, *args, **kwargs):\n"
        "        return Reply()\n"
        "client.RuntimeClient, client.RuntimeClientError = RuntimeClient, RuntimeClientError\n"
        "sys.modules['harness.orchestration.runtime_client'] = client\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "result",
    [{}, {"records": []}, {"records": "batches"}],
    ids=["no-records", "list-records", "text-records"],
)
def test_delivery_stats_report_a_malformed_answer_as_unavailable(
    tmp_path: Path, result: JsonObject
) -> None:
    _fake_tree(tmp_path, result)
    with pytest.raises(delivery_stats._StoreUnavailable, match="invalid_response"):
        delivery_stats._store_call(tmp_path, {"collections": ["batches"]})


def test_delivery_stats_read_an_answer_without_records_as_an_empty_store(
    tmp_path: Path,
) -> None:
    _fake_tree(tmp_path, {"records": {}})
    assert delivery_stats._store_call(tmp_path, {"collections": ["batches"]}) == {}


def test_delivery_stats_refuse_records_that_are_not_an_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_tree(tmp_path, {})

    def run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, json.dumps({"records": []}), "")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(delivery_stats._StoreUnavailable, match="invalid_response"):
        delivery_stats._store_call(tmp_path, {"collections": ["batches"]})
