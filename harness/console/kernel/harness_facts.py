"""What the harness installed in a repository, read from `.harness/harness.lock` and the skills
directory. Textual-free: the console server collects it and the TUI decodes its JSON payload."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .home_snapshot import _bool, _fields, _int, _list, _str
from .json_fields import strings, text


@dataclass(frozen=True)
class HarnessState:
    """What is installed in the repository."""

    installed: bool
    installed_version: str
    capabilities: tuple[str, ...]
    skills: int
    managed_files: int
    updated_at: str
    orchestration: bool

    def to_payload(self) -> dict[str, object]:
        """The JSON-safe form a console server reply carries."""
        return {**asdict(self), "capabilities": list(self.capabilities)}

    @classmethod
    def from_payload(cls, payload: object) -> HarnessState:
        """The state a `to_payload` result describes; any schema break is `ValueError`."""
        found = _fields(payload, cls)
        return cls(
            installed=_bool(found["installed"]),
            installed_version=_str(found["installed_version"]),
            capabilities=tuple(_str(item) for item in _list(found["capabilities"])),
            skills=_int(found["skills"]),
            managed_files=_int(found["managed_files"]),
            updated_at=_str(found["updated_at"]),
            orchestration=_bool(found["orchestration"]),
        )


def harness_state(repo: Path) -> HarnessState:
    lock_path = repo / ".harness" / "harness.lock"
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = None
    skills_dir = repo / ".harness" / "skills"
    skills = (
        sum(1 for path in skills_dir.iterdir() if (path / "SKILL.md").is_file())
        if skills_dir.is_dir()
        else 0
    )
    if not isinstance(payload, dict):
        return HarnessState(False, "", (), skills, 0, "", False)
    files = payload.get("files")
    updated = datetime.fromtimestamp(lock_path.stat().st_mtime, tz=timezone.utc)
    return HarnessState(
        installed=True,
        installed_version=text(payload.get("package_version"), "?"),
        capabilities=tuple(strings(payload.get("capabilities"))),
        skills=skills,
        managed_files=len(files) if isinstance(files, dict) else 0,
        updated_at=updated.strftime("%Y-%m-%d %H:%M UTC"),
        orchestration=(
            repo / ".harness" / "orchestration" / "coordinator.py"
        ).is_file(),
    )
