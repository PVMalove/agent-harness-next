"""The recovery vocabulary of the registry, the diagnostics of a check and the check results."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from harness.diagnostics import Diagnostic, pointer, safe_value
from harness.errors import INTERNAL_INVARIANT_REMEDY, HarnessError
from harness.orchestration.core.utils import CoordinatorError, JsonObject
from harness.orchestration.ledger.ledger_ops import LedgerBusyError
from harness.orchestration.operational_hold import OperationalHoldError, sanitize_detail
from harness.orchestration.runtime_client import RuntimeClientError

RECOVERY_CONTRACT = "recoveryStatus.v1"
ACTIONS = ("fix", "reload", "resume", "skip", "abort")
# The reconciliation checks, in the order they run.
CHECKS = (
    "config",
    "store",
    "ledger",
    "batch",
    "lifecycle",
    "runtime",
    "snapshot",
    "context",
    "compatibility",
    "operation",
    "liveness",
    "attention",
    "approval",
)
CHECK_STATUSES = ("passed", "pending", "reconciled", "refused", "skipped")
DIAGNOSTIC_CODES = (
    "config-invalid",
    "config-advisory",
    "runtime-compatibility",
    "integrity-failure",
    "stale-evidence",
    "ambiguous-effect",
    "concurrency-conflict",
    "storage-unavailable",
    "live-worker",
    "attention-open",
    "approval-required",
    "approval-stale",
    "terminal-refusal",
    "internal-error",
)
OUTCOMES = ("done", "refused")
INTENT_STATUSES = ("pending", "done", "refused", "interrupted", "aborted")
# The closed allowlist of advisories ``skip`` may hide for one session.
ADVISORIES = ("config-normalized",)
# The diagnostic code of each error code of the runtime protocol (ADR 0021, section 3).
_RUNTIME_CODES = {
    "runtime_unavailable": "storage-unavailable",
    "store_busy": "storage-unavailable",
    "revision_conflict": "concurrency-conflict",
    "idempotency_conflict": "concurrency-conflict",
    "invariant_violation": "integrity-failure",
    "not_found": "integrity-failure",
    "protocol_unsupported": "runtime-compatibility",
    "internal": "internal-error",
}


@dataclass(frozen=True)
class RecoveryDiagnostic:
    """One finding of a check: what is wrong, where, and what would make it right."""

    code: str
    check: str
    message: str
    remedy: str | None = None
    location: str | None = None
    expected: object = None
    received: object = None
    suggestion: object = None
    severity: str = "error"
    advisory: str | None = None
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if (
            self.code not in DIAGNOSTIC_CODES
            or self.check not in CHECKS
            or self.severity not in ("error", "warning")
            or (self.advisory is not None and self.advisory not in ADVISORIES)
            or (self.advisory is not None and self.severity != "warning")
        ):
            raise ValueError("unregistered recovery diagnostic")

    @property
    def id(self) -> str:
        """A stable identifier a console selects the diagnostic by."""
        key = json.dumps(
            [self.code, self.check, self.location, self.message, self.advisory]
        )
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    @property
    def fatal(self) -> bool:
        return self.severity == "error"

    def to_dict(self) -> JsonObject:
        return {
            "id": self.id,
            "code": self.code,
            "check": self.check,
            "message": sanitize_detail(self.message),
            "remedy": None if self.remedy is None else sanitize_detail(self.remedy),
            "pointer": self.location,
            "expected": safe_value(self.expected),
            "received_redacted": safe_value(self.received),
            "suggestion": safe_value(self.suggestion),
            "severity": self.severity,
            "fatal": self.fatal,
            "advisory": self.advisory,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_config(cls, item: Diagnostic) -> RecoveryDiagnostic:
        """A configuration diagnostic of the #682 boundary, kept with its pointer and values."""
        warning = item.severity == "warning"
        return cls(
            "config-advisory" if warning else "config-invalid",
            "config",
            f"{item.file}: {item.message}",
            remedy="run 'recovery fix' to preview the safe normalization"
            if item.recoverable
            else "edit .harness/orchestration.json at the pointer, then run 'recovery reload'",
            location=pointer(item.parts),
            expected=item.expected,
            received=item.received,
            suggestion=item.suggestion,
            severity=item.severity,
            advisory="config-normalized"
            if warning and item.code == "config-normalized"
            else None,
        )

    @classmethod
    def from_error(cls, check: str, exc: HarnessError) -> RecoveryDiagnostic:
        """A refusal of the core or the runtime, kept with its own remedy; never a
        configuration typo."""
        if isinstance(exc, RuntimeClientError):
            code = _RUNTIME_CODES.get(exc.code, "integrity-failure")
        elif isinstance(exc, RecoveryInternalError):
            code = "internal-error"
        elif isinstance(exc, OperationalHoldError) and exc.code in DIAGNOSTIC_CODES:
            code = exc.code
        elif isinstance(exc, LedgerBusyError):
            code = "storage-unavailable"
        else:
            code = "integrity-failure"
        return cls(code, check, exc.message, remedy=exc.remedy)


@dataclass
class CheckResult:
    """The result of one reconciliation check."""

    check: str
    status: str = "passed"
    detail: str = ""
    diagnostics: list[RecoveryDiagnostic] = field(default_factory=list)
    evidence: JsonObject | None = None

    def add(self, diagnostic: RecoveryDiagnostic, *, status: str | None = None) -> None:
        self.diagnostics.append(diagnostic)
        if status is not None:
            self.set(status)

    def set(self, status: str) -> None:
        """Raise the status; a refusal is never lowered by a later finding."""
        order = {"passed": 0, "skipped": 0, "reconciled": 1, "pending": 2, "refused": 3}
        if order[status] >= order[self.status]:
            self.status = status

    def to_dict(self, hidden: frozenset[str] = frozenset()) -> JsonObject:
        return {
            "check": self.check,
            "status": self.status,
            "detail": sanitize_detail(self.detail) if self.detail else "",
            "evidence": self.evidence,
            "diagnostics": [
                item.to_dict() for item in self.diagnostics if item.id not in hidden
            ],
        }


@dataclass(frozen=True)
class RecoverySession:
    """What one console or CLI session chose to hide; never persisted, never a policy."""

    skipped: frozenset[str] = frozenset()


class RecoveryInterrupted(CoordinatorError):
    """The operator cancelled, reached end of input or interrupted an action; its intent says so."""


class RecoveryInternalError(CoordinatorError):
    """An exception that is not a refusal: an internal invariant, never a configuration typo.
    It keeps the failure code, the step and the diagnostics of the action."""

    def __init__(self, action: str, exc: BaseException, correlation_id: str) -> None:
        detail = sanitize_detail(f"{type(exc).__name__}: {exc}") or type(exc).__name__
        super().__init__(
            f"recovery {action} hit an internal invariant violation (correlation "
            f"{correlation_id}): {detail}; nothing was decided on it",
            remedy=f"{INTERNAL_INVARIANT_REMEDY}; correlation {correlation_id}",
        )
        self.code = "internal-error"
        self.step = f"recovery-{action}"
        self.correlation_id = correlation_id
        self.diagnostics: JsonObject = {
            "detail": detail,
            "correlation_id": correlation_id,
            "internal_invariant": True,
        }
