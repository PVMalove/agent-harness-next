"""A ledger the process may not write is an infrastructure refusal, not a traceback."""

from __future__ import annotations

import errno
from pathlib import Path

import pytest

from harness.orchestration.ledger.ledger_ops import SandboxDeniedError, _ledger_lock
from harness.orchestration.ledger.lifecycle import LifecycleLedger


@pytest.mark.parametrize("code", [errno.EROFS, errno.EACCES, errno.EPERM])
def test_unwritable_ledger_state_is_reported_as_sandbox_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    real_mkdir = Path.mkdir

    def denied(self: Path, *args: object, **kwargs: object) -> None:
        if self.name == ".coordinator.lock":
            raise OSError(code, "Read-only file system", str(self))
        real_mkdir(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "mkdir", denied)
    with pytest.raises(SandboxDeniedError) as caught:
        with _ledger_lock(LifecycleLedger(tmp_path)):
            pytest.fail("the lock must not be taken")
    assert caught.value.message.startswith("sandbox_denied:")
    assert ".coordinator.lock" in caught.value.message
    assert "allowWrite" in caught.value.remedy
    # A Claude Code worker also writes the inbox and the shared check directories.
    assert "inbox" in caught.value.remedy
    for name in ("runs/qa", "runs/tests", "logs", "cache/npm", "cache/ms-playwright"):
        assert name in caught.value.remedy


def test_other_os_errors_are_not_called_sandbox_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_mkdir = Path.mkdir

    def broken(self: Path, *args: object, **kwargs: object) -> None:
        if self.name == ".coordinator.lock":
            raise OSError(errno.ENOSPC, "No space left on device", str(self))
        real_mkdir(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "mkdir", broken)
    with pytest.raises(OSError) as caught:
        with _ledger_lock(LifecycleLedger(tmp_path)):
            pytest.fail("the lock must not be taken")
    assert not isinstance(caught.value, SandboxDeniedError)


def test_ledger_lock_probe_takes_the_real_lock_and_reports_a_denial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.orchestration.operation_access import _probe_ledger_lock

    assert _probe_ledger_lock(tmp_path) == ("verified", "lock taken and released")
    assert not (tmp_path / ".coordinator.lock").exists()

    (tmp_path / ".coordinator.lock").mkdir()
    state, reason = _probe_ledger_lock(tmp_path)
    assert state == "verified" and "held by another operation" in reason
    (tmp_path / ".coordinator.lock").rmdir()

    real_mkdir = Path.mkdir

    def denied(self: Path, *args: object, **kwargs: object) -> None:
        if self.name == ".coordinator.lock":
            raise OSError(errno.EROFS, "Read-only file system", str(self))
        real_mkdir(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "mkdir", denied)
    state, reason = _probe_ledger_lock(tmp_path)
    assert state == "denied" and reason.startswith("sandbox_denied:")


def test_runtime_probe_asks_only_the_runtime_of_its_own_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The store epoch: a standard state dir probes its repository, any other is refused (#1251)."""
    from harness.orchestration import operation_access
    from harness.orchestration.ledger import lifecycle

    asked: list[Path] = []

    class Client:
        def __init__(self, repo: Path) -> None:
            asked.append(repo)

        def call(self, *args: object, **kwargs: object) -> None:
            return None

    monkeypatch.setattr(lifecycle, "store_is_authority", lambda root: True)
    monkeypatch.setattr("harness.orchestration.runtime_client.RuntimeClient", Client)
    state_dir = tmp_path / "repo" / ".harness" / "orchestration" / "state"

    assert operation_access._probe_ledger_lock(state_dir)[0] == "verified"
    assert asked == [tmp_path / "repo"]

    state, reason = operation_access._probe_ledger_lock(tmp_path / "elsewhere" / "a" / "b")
    assert state == "denied" and "without --state-dir" in reason
    assert asked == [tmp_path / "repo"]
