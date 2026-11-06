"""The inverse of `harness.health.report_json.to_json`: the console server sends the Diagnostics
report as that `--json` contract (schema version 1) and the TUI reads it back into a `Report`."""

from __future__ import annotations

from typing import cast

from ...health.model import CheckResult, Fix, Report, Status
from .home_snapshot import _bool, _int, _list, _optional, _str

SCHEMA_VERSION = 1
_REPORT_KEYS = frozenset(
    {"schema_version", "repo", "online", "summary", "checks", "fixes_applied"}
)
_CHECK_KEYS = frozenset({"id", "group", "status", "message", "fix"})
_STATUSES = frozenset({"ok", "warn", "fail", "skipped"})


def _keys(value: object, keys: frozenset[str], kind: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{kind}: unexpected fields")
    return {str(key): item for key, item in value.items()}


def _fix_from(value: object) -> Fix:
    found = _keys(value, frozenset({"text", "command"}), "Fix")
    return Fix(_str(found["text"]), _optional(found["command"], _str))


def _check_from(value: object) -> CheckResult:
    found = _keys(value, _CHECK_KEYS, "CheckResult")
    status = _str(found["status"])
    if status not in _STATUSES:
        raise ValueError(f"CheckResult: unknown status {status!r}")
    return CheckResult(
        id=_str(found["id"]),
        group=_str(found["group"]),
        status=cast(Status, status),
        message=_str(found["message"]),
        fix=_optional(found["fix"], _fix_from),
    )


def report_from_payload(payload: object) -> Report:
    """The report a `to_json` result describes; any schema break, including a summary that does
    not match the checks, is `ValueError`."""
    found = _keys(payload, _REPORT_KEYS, "Report")
    version = _int(found["schema_version"])
    if version != SCHEMA_VERSION:
        raise ValueError(f"unsupported health report schema: {version!r}")
    report = Report(
        schema_version=version,
        repo=_str(found["repo"]),
        online=_bool(found["online"]),
        checks=[_check_from(item) for item in _list(found["checks"])],
        fixes_applied=[_str(item) for item in _list(found["fixes_applied"])],
    )
    if found["summary"] != report.summary():
        raise ValueError("Report: summary does not match the checks")
    return report
