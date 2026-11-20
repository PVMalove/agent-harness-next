"""Предварительный просмотр и полное удаление харнесса из целевого проекта.

Удаляется всё, что устанавливают `init` и `adopt`: каталог `.harness/`, discovery-ссылки скиллов,
seed-файлы из шаблонов `harness/project/`, `AGENTS.md`, `CLAUDE.md` и строки харнесса в корневом
`.gitignore`. Всё, что проект мог изменить или создать сам (изменённые seed-файлы, `project.json`,
собственные скиллы, состояние ledger), перед удалением копируется в `.harness-uninstall-backup/`.
План строится без записи на диск; применение сверяет свежий план с показанным и требует
подтверждения `UNINSTALL`."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from harness import runtime_events
from harness.cleanup import _active_worktrees, _clear_read_only, _git
from harness.runtime_adapters import ADAPTER_ROOT, adapter_problem
from harness.health.hook_settings import ADAPTERS
from harness.health.project_files import (
    DISCOVERY_LINKS,
    HOOK_POLICY_REL,
    LOCK_REL,
    REGISTRY_REL,
    native_link_target,
)

PACKAGE = Path(__file__).resolve().parent
PROJECT_TEMPLATE_DIR = PACKAGE / "project"
CONFIRM_WORD = "UNINSTALL"
BACKUP_DIR = ".harness-uninstall-backup"
HARNESS_DIR = ".harness"
# `init` writes CLAUDE.md with exactly this text when the project has none.
CLAUDE_MD_SEED = "# Claude Code\n\n@AGENTS.md\n"
# Lines `init`/`adopt` append to the root .gitignore; the CLI imports them from here.
GITIGNORE_LINES = ("/docs/tasks/", "/.harness/.sandboxes/")
# Template folders `init`/`adopt` seed, in seeding order: (folder in harness/project, target in
# the project, seeded file suffixes). The CLI copies exactly these, so uninstall finds them all.
SEED_FOLDERS: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("instructions", ".harness/instructions", frozenset({".md"})),
    ("hooks", ".claude/hooks", frozenset({".sh", ".py"})),
    ("rules", ".claude/rules", frozenset({".md"})),
    ("agents", ".claude/agents", frozenset({".md"})),
)
# Seed target of the shared guides before #1249; `update` moves the guides found there.
LEGACY_INSTRUCTIONS_DIR = "docs/agents"
# Instructions of `harness/project/instructions/` that are managed files, not seeds: the CLI installs
# them into `.harness/instructions/` with their capability, and `update` overwrites them as any
# managed file (#814).
MANAGED_INSTRUCTIONS = frozenset({"project-memory.md", "container-executor.md"})
# Rules of `harness/project/rules/` that are managed files, not seeds: the language rules go into
# `.claude/rules/` of every install, `update` overwrites them as any managed file (#1249).
MANAGED_RULES = frozenset({"technical-english.md", "technical-russian.md"})
_MANAGED_TEMPLATES = {"instructions": MANAGED_INSTRUCTIONS, "rules": MANAGED_RULES}


def seed_sources(templates: Path, folder: str, suffixes: frozenset[str]) -> list[Path]:
    """The seed templates of one `SEED_FOLDERS` folder, without its managed files."""
    return [
        source
        for source in sorted((templates / folder).iterdir())
        if source.is_file()
        and source.suffix in suffixes
        and source.name not in _MANAGED_TEMPLATES.get(folder, frozenset())
    ]


# Regenerated or disposable content inside .harness that is never worth a backup.
_NO_BACKUP_PREFIXES = (".sandboxes/", ".venv/")
_NO_BACKUP_FILES = {
    LOCK_REL.relative_to(HARNESS_DIR).as_posix(),
    REGISTRY_REL.relative_to(HARNESS_DIR).as_posix(),
    HOOK_POLICY_REL.relative_to(HARNESS_DIR).as_posix(),
    ".gitignore",
    "orchestration.example.json",
}
# Directories removed at the end when the uninstall left them empty.
_PRUNE_DIRS = (
    ".claude/hooks",
    ".claude/rules",
    ".claude/agents",
    ".claude",
    ".codex",
    ".agents",
    LEGACY_INSTRUCTIONS_DIR,
    "docs",
)


class UninstallItem(TypedDict):
    """Удаляемый путь: `directory`, `file` или `link`; `backup` — копировать ли перед удалением."""

    kind: str
    path: str
    backup: bool


class UninstallPlan(TypedDict):
    """План удаления харнесса: что удаляется, что копируется и что пропущено."""

    root: str
    remove: list[UninstallItem]
    backup: list[str]
    runtime_events: list[str]
    gitignore_lines: list[str]
    skipped: list[dict[str, str]]
    blocked: str | None


class UninstallResult(TypedDict):
    """Итог удаления: удалённые пути, каталог резервной копии и ошибки."""

    removed: list[str]
    backup_dir: str | None
    failed: list[dict[str, str]]


def seed_templates() -> dict[str, bytes | None]:
    """Seed-файлы, которые пишут `init`/`adopt`, и их исходное содержимое.

    `None` — файл формируется из шаблона с подстановками (`AGENTS.md`), поэтому сравнить его
    не с чем и он всегда копируется в резервную копию."""
    seeds: dict[str, bytes | None] = {}
    for folder, target, suffixes in SEED_FOLDERS:
        for source in seed_sources(PROJECT_TEMPLATE_DIR, folder, suffixes):
            seeds[f"{target}/{source.name}"] = source.read_bytes()
    for adapter in ADAPTERS:
        seeds[adapter.config] = (PROJECT_TEMPLATE_DIR / adapter.template).read_bytes()
    seeds["CLAUDE.md"] = CLAUDE_MD_SEED.encode("utf-8")
    seeds["AGENTS.md"] = None
    return seeds


def _harness_backups(repo: Path, managed: set[str]) -> list[str]:
    """Файлы `.harness/`, которых нет в lock-файле: их создал или изменил проект.

    Seed-файлы внутри `.harness/` здесь не учитываются: их сверяет с шаблоном цикл seed-файлов."""
    root = repo / HARNESS_DIR
    backups: list[str] = []
    seeded = set(seed_templates())
    template = PROJECT_TEMPLATE_DIR / "project.schema.json"
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        inner = path.relative_to(root).as_posix()
        relative = f"{HARNESS_DIR}/{inner}"
        if (
            relative in managed
            or relative in seeded
            or inner in _NO_BACKUP_FILES
            or inner.startswith(_NO_BACKUP_PREFIXES)
            or "__pycache__" in path.parts
        ):
            continue
        if (
            inner == "project.schema.json"
            and path.read_bytes() == template.read_bytes()
        ):
            continue
        backups.append(relative)
    return backups


def _managed_files(repo: Path) -> dict[str, object]:
    """Снимок из `harness.lock`: путь → хэш; при отсутствии или порче lock-файла — пустой словарь."""
    try:
        lock = json.loads((repo / LOCK_REL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    files = lock.get("files") if isinstance(lock, dict) else None
    return dict(files) if isinstance(files, dict) else {}


def _adapter_removal_plan(
    repo: Path,
) -> tuple[list[UninstallItem], list[dict[str, str]]]:
    """Keep adapter paths whose ownership or unchanged contents cannot be proved."""
    root = repo / ADAPTER_ROOT
    if root.is_symlink():
        return [], [
            {"path": ADAPTER_ROOT, "reason": "symlink adapter target: preserved"}
        ]
    if not root.is_dir():
        return (
            (
                [],
                [
                    {
                        "path": ADAPTER_ROOT,
                        "reason": "non-directory adapter target: preserved",
                    }
                ],
            )
            if root.exists()
            else ([], [])
        )
    try:
        lock = json.loads((repo / LOCK_REL).read_text(encoding="utf-8"))
        hashes = lock.get("files") or {}
    except (OSError, ValueError, AttributeError):
        hashes = {}
    if not isinstance(hashes, dict):
        hashes = {}
    remove: list[UninstallItem] = []
    skipped: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir() and not path.is_symlink():
            continue
        relative = path.relative_to(repo).as_posix()
        problem = adapter_problem(repo, relative, hashes.get(relative))
        if problem:
            skipped.append({"path": relative, "reason": problem + ": preserved"})
        else:
            remove.append({"kind": "file", "path": relative, "backup": False})
    return remove, skipped


def plan_uninstall(repo: Path) -> UninstallPlan:
    """Построить план полного удаления харнесса без изменения файлов."""
    checkout = repo.expanduser().resolve()
    remove: list[UninstallItem] = []
    backup: list[str] = []
    skipped: list[dict[str, str]] = []
    blocked: str | None = None
    # Native configs keep their user entries; only the hooks Harness owns leave them.
    try:
        events = sorted(set(runtime_events.owned_configs(checkout).values()))
    except (OSError, ValueError):
        events = []
        skipped.append(
            {
                "path": runtime_events.OWNERSHIP.as_posix(),
                "reason": "владение runtime events не читается: нативные записи оставлены",
            }
        )

    harness_dir = checkout / HARNESS_DIR
    if harness_dir.is_dir():
        active = _active_worktrees(harness_dir)
        if active is None:
            blocked = "ledger оркестрации не читается: проверьте его перед удалением"
        elif active:
            blocked = "есть активные batch оркестрации: завершите или отмените их перед удалением"
        backup.extend(_harness_backups(checkout, set(_managed_files(checkout))))
        adapters, preserved = _adapter_removal_plan(checkout)
        if preserved:
            skipped.extend(preserved)
            remove.extend(adapters)
            for child in sorted(harness_dir.iterdir()):
                if child.name == "adapters":
                    continue
                kind = (
                    "link"
                    if child.is_symlink()
                    else "directory"
                    if child.is_dir()
                    else "file"
                )
                remove.append(
                    {
                        "kind": kind,
                        "path": child.relative_to(checkout).as_posix(),
                        "backup": False,
                    }
                )
        else:
            remove.append({"kind": "directory", "path": HARNESS_DIR, "backup": False})

    for relative, target in DISCOVERY_LINKS.items():
        path = checkout / relative
        if path.is_symlink() and os.readlink(path) == native_link_target(target):
            remove.append({"kind": "link", "path": relative, "backup": False})
        elif path.exists() or path.is_symlink():
            skipped.append(
                {
                    "path": relative,
                    "reason": "не ссылка харнесса: оставлен без изменений",
                }
            )

    for relative, pristine in seed_templates().items():
        path = checkout / relative
        if path.is_symlink() or not path.is_file():
            continue
        changed = pristine is None or path.read_bytes() != pristine
        if changed:
            backup.append(relative)
        # A seed inside .harness/ goes with that directory; a separate item would remove it twice.
        if not relative.startswith(f"{HARNESS_DIR}/"):
            remove.append({"kind": "file", "path": relative, "backup": changed})

    # Managed files outside .harness/ (the language rules in .claude/rules/) go one by one; a file
    # that differs from its snapshot hash is the project's edit and is backed up first.
    for relative, recorded in sorted(_managed_files(checkout).items()):
        path = checkout / relative
        if relative.startswith(f"{HARNESS_DIR}/") or path.is_symlink() or not path.is_file():
            continue
        changed = hashlib.sha256(path.read_bytes()).hexdigest() != recorded
        remove.append({"kind": "file", "path": relative, "backup": changed})
        if changed:
            backup.append(relative)

    gitignore = checkout / ".gitignore"
    lines: list[str] = []
    if gitignore.is_file():
        existing = set(gitignore.read_text(encoding="utf-8").splitlines())
        lines = [line for line in GITIGNORE_LINES if line in existing]

    return {
        "root": str(checkout),
        "remove": remove,
        "backup": sorted(backup),
        "runtime_events": events,
        "gitignore_lines": lines,
        "skipped": skipped,
        "blocked": blocked,
    }


def _remove_link(path: Path) -> None:
    """Удалить ссылку на каталог; в Windows ссылку на каталог снимает только `rmdir`."""
    try:
        path.unlink()
    except (IsADirectoryError, PermissionError):
        os.rmdir(path)


def _remove_directory(path: Path) -> None:
    """Удалить каталог целиком, в Windows — через путь расширенной длины."""
    target = (
        "\\\\?\\" + str(path)
        if os.name == "nt" and not str(path).startswith("\\\\?\\")
        else path
    )
    shutil.rmtree(target, onexc=_clear_read_only)


def apply_uninstall(
    repo: Path, plan: UninstallPlan, *, confirm: str | None = None
) -> UninstallResult:
    """Применить показанный план: сделать резервную копию, удалить файлы и навести порядок."""
    if confirm != CONFIRM_WORD:
        raise ValueError(f"uninstall requires confirm='{CONFIRM_WORD}'")
    checkout = repo.expanduser().resolve()
    fresh = plan_uninstall(checkout)
    if fresh["blocked"]:
        raise ValueError(fresh["blocked"])
    if (
        fresh["root"] != plan["root"]
        or fresh["remove"] != plan["remove"]
        or fresh["backup"] != plan["backup"]
    ):
        raise ValueError("uninstall plan changed; preview again before applying")

    backup_dir: Path | None = None
    if fresh["backup"]:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup_dir = checkout / BACKUP_DIR / stamp
        for relative in fresh["backup"]:
            target = backup_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(checkout / relative, target)

    removed: list[str] = []
    failed: list[dict[str, str]] = []
    if fresh["runtime_events"]:
        try:
            released = runtime_events.sync(checkout, release=True)
            removed.extend(f"{path}: runtime events" for path in released)
        except (OSError, ValueError) as exc:
            failed.append(
                {"path": runtime_events.OWNERSHIP.as_posix(), "reason": str(exc)}
            )
    for item in fresh["remove"]:
        path = checkout / item["path"]
        try:
            if item["kind"] == "link":
                _remove_link(path)
            elif item["kind"] == "directory":
                _remove_directory(path)
            else:
                path.unlink()
            removed.append(item["path"])
        except OSError as exc:
            failed.append({"path": item["path"], "reason": str(exc)})

    if fresh["gitignore_lines"]:
        gitignore = checkout / ".gitignore"
        kept = [
            line
            for line in gitignore.read_text(encoding="utf-8").splitlines()
            if line not in fresh["gitignore_lines"]
        ]
        gitignore.write_text(
            "\n".join(kept) + "\n" if kept else "", encoding="utf-8", newline="\n"
        )
        removed.append(".gitignore: " + ", ".join(fresh["gitignore_lines"]))

    for relative in _PRUNE_DIRS:
        directory = checkout / relative
        if (
            directory.is_dir()
            and not directory.is_symlink()
            and not any(directory.iterdir())
        ):
            directory.rmdir()

    # Worktrees of finished batches lived under .harness/.sandboxes: drop their registrations.
    # Best effort: a failed or unanswered prune is ignored; git prunes stale registrations later.
    _git(checkout, "worktree", "prune")
    return {
        "removed": removed,
        "backup_dir": str(backup_dir) if backup_dir is not None else None,
        "failed": failed,
    }
