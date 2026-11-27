"""What the runtime observes of a supervised execution, as plain data (#1296): a worker process
or container, or the containers of a QA run. Pure: the caller reads the runtime and the files;
`execution_facts` does that for the console server and the TUI."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

from .json_fields import text
from .protocol import ID_BYTES, MESSAGE_BYTES, _clip

# The last lines of an execution's stderr a summary carries: an adapter that fails before its
# first event writes only there.
MAX_STDERR_LINES = 5


@dataclass(frozen=True)
class ExecutionSummary:
    """What the runtime observes of a supervised execution (a process or a container): its
    state, engine and image, the deadline, the exit, whether its objects were removed and the
    tail of its stderr. Fields the runtime did not report are "" or None."""

    kind: str
    state: str
    engine: str
    image: str
    container_id: str
    deadline: str
    observed_at: str
    exit_code: int | None
    stopped_by: str
    oom_killed: bool | None
    teardown: str
    stderr_tail: tuple[str, ...]

    def to_wire(self) -> dict[str, object]:
        return {**asdict(self), "stderr_tail": list(self.stderr_tail)}


def execution_summary(
    execution: Mapping[str, object],
    teardown: Mapping[str, object] | None,
    stderr_tail: Sequence[str],
) -> ExecutionSummary:
    """The summary of one execution record of the runtime, its ``teardown.json`` and the last
    lines of its stderr, already redacted by the caller."""
    launch = execution.get("launch")
    launch = launch if isinstance(launch, Mapping) else {}
    images = launch.get("images")
    image = ""
    if isinstance(images, Mapping):
        image = ", ".join(text(value) for value in images.values() if text(value))
    observation = execution.get("observation")
    observation = observation if isinstance(observation, Mapping) else {}
    exit_ = execution.get("exit")
    exit_ = exit_ if isinstance(exit_, Mapping) else {}
    code = exit_.get("code")
    oom = exit_.get("oom_killed")
    removed = teardown.get("removed") if teardown else None
    return ExecutionSummary(
        kind=_clip(text(execution.get("kind")), ID_BYTES),
        state=_clip(text(execution.get("state")), ID_BYTES),
        engine=_clip(text(execution.get("engine")), ID_BYTES),
        image=_clip(image, MESSAGE_BYTES),
        container_id=_clip(text(execution.get("container_id")), ID_BYTES),
        deadline=_clip(text(execution.get("execution_deadline")), ID_BYTES),
        observed_at=_clip(text(observation.get("observed_at")), ID_BYTES),
        exit_code=code if isinstance(code, int) and not isinstance(code, bool) else None,
        stopped_by=_clip(text(exit_.get("stopped_by")), ID_BYTES),
        oom_killed=oom if isinstance(oom, bool) else None,
        teardown=""
        if teardown is None
        else ("removed" if removed is True else _clip(text(teardown.get("state")) or "recorded", ID_BYTES)),
        stderr_tail=tuple(
            _clip(line, MESSAGE_BYTES) for line in stderr_tail[-MAX_STDERR_LINES:]
        ),
    )
