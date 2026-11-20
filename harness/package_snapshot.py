# Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
# SPDX-License-Identifier: BUSL-1.1
# Licensed under the Business Source License 1.1 (BSL-1.1).
# Commercial use, sale, or use in commercial application development is strictly
# prohibited without prior written permission from the copyright holder.
# Removing or altering this header is prohibited and voids all license rights.

"""Package snapshot of the harness source tree: capabilities, package files, the project lock, the
snapshot diff and the seed templates.

Shared by the packager CLI (`harness/bin/harness.py`) and the console. Importing it has no side
effects, and every failure raises `PackageError` instead of exiting the process; the CLI prints it
the way its own `fail()` does.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from harness import skill_invocation
from harness.errors import HarnessError
from harness.health.hook_settings import ADAPTERS
from harness.health.model import JsonObject
from harness.health.project_files import (
    JSON_READ_ERRORS,
    LOCK_REL,
    canonical_capability,
    digest,
    file_digest,
)
from harness.runtime_adapters import adapter_problem, is_adapter
from harness.storage import storage_path
from harness.uninstall import MANAGED_RULES, SEED_FOLDERS, seed_sources

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent
CAPABILITIES_FILE = PACKAGE / "CAPABILITIES.json"
VERSION_FILE = PACKAGE / "VERSION"
# How printed remedies invoke the CLI: the running interpreter and the CLI script, runnable as shown.
HARNESS_CLI = (sys.executable, str(PACKAGE / "bin" / "harness.py"))
DEFAULT_CAPABILITY = "project-foundation"
PROJECT_TEMPLATE_DIR = PACKAGE / "project"
PACKAGE_REMEDY = "fix the file or the capability entry named in the message, then retry"


class PackageError(HarnessError):
    """The harness package or a project's harness.lock cannot be read or resolved."""


def version() -> str:
    """Получить текущую версию пакета harness из файла VERSION."""
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def capabilities() -> dict[str, JsonObject]:
    """Загрузить и распарсить каталог возможностей из CAPABILITIES.json."""
    try:
        data: object = json.loads(CAPABILITIES_FILE.read_text(encoding="utf-8"))
    except JSON_READ_ERRORS as exc:
        raise PackageError(
            f"cannot read {CAPABILITIES_FILE}: {exc}", remedy=PACKAGE_REMEDY
        )
    if not isinstance(data, dict):
        raise PackageError(
            "CAPABILITIES.json must contain an object", remedy=PACKAGE_REMEDY
        )
    return data


def selected_capabilities(names: list[str] | None) -> list[str]:
    """Нормализовать и проверить переданный список возможностей."""
    selected = [canonical_capability(name) for name in names or [DEFAULT_CAPABILITY]]
    catalog = capabilities()
    unknown = [name for name in selected if name not in catalog]
    if unknown:
        raise PackageError(
            f"unknown capabilities: {', '.join(unknown)}", remedy=PACKAGE_REMEDY
        )
    return list(dict.fromkeys(selected))


def _resolve_skill_source(entry: str) -> Path:
    """Найти исходный каталог скилла в репозитории harness."""
    source = ROOT / "skills" / entry
    if not (source / "SKILL.md").is_file():
        raise PackageError(
            f"missing skill: skills/{entry}/SKILL.md", remedy=PACKAGE_REMEDY
        )
    return source


def _resolve_resource_source(entry: str) -> Path:
    """Найти исходный путь ресурса возможности в репозитории harness."""
    source = PACKAGE / entry
    if not source.is_dir() and not source.is_file():
        raise PackageError(
            f"missing capability resource: harness/{entry}", remedy=PACKAGE_REMEDY
        )
    return source


def resolve_capability_skills(
    name: str, catalog: dict[str, JsonObject], _stack: tuple[str, ...] = ()
) -> dict[str, Path]:
    """Разрешить возможность в словарь {имя_скилла: путь_к_источнику}.

    Обрабатывает наследование `extends`, переопределения `overrides` и дополнения `additions`.
    """
    name = canonical_capability(name)
    if name in _stack:
        raise PackageError(
            f"capability cycle: {' -> '.join(_stack + (name,))}", remedy=PACKAGE_REMEDY
        )
    definition = catalog[name]
    resolved: dict[str, Path] = {}

    extends = definition.get("extends")
    if extends:
        if extends not in catalog:
            raise PackageError(
                f"capability {name!r} extends unknown capability {extends!r}",
                remedy=PACKAGE_REMEDY,
            )
        resolved.update(resolve_capability_skills(extends, catalog, _stack + (name,)))

    for entry in definition.get("skills") or []:
        source = _resolve_skill_source(entry)
        resolved[source.name] = source

    for skill_name, entry in (definition.get("overrides") or {}).items():
        if skill_name not in resolved:
            raise PackageError(
                f"capability {name!r} overrides unknown skill {skill_name!r} (not in {extends!r})",
                remedy=PACKAGE_REMEDY,
            )
        resolved[skill_name] = _resolve_skill_source(entry)

    for entry in definition.get("additions") or []:
        source = _resolve_skill_source(entry)
        if source.name in resolved:
            raise PackageError(
                f"capability {name!r} addition {source.name!r} collides with an inherited skill",
                remedy=PACKAGE_REMEDY,
            )
        resolved[source.name] = source

    return resolved


def resolve_capability_resources(
    name: str, catalog: dict[str, JsonObject], _stack: tuple[str, ...] = ()
) -> dict[str, Path]:
    """Разрешить управляемые не-скилловые ресурсы для возможности и её родителей.

    Ресурсы сохраняют свой относительный путь при развёртывании в проектной директории `.harness/`.
    """
    name = canonical_capability(name)
    if name in _stack:
        raise PackageError(
            f"capability cycle: {' -> '.join(_stack + (name,))}", remedy=PACKAGE_REMEDY
        )
    definition = catalog[name]
    resolved: dict[str, Path] = {}

    extends = definition.get("extends")
    if extends:
        if extends not in catalog:
            raise PackageError(
                f"capability {name!r} extends unknown capability {extends!r}",
                remedy=PACKAGE_REMEDY,
            )
        resolved.update(
            resolve_capability_resources(extends, catalog, _stack + (name,))
        )

    for entry in definition.get("resources") or []:
        resolved[entry] = _resolve_resource_source(entry)

    return resolved


def selected_skills(names: list[str]) -> list[Path]:
    """Получить список путей ко всем скиллам, входящим в выбранные возможности."""
    catalog = capabilities()
    paths: list[Path] = []
    seen_names: dict[str, Path] = {}
    for capability in names:
        for skill_name, source in resolve_capability_skills(
            capability, catalog
        ).items():
            if skill_name in seen_names and seen_names[skill_name] != source:
                raise PackageError(
                    f"duplicate skill name {skill_name!r}: {seen_names[skill_name]} and {source}",
                    remedy=PACKAGE_REMEDY,
                )
            if skill_name not in seen_names:
                seen_names[skill_name] = source
                paths.append(source)
    return paths


def selected_resources(names: list[str]) -> list[Path]:
    """Получить список путей ко всем ресурсам, входящим в выбранные возможности."""
    catalog = capabilities()
    paths: list[Path] = []
    seen_destinations: dict[Path, Path] = {}
    for capability in names:
        for source in resolve_capability_resources(capability, catalog).values():
            destination = source.relative_to(PACKAGE)
            if (
                destination in seen_destinations
                and seen_destinations[destination] != source
            ):
                raise PackageError(
                    f"duplicate capability resource {destination}: "
                    f"{seen_destinations[destination]} and {source}",
                    remedy=PACKAGE_REMEDY,
                )
            if destination not in seen_destinations:
                seen_destinations[destination] = source
                paths.append(source)
    return paths


def _packageable(path: Path) -> bool:
    """Пропустить локальные артефакты сборки, байт-код и кэши при пакетировании."""
    return path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"


# Managed agent instructions: the source in the project templates, the target in `.harness/` (#814).
INSTRUCTIONS_SOURCE = PACKAGE / "project" / "instructions"
INSTRUCTIONS_TARGET = ".harness/instructions"
# Managed language rules: the source next to the seed rules, the target in `.claude/rules/` (#1249).
RULES_SOURCE = PACKAGE / "project" / "rules"
RULES_TARGET = ".claude/rules"


def _resource_target(source: Path) -> Path:
    """Where a capability resource file is installed: an instruction into `.harness/instructions/`,
    any other file at its path below `.harness/`."""
    if source.parent == INSTRUCTIONS_SOURCE:
        return Path(INSTRUCTIONS_TARGET) / source.name
    return Path(".harness") / source.relative_to(PACKAGE)


def package_files(
    names: list[str], explicit: set[str] | None = None
) -> dict[str, bytes]:
    """Сформировать словарь относительных целевых путей и байтового содержимого файлов пакета."""
    # Языковые правила ставятся в любую установку, вне каталога capability: runtime грузит их
    # из `.claude/rules/`, Codex читает по указателю из `AGENTS.md` (#1249).
    result: dict[str, bytes] = {
        f"{RULES_TARGET}/{name}": (RULES_SOURCE / name).read_bytes()
        for name in sorted(MANAGED_RULES)
    }
    for source in selected_skills(names):
        for path in sorted(source.rglob("*")):
            if not _packageable(path):
                continue
            relative = path.relative_to(source)
            target = Path(".harness/skills") / source.name / relative
            result[target.as_posix()] = path.read_bytes()
        if explicit and source.name in explicit:
            root = f".harness/skills/{source.name}"
            skill_path = f"{root}/SKILL.md"
            codex_path = f"{root}/agents/openai.yaml"
            try:
                result[skill_path] = skill_invocation.restrict_frontmatter(
                    result[skill_path]
                )
                result[codex_path] = skill_invocation.restrict_codex(
                    result.get(codex_path, b"")
                )
            except ValueError as exc:
                raise PackageError(
                    f"cannot set explicit invocation for {source.name}: {exc}",
                    remedy=PACKAGE_REMEDY,
                )
    for source in selected_resources(names):
        if source.is_file():
            if _packageable(source):
                result[_resource_target(source).as_posix()] = source.read_bytes()
            continue
        for path in sorted(source.rglob("*")):
            if not _packageable(path):
                continue
            relative = path.relative_to(source)
            target = Path(".harness") / source.relative_to(PACKAGE) / relative
            result[target.as_posix()] = path.read_bytes()
    return result


def render(template: str, values: dict[str, str]) -> str:
    """Подставить значения плейсхолдеров {{KEY}} в шаблонную строку."""
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def load_lock(repo: Path) -> JsonObject | None:
    """Загрузить и распарсить файл блокировки .harness/harness.lock репозитория."""
    path = repo / LOCK_REL
    if not path.is_file():
        return None
    try:
        data: object = json.loads(path.read_text(encoding="utf-8"))
    except JSON_READ_ERRORS as exc:
        raise PackageError(f"cannot read {path}: {exc}", remedy=PACKAGE_REMEDY)
    if not isinstance(data, dict):
        raise PackageError(
            f"cannot read {path}: expected a JSON object", remedy=PACKAGE_REMEDY
        )
    return data


def snapshot_diff(repo: Path, override: list[str] | None = None) -> JsonObject:
    """Сравнить установленный снимок файлов с эталонным пакетом возможностей."""
    lock = load_lock(repo)
    if lock is None:
        return {"state": "missing", "detail": "no .harness/harness.lock"}

    selected = selected_capabilities(override or lock.get("capabilities"))
    try:
        explicit = skill_invocation.requested_skills(lock)
    except ValueError as exc:
        raise PackageError(str(exc), remedy=PACKAGE_REMEDY)
    current = package_files(selected, explicit)
    previous: dict[str, str] = lock.get("files") or {}
    added: list[str] = []
    missing: list[str] = []
    changed: list[str] = []
    local: list[str] = []
    conflict: list[str] = []
    retired: list[str] = []

    for relative, data in current.items():
        package_hash = digest(data)
        disk_hash = file_digest(repo / relative)
        old_hash = previous.get(relative)
        if is_adapter(relative) and adapter_problem(repo, relative, old_hash):
            conflict.append(relative)
        elif old_hash is None:
            added.append(relative)
        elif disk_hash is None:
            missing.append(relative)
        elif disk_hash == package_hash:
            continue
        elif old_hash == package_hash:
            local.append(relative)
        elif disk_hash == old_hash:
            changed.append(relative)
        else:
            conflict.append(relative)

    for relative, old_hash in previous.items():
        if relative in current:
            continue
        disk_hash = file_digest(repo / relative)
        if disk_hash is None:
            continue
        if disk_hash == old_hash:
            retired.append(relative)
        else:
            conflict.append(relative)

    state = "clean"
    if added or missing or changed or local or conflict or retired:
        state = "drift"
    return {
        "state": state,
        "package_version": version(),
        "installed_version": lock.get("package_version"),
        "capabilities": selected,
        "added": sorted(added),
        "missing": sorted(missing),
        "package_changed": sorted(changed),
        "local_changed": sorted(local),
        "conflict": sorted(set(conflict)),
        "retired": sorted(retired),
    }


HARNESS_RUNTIME_GITIGNORE = """# Generated harness runtime data
.sandboxes/
.venv
config_versions/
config-versions/
"""


def seed_template_sources(*, orchestration_enabled: bool) -> dict[str, Path]:
    sources = {
        f"{target}/{source.name}": source
        for folder, target, suffixes in SEED_FOLDERS
        for source in seed_sources(PROJECT_TEMPLATE_DIR, folder, suffixes)
    }
    sources.update(
        {
            adapter.config: PROJECT_TEMPLATE_DIR / adapter.template
            for adapter in ADAPTERS
        }
    )
    sources[".harness/project.schema.json"] = (
        PROJECT_TEMPLATE_DIR / "project.schema.json"
    )
    if orchestration_enabled:
        sources[".harness/orchestration.json"] = PACKAGE / "orchestration.example.json"
    return sources


def seed_template_files(repo: Path, *, orchestration_enabled: bool) -> dict[str, bytes]:
    """Seed-файлы, которые `update` может перезаписать: путь от корня проекта -> эталон из шаблона."""
    files = {
        relative: source.read_bytes()
        for relative, source in seed_template_sources(
            orchestration_enabled=orchestration_enabled
        ).items()
    }
    scratch = storage_path(repo, "scratch", ".gitignore")
    # A linked checkout shares scratch with its main checkout. Seeding this worker must not
    # turn a shared path into a ../ write or fail while relativizing that outside path.
    if scratch.is_relative_to(repo):
        files[scratch.relative_to(repo).as_posix()] = (
            PROJECT_TEMPLATE_DIR / "scratch/.gitignore"
        ).read_bytes()
    files[".harness/.gitignore"] = HARNESS_RUNTIME_GITIGNORE.encode("utf-8")
    return files


def seed_differing(repo: Path) -> list[str]:
    """Существующие seed-файлы проекта, которые отличаются от шаблона."""
    templates = seed_template_files(
        repo, orchestration_enabled=(repo / ".harness/orchestration.json").exists()
    )
    differing: list[str] = []
    for relative, content in templates.items():
        path = repo / relative
        if path.is_file() and path.read_bytes() != content:
            differing.append(relative)
    return sorted(differing)
