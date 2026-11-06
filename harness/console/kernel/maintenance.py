"""Read-only maintenance facts. Deletion policy belongs to harness.cleanup.

Textual-free: the console server collects a `MaintenanceView` and the TUI decodes its JSON
payload (`to_payload` / `from_payload`)."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from harness.cleanup import (
    CleanupPlan,
    WorktreeFact,
    plan_cleanup,
    plan_digest,
    worktree_facts,
)

from .home_snapshot import _fields, _int, _list, _optional, _str


@dataclass
class Size:
    bytes: int = 0
    files: int = 0


def path_size(path: Path) -> Size:
    """Count regular files without following symlinks or hiding inaccessible paths."""
    result = Size()

    def count(candidate: Path) -> None:
        info = candidate.lstat()
        if stat.S_ISREG(info.st_mode):
            result.bytes += info.st_size
            result.files += 1

    if path.is_symlink():
        return result
    if path.is_dir():

        def fail(error: OSError) -> None:
            raise error

        for parent, _, files in os.walk(path, followlinks=False, onerror=fail):
            for name in files:
                count(Path(parent) / name)
    else:
        count(path)
    return result


@dataclass
class CleanupSummary:
    plan: CleanupPlan
    categories: dict[str, Size] = field(default_factory=dict)

    @property
    def total(self) -> Size:
        return Size(
            sum(row.bytes for row in self.categories.values()),
            sum(row.files for row in self.categories.values()),
        )

    def to_payload(self) -> dict[str, object]:
        """The plan, its per-category sizes and the digest a confirmation binds to."""
        return {
            "plan": self.plan,
            "categories": {
                name: _size_payload(size) for name, size in self.categories.items()
            },
            "total": _size_payload(self.total),
            "items": len(self.plan["remove"]),
            "digest": plan_digest(self.plan),
        }

    @classmethod
    def from_payload(cls, payload: object) -> CleanupSummary:
        """The summary a `to_payload` result describes; any schema break — including a digest or
        a total that does not match the plan — is `ValueError`."""
        if not isinstance(payload, dict) or set(payload) != _SUMMARY_KEYS:
            raise ValueError("CleanupSummary: unexpected fields")
        plan = _plan_from(payload["plan"])
        categories = payload["categories"]
        if not isinstance(categories, dict):
            raise ValueError("CleanupSummary: categories is not an object")
        summary = cls(
            plan,
            {_str(name): _size_from(size) for name, size in categories.items()},
        )
        if (
            _str(payload["digest"]) != plan_digest(plan)
            or _int(payload["items"]) != len(plan["remove"])
            or _size_from(payload["total"]) != summary.total
        ):
            raise ValueError("CleanupSummary: digest, items or total do not match")
        return summary


_SUMMARY_KEYS = frozenset({"plan", "categories", "total", "items", "digest"})
_PLAN_KEYS = frozenset({"mode", "root", "min_age_hours", "remove", "skipped"})


def _size_payload(size: Size) -> dict[str, int]:
    return {"bytes": size.bytes, "files": size.files}


def _size_from(value: object) -> Size:
    found = _fields(value, Size)
    return Size(_int(found["bytes"]), _int(found["files"]))


def _string_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"not an object: {value!r}")
    return {_str(key): _str(item) for key, item in value.items()}


def _plan_from(value: object) -> CleanupPlan:
    if not isinstance(value, dict) or set(value) != _PLAN_KEYS:
        raise ValueError("CleanupPlan: unexpected fields")
    age = value["min_age_hours"]
    if isinstance(age, bool) or not isinstance(age, (int, float)):
        raise ValueError(f"not a number: {age!r}")
    remove = []
    for item in _list(value["remove"]):
        if not isinstance(item, dict) or not {"kind", "path"} <= set(item):
            raise ValueError(f"CleanupItem: bad item {item!r}")
        branch = item.get("branch")
        if branch is not None and not isinstance(branch, str):
            raise ValueError(f"CleanupItem: bad branch {branch!r}")
        remove.append(
            {
                str(key): field_value if key == "branch" else _str(field_value)
                for key, field_value in item.items()
            }
        )
    return cast(
        CleanupPlan,
        {
            "mode": _str(value["mode"]),
            "root": _str(value["root"]),
            "min_age_hours": age,
            "remove": remove,
            "skipped": [_string_map(item) for item in _list(value["skipped"])],
        },
    )


def summarize(plan: CleanupPlan) -> CleanupSummary:
    summary = CleanupSummary(plan)
    root = Path(plan["root"])
    for item in plan["remove"]:
        if item["kind"] not in ("directory", "file", "worktree"):
            continue
        path = Path(item["path"])
        parts = path.relative_to(root).parts
        if parts[0] == ".sandboxes":
            parts = parts[1:]
        category = (
            "/".join(parts[:2])
            if parts[0] == "runs" and len(parts) > 1 and parts[1] in ("tests", "qa")
            else parts[0]
        )
        size = path_size(path)
        row = summary.categories.setdefault(category, Size())
        row.bytes += size.bytes
        row.files += size.files
    return summary


@dataclass
class MaintenanceView:
    soft: CleanupSummary
    hard: CleanupSummary
    worktrees: list[WorktreeFact]
    worktree_error: str = ""
    tree_sizes: dict[Path, Size] = field(default_factory=dict)

    def to_payload(self) -> dict[str, object]:
        """The JSON-safe form a console server reply carries."""
        return {
            "soft": self.soft.to_payload(),
            "hard": self.hard.to_payload(),
            "worktrees": [
                {
                    "path": str(fact.path),
                    "branch": fact.branch,
                    "dirty": fact.dirty,
                    "reason": fact.reason,
                }
                for fact in self.worktrees
            ],
            "worktree_error": self.worktree_error,
            "tree_sizes": [
                {"path": str(path), "size": _size_payload(size)}
                for path, size in self.tree_sizes.items()
            ],
        }

    @classmethod
    def from_payload(cls, payload: object) -> MaintenanceView:
        """The view a `to_payload` result describes; any schema break is `ValueError`."""
        found = _fields(payload, cls)
        return cls(
            soft=CleanupSummary.from_payload(found["soft"]),
            hard=CleanupSummary.from_payload(found["hard"]),
            worktrees=[_worktree_from(item) for item in _list(found["worktrees"])],
            worktree_error=_str(found["worktree_error"]),
            tree_sizes=dict(_tree_size_from(item) for item in _list(found["tree_sizes"])),
        )


def _worktree_from(value: object) -> WorktreeFact:
    found = _fields(value, WorktreeFact)
    return WorktreeFact(
        path=Path(_str(found["path"])),
        branch=_optional(found["branch"], _str),
        dirty=_optional(found["dirty"], _int),
        reason=_str(found["reason"]),
    )


def _tree_size_from(value: object) -> tuple[Path, Size]:
    if not isinstance(value, dict) or set(value) != {"path", "size"}:
        raise ValueError(f"tree size: bad entry {value!r}")
    return Path(_str(value["path"])), _size_from(value["size"])


def load_maintenance(repo: Path) -> MaintenanceView:
    soft = summarize(plan_cleanup(repo, "soft"))
    hard = summarize(plan_cleanup(repo, "hard"))
    try:
        trees = worktree_facts(repo)
    except ValueError as exc:
        return MaintenanceView(soft, hard, [], str(exc))
    view = MaintenanceView(soft, hard, trees)
    for tree in trees:
        if tree.reason != "current checkout" and tree.path.is_relative_to(
            Path(hard.plan["root"])
        ):
            try:
                view.tree_sizes[tree.path] = path_size(tree.path)
            except OSError:
                pass  # Unknown size stays unavailable, never becomes zero.
    return view


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size / (1024 * 1024):.1f} MiB"


def summary_text(summary: CleanupSummary, language: str) -> str:
    total = summary.total
    lines = [
        f"{format_size(total.bytes)} · {total.files} "
        + ("файлов" if language == "ru" else "files"),
        *(
            f"{name}: {format_size(size.bytes)} · {size.files}"
            for name, size in summary.categories.items()
        ),
        ("Пропущено" if language == "ru" else "Skipped")
        + f": {len(summary.plan['skipped'])}",
    ]
    lines.extend(
        f"{item['kind']}: {item['path']}"
        for item in summary.plan["remove"]
        if item["kind"] in ("worktree", "container", "network")
    )
    for item in summary.plan["skipped"]:
        lines.append(f"○ {item['path']}: {reason_text(item['reason'], language)}")
    if not summary.plan["remove"]:
        lines.insert(
            0, "Временных файлов нет" if language == "ru" else "No temporary files"
        )
    return "\n".join(lines)


_REASONS_RU = {
    "current checkout": "текущий checkout",
    "not a direct managed worktree": "вне управляемого каталога worktree",
    "Git or ledger state unavailable": "Git или ledger недоступен",
    "referenced by an active batch": "используется активным batch",
    "unowned local branch": "ветка вне шаблона проекта",
    "worktree newer than minimum age": "worktree моложе 24 ч",
    "worktree status unavailable": "статус Git недоступен",
    "worktree has uncommitted changes": "есть незакоммиченные изменения",
    "local commits are not preserved on origin": "коммиты не сохранены на origin",
    "active or newer than minimum age": "активные данные или моложе 24 ч",
    "registered QA worktree or Git unavailable": "зарегистрированный QA worktree или Git недоступен",
    "not a local directory": "каталог вне локального хранилища",
    "Git unavailable": "Git недоступен",
    "worktree is not registered": "worktree не зарегистрирован",
}


def reason_text(reason: str, language: str) -> str:
    if not reason:
        return "Можно удалить" if language == "ru" else "Can remove"
    return _REASONS_RU.get(reason, reason) if language == "ru" else reason
