"""The read-only reconciliation checks of one batch and the ``recoveryStatus.v1`` document.

``Survey`` keeps what the checks read and runs them in ``CHECKS`` order; each group of checks is
a component of its own: ``inputs`` reads the configuration, the store, the ledger and the batch,
``batch_state`` checks the lifecycle and the attention of the batch record, ``evidence`` the
runtime, the pinned snapshots, the Context Packages and the runtime compatibility, and
``dispatches`` the observed executions, the live workers and the approvals of the open
dispatches."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from harness.configuration import Bundle
from harness.orchestration import operational_hold
from harness.orchestration.core.utils import JsonObject, _now
from harness.orchestration.recovery_status import batch_state, dispatches, evidence, inputs
from harness.orchestration.recovery_status.batch_state import lifecycle_view
from harness.orchestration.recovery_status.intent import read_intent
from harness.orchestration.recovery_status.model import (
    CHECKS,
    RECOVERY_CONTRACT,
    CheckResult,
    RecoveryDiagnostic,
    RecoverySession,
)


def open_entries(batch: JsonObject) -> list[JsonObject]:
    """The dispatches of the batch's active chain that are not settled yet."""
    from harness.orchestration.ledger.recovery_chain import active_dispatches
    from harness.orchestration.workflow.history import _settled

    return [entry for entry in active_dispatches(batch) if not _settled(entry)]


class Survey:
    """The read-only reconciliation checks of one batch; ``resume`` acts on their result."""

    def __init__(self, repo: Path, root: Path, batch_id: str) -> None:
        self.repo = repo
        self.root = root
        self.batch_id = batch_id
        self.checks: dict[str, CheckResult] = {
            name: CheckResult(name) for name in CHECKS
        }
        self.hello: JsonObject | None = None
        self.hold: operational_hold.Hold | None = None
        self.batch: JsonObject | None = None
        self.config: JsonObject | None = None
        self.config_document: JsonObject | None = None
        self.bundle: Bundle | None = None
        self.hold_reason: str | None = None

    # The checks run in CHECKS order; a check whose input is missing is skipped.
    def run(self) -> Survey:
        self._config()
        self._store()
        self._ledger()
        self._batch()
        if self.batch is None:
            for name in CHECKS[CHECKS.index("lifecycle") :]:
                if name != "operation":
                    self._skip(name, "the batch record is not readable")
            dispatches.check_operation(self)
            return self
        batch_state.check_lifecycle(self)
        evidence.check_runtime(self)
        evidence.check_snapshot(self)
        evidence.check_context(self)
        evidence.check_compatibility(self)
        dispatches.check_operation(self)
        dispatches.check_liveness(self)
        batch_state.check_attention(self)
        dispatches.check_approval(self)
        return self

    def _skip(self, name: str, detail: str) -> None:
        self.checks[name].status = "skipped"
        self.checks[name].detail = detail

    # The inputs the later checks read; ``reload``, ``fix`` and ``abort`` read some of them alone.
    def _config(self) -> None:
        inputs.read_config(self)

    def _store(self) -> None:
        inputs.read_store(self)

    def _ledger(self) -> None:
        inputs.read_ledger(self)

    def _batch(self) -> None:
        inputs.read_batch(self)

    def _briefs(self) -> list[tuple[JsonObject, JsonObject]]:
        from harness.orchestration.ledger.ledger_ops import _load_dispatch

        batch = cast(JsonObject, self.batch)
        return [
            (entry, _load_dispatch(self.root, entry["dispatch_id"]))
            for entry in open_entries(batch)
        ]

    # -- the document ------------------------------------------------------------------------

    @property
    def resumable(self) -> bool:
        return all(check.status != "refused" for check in self.checks.values())

    def diagnostics(self) -> list[RecoveryDiagnostic]:
        return [item for name in CHECKS for item in self.checks[name].diagnostics]

    def document(self, session: RecoverySession | None = None) -> JsonObject:
        hidden = (session or RecoverySession()).skipped
        visible = [item for item in self.diagnostics() if item.id not in hidden]
        return {
            "contract": RECOVERY_CONTRACT,
            "batch_id": self.batch_id,
            "observed_at": _now(),
            "resumable": self.resumable,
            "lifecycle": None if self.batch is None else lifecycle_view(self.batch),
            "hold": None if self.hold is None else self.hold.to_dict(),
            "checks": [self.checks[name].to_dict(hidden) for name in CHECKS],
            "diagnostics": [item.to_dict() for item in visible],
            "skipped_advisories": sorted(hidden),
            "actions": self.actions(visible),
            "intent": read_intent(self.root, self.batch_id),
            "next": self.next_step(),
        }

    def fix_available(self) -> bool:
        """Whether the authored configuration has a safe normalization to write; a project
        without one gets none created."""
        authored = None if self.bundle is None else self.bundle["orchestration.json"]
        if authored is None or self.config_document is None:
            return False
        try:
            document: object = json.loads(authored)
        except ValueError:
            return False
        return document != self.config_document

    def actions(self, visible: list[RecoveryDiagnostic]) -> list[JsonObject]:
        advisories = [item for item in visible if item.advisory is not None]
        fix = self.fix_available()
        return [
            {
                "action": "fix",
                "available": fix,
                "reason": "the configuration has a safe normalization to apply"
                if fix
                else "no safe normalization: an error needs an authored edit",
            },
            {
                "action": "reload",
                "available": True,
                "reason": "re-read and validate the current configuration",
            },
            {
                "action": "resume",
                "available": self.resumable,
                "reason": "every check passed or resume reconciles it"
                if self.resumable
                else "a check refuses: resolve its diagnostics first",
            },
            {
                "action": "skip",
                "available": bool(advisories),
                "reason": "hide an allowlisted advisory for this session"
                if advisories
                else "no allowlisted advisory to hide",
            },
            {
                "action": "abort",
                "available": True,
                "reason": "leave recovery; nothing is abandoned, stopped or cleaned",
            },
        ]

    def next_step(self) -> JsonObject | None:
        if self.resumable:
            return {
                "command": f"recovery resume --batch {self.batch_id}",
                "reason": "every check passed or is reconciled by resume",
            }
        if self.checks["config"].status == "refused":
            if self.fix_available():
                command = "config validate --fix --dry-run"
            else:
                command = f"recovery reload --batch {self.batch_id}"
            return {
                "command": command,
                "reason": "the current configuration is invalid; edit it, then reload",
            }
        for name in CHECKS:
            for item in self.checks[name].diagnostics:
                if self.checks[name].status == "refused" and item.fatal:
                    return {"command": None, "reason": item.remedy or item.message}
        return None
