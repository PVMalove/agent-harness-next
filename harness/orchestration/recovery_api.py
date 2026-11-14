"""The shared recovery status and action API of the core, the CLI and the Harness console.

One structured contract (``recoveryStatus.v1``) says what keeps a batch from going on and what may
be done about it.  Every check names its diagnostics with a pointer, the redacted expected and
received values and a suggestion, so a console or a CI log shows them without parsing stderr:

* ``status`` is read-only: it takes no lock and writes nothing;
* ``reload`` re-reads and re-validates the current configuration and never starts a worker;
* ``fix`` previews or applies the configuration's safe normalization through the configuration
  transaction, and never resumes anything;
* ``skip`` hides one allowlisted advisory for one session; a fatal diagnostic is never skipped;
* ``abort`` records that the operator left recovery: it abandons no batch, stops no worker and
  cleans no worktree;
* ``resume`` (``recovery_commands``) re-checks the batch, releases its hold and reacts to the
  observed execution of its open dispatches.

Every action except ``skip`` records its durable intent before it runs, so a console that is
cancelled, reaches end of input or is interrupted shows the same status after a restart.  The hold
and the intent are recovery records of the runtime store (``recovery/hold/<batch_id>.json``,
``recovery/intent/<batch_id>.json``, ADR 0026): Python decides them, the Rust store writes them
through ``state.write``, and the file-ledger epoch keeps neither, so there every command refuses
with the ``harness-runtime migrate`` remedy.  Nothing here reads standard input, waits for a
terminal or imports a UI toolkit.  An exception that is not a refusal is never shown as a
configuration problem: it is an ``internal-error`` diagnostic with a correlation ID.

The parts live in the ``harness.orchestration.recovery_status`` package; this module re-exports
them, so its importers keep one name.
"""

from __future__ import annotations

from harness.orchestration.recovery_status.actions import (
    abort as abort,
    fix as fix,
    reload as reload,
    skip as skip,
    status as status,
)
from harness.orchestration.recovery_status.batch_state import (
    lifecycle_view as lifecycle_view,
    stopped_route as stopped_route,
)
from harness.orchestration.recovery_status.inputs import (
    hold_reason_of as hold_reason_of,
)
from harness.orchestration.recovery_status.intent import (
    INTENT_CONTRACT as INTENT_CONTRACT,
    INTENT_DIRECTORY as INTENT_DIRECTORY,
    Intent as Intent,
    intent_relative as intent_relative,
    read_intent as read_intent,
    tracked as tracked,
)
from harness.orchestration.recovery_status.model import (
    ACTIONS as ACTIONS,
    ADVISORIES as ADVISORIES,
    CHECK_STATUSES as CHECK_STATUSES,
    CHECKS as CHECKS,
    DIAGNOSTIC_CODES as DIAGNOSTIC_CODES,
    INTENT_STATUSES as INTENT_STATUSES,
    OUTCOMES as OUTCOMES,
    RECOVERY_CONTRACT as RECOVERY_CONTRACT,
    CheckResult as CheckResult,
    RecoveryDiagnostic as RecoveryDiagnostic,
    RecoveryInternalError as RecoveryInternalError,
    RecoveryInterrupted as RecoveryInterrupted,
    RecoverySession as RecoverySession,
)
from harness.orchestration.recovery_status.resume import (
    resume as resume,
)
from harness.orchestration.recovery_status.runtime import (
    RECOVERY_FEATURES as RECOVERY_FEATURES,
    RECOVERY_PROTOCOL as RECOVERY_PROTOCOL,
    runtime_hello as runtime_hello,
    runtime_problems as runtime_problems,
)
from harness.orchestration.recovery_status.survey import (
    Survey as Survey,
    open_entries as open_entries,
)
