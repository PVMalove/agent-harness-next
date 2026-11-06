"""Approval compatibility for pre-#826 stores, through the real runtime CLI."""

from __future__ import annotations

import hashlib
import json
import os
import select
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

from harness.orchestration.ledger.lifecycle import _canonical

from .runtime_store_support import STATE_REL, Store, runtime_binary

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Unix runtime seam")

APPROVAL = {
    "approved_by": "Rina",
    "approved_at": "2026-10-30T08:15:00+00:00",
    "reason": "accept the pre-826 import and preserve subsequent state",
}


def _old_format(store: Store) -> None:
    store.stop_runtime()
    marker = store.repo / STATE_REL / "AUTHORITY.json"
    authority = json.loads(marker.read_text())
    for key in APPROVAL:
        del authority[key]
    marker.write_text(_canonical(authority))
    with closing(sqlite3.connect(store.database)) as connection:
        previous = "0" * 64
        rows = connection.execute(
            "SELECT seq, at, action, details_json FROM audit ORDER BY seq"
        )
        for seq, at, action, raw in rows.fetchall():
            details = json.loads(raw)
            if seq == 1:
                for key in APPROVAL:
                    del details[key]
            record = hashlib.sha256(
                _canonical({"action": action, "at": at, "details": details}).encode()
            ).hexdigest()
            chain = hashlib.sha256((previous + record).encode()).hexdigest()
            connection.execute(
                "UPDATE audit SET details_json=?, record_sha256=?, prev_chain_sha256=?, "
                "chain_sha256=? WHERE seq=?",
                (_canonical(details), record, previous, chain, seq),
            )
            previous = chain
        connection.execute(
            "UPDATE audit_checkpoint SET seq=?, chain_sha256=? WHERE id=1",
            (seq, previous),
        )
        connection.commit()


def _repair(
    store: Store, *flags: str, approved: bool = False
) -> subprocess.CompletedProcess[str]:
    approval = [
        part
        for key, value in APPROVAL.items()
        for part in (f"--{key.replace('_', '-')}", value)
    ]
    return subprocess.run(
        [
            str(runtime_binary()),
            "repair-import-approval",
            "--repo",
            str(store.repo),
            *flags,
            *(approval if approved else []),
        ],
        env={**os.environ, **store.runtime.environ},
        text=True,
        capture_output=True,
        check=False,
    )


def test_full_validation_identifies_an_unsupported_old_import_without_recommending_data_loss(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path)
    try:
        _old_format(store)
        store.restart_runtime()

        result = store.run("ledger", "validate", "--full")

        assert result.returncode == 2
        assert "[approval_mismatch]" in result.stderr
        assert "repair-import-approval" in result.stderr
        assert "restore" not in result.stderr
    finally:
        store.stop_runtime()


def test_the_operator_can_check_the_old_store_but_cannot_repair_without_human_approval(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path)
    try:
        _old_format(store)
        before = store.database.read_bytes()
        marker = (store.repo / STATE_REL / "AUTHORITY.json").read_bytes()

        checked = _repair(store, "--check")
        refused = _repair(store)

        assert checked.returncode == 2, checked.stderr
        assert "[approval_mismatch]" in checked.stderr
        assert refused.returncode == 2, refused.stderr
        assert "[malformed_request]" in refused.stderr
        assert store.database.read_bytes() == before
        assert (store.repo / STATE_REL / "AUTHORITY.json").read_bytes() == marker
    finally:
        store.stop_runtime()


def _business_rows(store: Store) -> dict[str, list[tuple[object, ...]]]:
    with closing(sqlite3.connect(store.database)) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN "
            "('audit', 'audit_checkpoint') ORDER BY name"
        ).fetchall()
        return {
            name: sorted(
                connection.execute(f'SELECT * FROM "{name}"').fetchall(), key=repr
            )
            for (name,) in tables
        }


def test_repair_preserves_post_cutover_rows_and_is_idempotent(tmp_path: Path) -> None:
    store = Store(tmp_path)
    try:
        _old_format(store)
        before = _business_rows(store)
        with closing(sqlite3.connect(store.database)) as connection:
            history = connection.execute(
                "SELECT seq, at, action, details_json FROM audit"
            ).fetchall()
        assert (
            len(history) > 1
        )  # Store writes dispatch send and self-report after migration.
        marker = store.repo / STATE_REL / "AUTHORITY.json"
        authority = json.loads(marker.read_text())

        repaired = _repair(store, approved=True)

        assert repaired.returncode == 0, repaired.stderr
        outcome = json.loads(repaired.stdout)
        assert outcome["repaired"] is True
        assert _business_rows(store) == before
        assert json.loads(marker.read_text()) == {**authority, **APPROVAL}
        backup = store.repo / STATE_REL / outcome["backup"]
        assert (backup / "runtime.db").is_file()
        assert json.loads((backup / "AUTHORITY.json").read_text()) == authority
        with closing(sqlite3.connect(store.database)) as connection:
            rows = connection.execute(
                "SELECT seq, at, action, details_json FROM audit"
            ).fetchall()
            assert rows[1:-1] == history[1:]
            assert rows[-1][2] == "import-approval-repair"
            anchor = json.loads(rows[0][3])
            assert {key: anchor[key] for key in APPROVAL} == APPROVAL

        repeated = _repair(store, approved=True)
        assert repeated.returncode == 0, repeated.stderr
        assert json.loads(repeated.stdout)["already_repaired"] is True
        assert _repair(store, "--check").returncode == 0
        store.restart_runtime()
        ordinary = store.run("ledger", "validate")
        full = store.run("ledger", "validate", "--full")
        assert ordinary.returncode == 0, ordinary.stderr
        assert full.returncode == 0, full.stderr
    finally:
        store.stop_runtime()


REPAIR_STEPS = (
    "approval-backup",
    "approval-intent",
    "approval-install",
    "approval-installed",
    "approval-authority",
)


@pytest.mark.parametrize("step", REPAIR_STEPS)
def test_a_killed_repair_resumes_without_losing_a_row(
    tmp_path: Path, step: str
) -> None:
    store = Store(tmp_path)
    process = None
    try:
        _old_format(store)
        before = _business_rows(store)
        flags = [
            part
            for key, value in APPROVAL.items()
            for part in (f"--{key.replace('_', '-')}", value)
        ]
        process = subprocess.Popen(
            [
                str(runtime_binary()),
                "repair-import-approval",
                "--repo",
                str(store.repo),
                *flags,
            ],
            env={
                **os.environ,
                **store.runtime.environ,
                "HARNESS_RUNTIME_TEST_PAUSE_AT": step,
            },
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert process.stderr is not None
        assert select.select([process.stderr], [], [], 15)[
            0
        ], "repair did not reach its boundary"
        assert process.stderr.readline().strip() == f"PAUSED:{step}"
        concurrent = _repair(store, approved=True)
        assert concurrent.returncode == 2
        process.kill()
        process.wait(timeout=15)
        if step != "approval-backup":
            check = _repair(store, "--check")
            assert check.returncode == 2
            assert "unfinished" in check.stderr
            serving = subprocess.run(
                [str(runtime_binary()), "serve", "--repo", str(store.repo)],
                env={**os.environ, **store.runtime.environ},
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert serving.returncode == 2, serving.stderr
            assert "unfinished" in serving.stderr

        repeated = _repair(store, approved=True)

        assert repeated.returncode == 0, repeated.stderr
        assert _business_rows(store) == before
        with closing(sqlite3.connect(store.database)) as connection:
            assert connection.execute(
                "SELECT count(*) FROM audit WHERE action='import-approval-repair'"
            ).fetchone() == (1,)
        store.restart_runtime()
        result = store.run("ledger", "validate", "--full")
        assert result.returncode == 0, result.stderr
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=15)
        store.stop_runtime()


@pytest.mark.parametrize(
    "extra,code",
    [
        (("--approved-by", "policy:automatic"), "policy_denied"),
        (("--approved-at", "2999-01-01T00:00:00Z"), "malformed_request"),
        (("--approved-at", "yesterday"), "malformed_request"),
        (("--reason", " "), "malformed_request"),
    ],
)
def test_invalid_human_approval_changes_no_store_byte(
    tmp_path: Path,
    extra: tuple[str, str],
    code: str,
) -> None:
    store = Store(tmp_path)
    try:
        _old_format(store)
        before = store.database.read_bytes()
        flags = [
            part
            for key, value in APPROVAL.items()
            for part in (f"--{key.replace('_', '-')}", value)
        ]

        refused = _repair(store, *flags, *extra)

        assert refused.returncode == 2
        assert f"[{code}]" in refused.stderr
        assert store.database.read_bytes() == before
        assert not (store.repo / STATE_REL / "import-approval-backups").exists()
    finally:
        store.stop_runtime()


def test_a_failure_after_installation_names_the_repair_instead_of_snapshot_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = Store(tmp_path)
    try:
        _old_format(store)
        monkeypatch.setenv("HARNESS_RUNTIME_TEST_FAIL_AT", "approval-installed")

        failed = _repair(store, approved=True)

        assert failed.returncode == 3
        assert "repeat harness-runtime repair-import-approval" in failed.stderr
        assert "snapshot" not in failed.stderr
    finally:
        store.stop_runtime()


@pytest.mark.parametrize(
    "damage", ["partial_approval", "empty_approval", "audit", "business_row"]
)
def test_repair_never_legitimizes_other_damage(tmp_path: Path, damage: str) -> None:
    store = Store(tmp_path)
    try:
        _old_format(store)
        marker = store.repo / STATE_REL / "AUTHORITY.json"
        if damage in ("partial_approval", "empty_approval"):
            authority = json.loads(marker.read_text())
            authority["approved_by"] = "Rina" if damage == "partial_approval" else ""
            marker.write_text(_canonical(authority))
        else:
            with closing(sqlite3.connect(store.database)) as connection:
                if damage == "audit":
                    connection.execute(
                        "UPDATE audit SET record_sha256='damaged' WHERE seq=1"
                    )
                else:
                    connection.execute(
                        "UPDATE batch SET body_json=json_set(body_json, '$.ticket', '#tampered')"
                    )
                connection.commit()
        before = store.database.read_bytes(), marker.read_bytes()

        refused = _repair(store, approved=True)

        assert refused.returncode == 2, refused.stderr
        assert "[invariant_violation]" in refused.stderr
        assert (store.database.read_bytes(), marker.read_bytes()) == before
        assert not (store.repo / STATE_REL / "import-approval-backups").exists()
    finally:
        store.stop_runtime()


def test_a_live_runtime_excludes_repair(tmp_path: Path) -> None:
    store = Store(tmp_path)
    try:
        _old_format(store)
        store.restart_runtime()
        before = _business_rows(store)

        refused = _repair(store, approved=True)

        assert refused.returncode == 2
        assert "stop harness-runtime serve" in refused.stderr
        assert _business_rows(store) == before
        assert not (store.repo / STATE_REL / "import-approval-backups").exists()
    finally:
        store.stop_runtime()


def test_a_changed_backup_prevents_resuming_an_interrupted_repair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = Store(tmp_path)
    try:
        _old_format(store)
        monkeypatch.setenv("HARNESS_RUNTIME_TEST_FAIL_AT", "approval-installed")
        assert _repair(store, approved=True).returncode == 3
        monkeypatch.delenv("HARNESS_RUNTIME_TEST_FAIL_AT")
        state = store.repo / STATE_REL
        intent = json.loads((state / "IMPORT_APPROVAL_REPAIR.json").read_text())
        backup = state / intent["backup"] / "runtime.db"
        backup.write_bytes(backup.read_bytes() + b"damaged")
        before = store.database.read_bytes()

        refused = _repair(store, approved=True)

        assert refused.returncode == 4, refused.stderr
        assert "backup runtime.db changed" in refused.stderr
        assert store.database.read_bytes() == before
        assert (state / "IMPORT_APPROVAL_REPAIR.json").is_file()
    finally:
        store.stop_runtime()
