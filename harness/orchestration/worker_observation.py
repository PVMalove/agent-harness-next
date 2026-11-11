"""Passive local worker evidence. No model calls, process control or lifecycle decisions."""

from __future__ import annotations

import socket
import os
import re
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import BinaryIO

from harness.orchestration.core.utils import JsonObject

PROTOCOL = "harness-worker-v1"
STARTUP_TIMEOUT_SECONDS = 120


def process_identity(pid: int) -> JsonObject | None:
    """Linux PID plus boot/start identity; other hosts remain explicitly unobserved."""
    if not sys.platform.startswith("linux") or isinstance(pid, bool) or pid < 1:
        return None
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {
            "pid": pid,
            "host": socket.gethostname(),
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "start_time": fields[19],
            "pid_namespace": os.readlink(f"/proc/{pid}/ns/pid"),
        }
    except (OSError, IndexError, ValueError):
        return None


def observe_process(receipt: object, dispatch_id: object) -> JsonObject | None:
    """Only a bound, local process identity can prove termination. Reused PIDs stay unknown."""
    if not isinstance(receipt, Mapping) or receipt.get("protocol") != PROTOCOL:
        return None
    unknown = {
        "state": "unknown",
        "source": "local-process",
        "reason": "unverified process identity",
    }
    if receipt.get("dispatch_id") != dispatch_id or not receipt.get("launch_id"):
        return {**unknown, "reason": "launch receipt does not match dispatch"}
    identity = receipt.get("process")
    if not isinstance(identity, Mapping):
        return unknown
    pid = identity.get("pid")
    if (
        not sys.platform.startswith("linux")
        or identity.get("host") != socket.gethostname()
        or not isinstance(pid, int)
        or isinstance(pid, bool)
        or pid < 1
        or not isinstance(identity.get("start_time"), str)
        or not str(identity.get("start_time", "")).isdigit()
        or not isinstance(identity.get("boot_id"), str)
    ):
        return unknown
    try:
        if identity.get("pid_namespace") != os.readlink("/proc/self/ns/pid"):
            return {**unknown, "reason": "worker belongs to another PID namespace"}
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        if boot != identity["boot_id"]:
            return {**unknown, "reason": "host rebooted since launch"}
        try:
            fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        except FileNotFoundError:
            return {
                "state": "stopped",
                "source": "local-process",
                "reason": "bound process no longer exists",
            }
        if fields[19] != identity["start_time"]:
            return {**unknown, "reason": "PID belongs to another process"}
        return {
            "state": "stopped" if fields[0] in {"Z", "X"} else "live",
            "source": "local-process",
            "reason": "bound process exited"
            if fields[0] in {"Z", "X"}
            else "bound process exists",
        }
    except (OSError, ValueError, IndexError):
        return {**unknown, "reason": "process observation is unavailable"}


def observe_worker(
    receipt: object, dispatch_id: object, *, repo: Path | None = None
) -> JsonObject | None:
    """Prefer a bound supervisor exit result; otherwise require local kernel evidence."""
    if (
        repo is not None
        and isinstance(receipt, dict)
        and receipt.get("dispatch_id") == dispatch_id
    ):
        terminal = read_terminal(repo, receipt)
        if terminal is not None:
            return {
                "state": "stopped",
                "source": "runtime-supervisor",
                "reason": "bound runtime exit was recorded",
                **terminal,
            }
    return observe_process(receipt, dispatch_id)


def redact_visible(text: str) -> str:
    """Scrub configured secret values as well as common credential assignments before storage."""
    from harness.orchestration.core.utils import _sanitise

    secret_key = re.compile(
        r"(?:token|secret|password|credential|api.?key|authorization)", re.I
    )
    for key, value in os.environ.items():
        if len(value) >= 4 and secret_key.search(key):
            text = text.replace(value, "<redacted>")
    text = re.sub(
        r"(?i)((?:[\w-]*(?:api[_-]?key|token|secret|password|authorization)[\w-]*)[\"']?\s*[:=]\s*[\"']?)([^\s,;\"'}]+)",
        r"\1<redacted>",
        text,
    )
    return _sanitise(text)[:8192]


def visible_events(record: object) -> list[JsonObject]:
    """Allowlisted stream-json text/tool names only; never thinking, inputs or raw JSON."""
    if not isinstance(record, dict):
        return []

    def row(kind: str, text: object) -> list[JsonObject]:
        return (
            [{"kind": kind, "text": redact_visible(text)}]
            if isinstance(text, str) and text
            else []
        )

    kind = record.get("type")
    if kind == "harness-event" and record.get("kind") in {
        "output",
        "tool",
        "tool-result",
        "result",
        "error",
        "system",
        "permission",
        "stderr",
    }:
        return row(record["kind"], record.get("text"))
    if kind in {"assistant", "user"}:
        message = record.get("message", {})
        content = message.get("content", []) if isinstance(message, dict) else []
        events: list[JsonObject] = []
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    events.extend(row("output", block.get("text")))
                elif block.get("type") == "tool_use":
                    events.extend(row("tool", block.get("name")))
                elif block.get("type") == "tool_result" and isinstance(
                    block.get("content"), str
                ):
                    events.extend(row("tool-result", block["content"]))
        return events
    if kind == "result":
        return row(
            "error" if record.get("is_error") else "result", record.get("result")
        )
    if kind == "system" and record.get("subtype") == "init":
        return row("system", "Runtime session connected")
    if (
        kind == "control_request"
        and isinstance(record.get("request"), dict)
        and record["request"].get("subtype") == "can_use_tool"
    ):
        return row(
            "permission",
            "Native permission required: "
            + str(record["request"].get("tool_name", "unknown")),
        )
    if kind == "permission_request":
        return row(
            "permission",
            "Native runtime permission request; respond through the runtime",
        )
    # Partial text duplicates the final assistant message. In particular, thinking deltas and
    # provider metadata are not a second channel to display hidden reasoning or credentials.
    return []


def read_events(
    repo: Path, receipt: object, offset: int = 0, extra_roots: tuple[Path, ...] = ()
) -> JsonObject:
    """Bounded incremental local log reader; never interprets output as executable commands.

    The log must be under shared logs storage or one of ``extra_roots``, such as the runtime's
    executions directory that holds a container worker's stream (#1014)."""
    import json
    from harness.storage import storage_path

    empty: JsonObject = {
        "events": [],
        "next_offset": offset,
        "stream_state": "unavailable",
        "reset": False,
    }
    if not isinstance(receipt, dict) or not isinstance(receipt.get("log_path"), str):
        return {**empty, "stream_reason": "adapter supplied no structured event log"}
    path = Path(receipt["log_path"]).resolve()
    allowed = (
        storage_path(repo, "logs").resolve(),
        *(r.resolve() for r in extra_roots),
    )
    if not any(path.is_relative_to(root) for root in allowed):
        return {**empty, "stream_reason": "event log is outside shared logs storage"}
    try:
        with path.open("rb") as stream:
            size = stream.seek(0, 2)
            start = offset if offset <= size else 0
            reset = offset > size
            if size - start > 65536:
                start = size - 65536
                reset = True
            stream.seek(start)
            if start and reset:
                stream.readline(
                    65536
                )  # never parse the middle of an oversized/rotated record
            raw = stream.read(65536)
            complete = raw.rfind(b"\n") + 1
            next_offset = stream.tell() - len(raw) + complete
        events: list[JsonObject] = []
        for line in raw[:complete].splitlines():
            try:
                events.extend(visible_events(json.loads(line)))
            except (ValueError, UnicodeDecodeError):
                continue  # incomplete/foreign output is not trusted text to expose
        return {
            "events": events[-200:],
            "next_offset": next_offset,
            "stream_state": "connected" if size else "waiting",
            "reset": reset,
            "log_path": str(path),
            "last_event_age_seconds": max(0, int(time.time() - path.stat().st_mtime))
            if size
            else None,
        }
    except OSError:
        return {
            **empty,
            "stream_reason": "event stream is missing or unreadable; worker outcome is independent",
        }


def read_terminal(repo: Path, receipt: object) -> JsonObject | None:
    """A supervisor's bound exit result is separate from a completion report or its acceptance."""
    import json
    from harness.storage import storage_path

    if (
        not isinstance(receipt, dict)
        or receipt.get("protocol") != PROTOCOL
        or not isinstance(receipt.get("terminal_path"), str)
    ):
        return None
    terminal = Path(receipt["terminal_path"]).resolve()
    log = Path(receipt.get("log_path", "")).resolve()
    if (
        not terminal.is_relative_to(storage_path(repo, "logs", "workers").resolve())
        or terminal.parent != log.parent
        or terminal.name != "terminal.json"
        or terminal.parent.name != receipt.get("launch_id")
    ):
        return None
    try:
        with terminal.open("rb") as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            return None
        record = json.loads(raw)
        code = record.get("exit_code")
        if (
            record.get("dispatch_id") != receipt.get("dispatch_id")
            or record.get("launch_id") != receipt.get("launch_id")
            or not isinstance(code, int)
            or isinstance(code, bool)
        ):
            return None
        return {"exit_code": code, "source": "runtime-supervisor"}
    except (OSError, ValueError, TypeError, AttributeError):
        return None


# Step pages for console clients. Reading is ``open("rb")`` and ``stat`` only: no lock, no write.
STEP_REASON_MESSAGES = {
    "no_log": "Worker supplied no observable log; worker outcome is independent",
    "log_missing": "Worker log does not exist yet; worker outcome is independent",
    "log_unreadable": "Worker log is unreadable; worker outcome is independent",
    "log_outside_storage": "Worker log is outside harness storage and is not read",
    "log_unrecognised": (
        "Worker log has no recognised Codex sections at its start, so its text is not shown;"
        " worker outcome is independent"
    ),
}
MAX_STEP_LINE_BYTES = 1024 * 1024
MAX_PAGE_RAW_BYTES = 4 * 1024 * 1024
PLAIN_HEADER_WINDOW_BYTES = 65536
_PLAIN_TOOL_SECTIONS = ("exec", "apply_patch", "mcp tool call")
_PLAIN_SECTIONS = ("codex", "thinking", "user", "tokens used", *_PLAIN_TOOL_SECTIONS)
OMITTED_STEP_KIND = "omitted"
_OMITTED_RESERVE_BYTES = 160
_MAX_ESCAPED_CHAR_BYTES = 12  # a surrogate pair escaped as two ``\uXXXX`` sequences
_UNKNOWN_SECTION = "?"  # any section outside the allowlist; it is never visible
# A stamped line, or any line that opens with ``[`` or an escape sequence, starts a section.
_PLAIN_STAMPED = re.compile(r"\[[^\]\n]*\]\s*(?P<rest>.*)")
_PLAIN_BARE_LABEL = re.compile(r"[A-Za-z][\w .-]*:")


def unavailable_page(source: str, reason: str, offset: int = 0) -> JsonObject:
    """An explicit observation state; it never decides or changes the worker outcome."""
    return {
        "source": source,
        "structure": "available" if source == "structured" else "unavailable",
        "state": "unavailable",
        "reason": reason,
        "message": STEP_REASON_MESSAGES[reason],
        "steps": [],
        "offset": max(0, offset),
        "reset": False,
        "more": False,
        "last_step_age_seconds": None,
    }


def structured_log_path(
    repo: Path, receipt: object, dispatch_id: object
) -> tuple[Path | None, str | None]:
    """A bound runtime receipt names its event log; only the project's logs storage is read.

    ``repo`` is the main checkout that owns the storage; the path is built without asking Git,
    so observation starts no process."""
    if (
        not isinstance(receipt, Mapping)
        or receipt.get("protocol") != PROTOCOL
        or receipt.get("dispatch_id") != dispatch_id
        or not isinstance(receipt.get("log_path"), str)
        or not receipt["log_path"]
    ):
        return None, "no_log"
    path = Path(receipt["log_path"]).resolve()
    if not path.is_relative_to((repo / ".harness/.sandboxes/logs").resolve()):
        return None, "log_outside_storage"
    return path, None


def external_log_path(
    repo: Path, dispatch: Mapping[str, object]
) -> tuple[Path | None, str | None]:
    """The standalone adapters' rule: ``<staging>/../../worker-logs/<dispatch_id>.log``."""
    staging = dispatch.get("report_staging_path")
    dispatch_id = dispatch.get("dispatch_id")
    if not isinstance(staging, str) or not staging or not isinstance(dispatch_id, str):
        return None, "no_log"
    path = (
        Path(staging).parent.parent / "worker-logs" / f"{dispatch_id}.log"
    ).resolve()
    allowed = (repo / ".harness/.sandboxes/scratch/worker-logs").resolve()
    if path.parent != allowed:
        return None, "log_outside_storage"
    return path, None


def _structured_line(line: bytes, _section: list[str]) -> list[JsonObject]:
    import json

    try:
        return visible_events(json.loads(line))
    except (ValueError, UnicodeDecodeError):
        return []  # incomplete/foreign output is not trusted text to expose


def _plain_header(text: str) -> str | None:
    """The section a line starts, or ``None`` for a body line.

    Fail closed: only a line that is exactly the ``codex`` header opens the visible section.
    Every other stamped, bracketed, escaped or labelled line starts a hidden section."""
    line = text.strip()
    if not line:
        return None
    stamped = _PLAIN_STAMPED.fullmatch(line)
    if stamped:
        rest = stamped.group("rest").strip()
        for name in _PLAIN_SECTIONS:
            if name != "codex" and re.fullmatch(
                re.escape(name) + r"(?:[:\s].*)?", rest
            ):
                return name
    elif line[0] in "[\x1b":
        return _UNKNOWN_SECTION
    else:
        rest = line
        if rest in _PLAIN_SECTIONS or rest.removesuffix(":") in _PLAIN_TOOL_SECTIONS:
            return rest.removesuffix(":")
    if rest == "codex":
        return "codex"
    if stamped or _PLAIN_BARE_LABEL.fullmatch(rest):
        return _UNKNOWN_SECTION
    return None


def _plain_segments(line: bytes) -> list[str]:
    """A carriage return starts a new segment, so it cannot hide a header inside a line."""
    return line.decode("utf-8", errors="replace").removesuffix("\n").split("\r")


def _plain_line(line: bytes, section: list[str]) -> list[JsonObject]:
    """Fail closed: only agent-message lines and tool section names are visible."""
    import json

    steps: list[JsonObject] = []
    for text in _plain_segments(line):
        header = _plain_header(text)
        if header is not None:
            section[0] = header
            if header in _PLAIN_TOOL_SECTIONS:
                steps.append({"kind": "tool", "text": header})
            continue
        if section[0] != "codex" or not text.strip():
            continue
        try:
            if isinstance(json.loads(text), (dict, list)):
                continue
        except ValueError:
            pass
        visible = redact_visible(text)
        if visible:
            steps.append({"kind": "log", "text": visible})
    return steps


def _plain_headers_before(reader: BinaryIO, offset: int) -> list[str]:
    """Section headers in a bounded window before ``offset``, in order.

    Only whole lines are classified; an oversized line is a hidden-section boundary, as in a
    forward read."""
    start = max(0, offset - PLAIN_HEADER_WINDOW_BYTES)
    reader.seek(start)
    window = reader.read(offset - start)
    lines = window.split(b"\n")
    if start:
        lines = lines[1:]  # the first line may be cut in the middle
    headers: list[str] = []
    for raw in lines:
        if len(raw) > MAX_STEP_LINE_BYTES:
            headers.append(_UNKNOWN_SECTION)
            continue
        headers.extend(
            header
            for text in _plain_segments(raw)
            if (header := _plain_header(text)) is not None
        )
    return headers


def _plain_section_before(reader: BinaryIO, offset: int) -> str:
    """The last header in a bounded window before ``offset`` sets the section."""
    headers = _plain_headers_before(reader, offset)
    return headers[-1] if headers else ""


def _step_cost(step: JsonObject) -> int:
    import json

    # ASCII-escaped JSON is an upper bound of a step's bytes in any reply.
    return len(json.dumps(step)) + 1


def _fit_record(found: list[JsonObject], budget: int) -> list[JsonObject]:
    """One record whose steps exceed a whole page: its leading steps that fit, the first one cut
    if even it does not fit, and an ``omitted`` step counting what is not shown in full. The
    page then moves past the record, so a client always makes progress."""
    room = budget - _OMITTED_RESERVE_BYTES
    kept: list[JsonObject] = []
    used = 0
    for step in found:
        cost = _step_cost(step)
        if used + cost > room:
            break
        kept.append(step)
        used += cost
    cut = 0
    if not kept:
        first = found[0]
        frame = _step_cost({**first, "text": ""})
        chars = max(0, (room - frame) // _MAX_ESCAPED_CHAR_BYTES)
        kept = [{**first, "text": str(first["text"])[:chars]}]
        cut = 1
    hidden = len(found) - len(kept) + cut
    return [
        *kept,
        {
            "kind": OMITTED_STEP_KIND,
            "text": f"One log record exceeds the page budget: {hidden} of {len(found)}"
            " steps are not shown in full",
        },
    ]


def _plain_log_unrecognised(reader: BinaryIO, size: int) -> bool:
    """A non-empty plain log whose head holds no Codex section header has no visible text."""
    return bool(size) and not any(
        header in _PLAIN_SECTIONS
        for header in _plain_headers_before(
            reader, min(size, PLAIN_HEADER_WINDOW_BYTES)
        )
    )


def _skip_line(reader: BinaryIO) -> bool:
    """Read past the rest of the current line; ``False`` if it has no end yet."""
    while True:
        chunk = reader.readline(MAX_STEP_LINE_BYTES)
        if not chunk:
            return False
        if chunk.endswith(b"\n"):
            return True


def _line_start(reader: BinaryIO, offset: int) -> int | None:
    """The first line start at or after ``offset``, or ``None`` while that line is unfinished.

    A client offset is never trusted as a line boundary: a line whose start was not seen is
    skipped whole, never parsed."""
    if not offset:
        return 0
    reader.seek(offset - 1)
    if reader.read(1) == b"\n":
        return offset
    return reader.tell() if _skip_line(reader) else None


def _read_step_page(
    path: Path,
    offset: int,
    budget: int,
    source: str,
    parse_line: Callable[[bytes, list[str]], list[JsonObject]],
) -> JsonObject:
    """``budget`` bounds the encoded size of the page's steps, so the reply stays bounded."""
    offset = max(0, offset)
    try:
        with path.open("rb") as stream:
            size = stream.seek(0, 2)
            reset = offset > size
            position = 0 if reset else offset
            if source == "plain" and _plain_log_unrecognised(stream, size):
                return {
                    **unavailable_page(source, "log_unrecognised", position),
                    "reset": reset,
                }
            aligned = _line_start(stream, position)
            position = position if aligned is None else aligned
            section = [
                _plain_section_before(stream, position)
                if source == "plain" and position
                else ""
            ]
            # An unfinished line under the offset: wait at the offset, read nothing.
            stream.seek(size if aligned is None else position)
            steps: list[JsonObject] = []
            used = 0
            more = False
            consumed = 0
            while True:
                line = stream.readline(MAX_STEP_LINE_BYTES + 1)
                if not line:
                    break
                if not line.endswith(b"\n"):
                    if len(line) <= MAX_STEP_LINE_BYTES:
                        break  # the writer has not finished this line yet
                    while line and not line.endswith(b"\n"):
                        line = stream.readline(MAX_STEP_LINE_BYTES)
                    if not line:
                        break  # oversized and unfinished: wait at its start
                    position = stream.tell()  # oversized records are never parsed
                    # Its section is unknown, so it hides what follows until a header.
                    section[0] = _UNKNOWN_SECTION
                    continue
                found = parse_line(line, section)
                cost = sum(_step_cost(step) for step in found)
                if used + cost > budget:
                    if steps:
                        more = True
                        break
                    found = _fit_record(found, budget)
                    cost = budget  # a cut record fills its page
                steps.extend(found)
                used += cost
                position = stream.tell()
                consumed += len(line)
                if used >= budget or consumed >= MAX_PAGE_RAW_BYTES:
                    more = position < size
                    break
            age = max(0, int(time.time() - path.stat().st_mtime)) if size else None
    except FileNotFoundError:
        return unavailable_page(source, "log_missing", offset)
    except OSError:
        return unavailable_page(source, "log_unreadable", offset)
    return {
        "source": source,
        "structure": "available" if source == "structured" else "unavailable",
        "state": "connected" if size else "waiting",
        "reason": None,
        "message": "",
        "steps": steps,
        "offset": position,
        "reset": reset,
        "more": more,
        "last_step_age_seconds": age,
    }


def read_structured_steps(path: Path, offset: int, budget: int) -> JsonObject:
    """One page of allowlisted stream-json steps from a byte offset."""
    return _read_step_page(path, offset, budget, "structured", _structured_line)


def read_plain_steps(path: Path, offset: int, budget: int) -> JsonObject:
    """One page of a plain worker log tail; structure is explicitly unavailable."""
    return _read_step_page(path, offset, budget, "plain", _plain_line)
