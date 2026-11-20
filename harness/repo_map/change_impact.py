"""ChangeImpact: затронутые модули и тесты по diff `base..candidate` и графу импортов Repo Map.

Функция строит граф в процессе через `ParserBackend.parse` и `graph.build_graph`, а не через CLI
Repo Map с бюджетом токенов: отсечение по бюджету потеряло бы тесты. Результат — `ImpactSet` по
ADR 0023, раздел 1. Всё, чего граф не видит, попадает в `unknown`, и вызывающий расширяет выбор до
полного набора, а не сужает его.
"""

from __future__ import annotations

import fnmatch
import re
import tomllib
from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from harness.repo_map.backend import BundleParserBackend, ParseOutcome, ParserBackend
from harness.repo_map.bundle_worker import FileFacts
from harness.repo_map.git_source import blob_contents, run_git, tracked_paths
from harness.repo_map.graph import build_graph
from harness.repo_map.policy import RepoMapPolicy, path_allowed

# Причины `unknown`; вызывающий код ветвится по ним, поэтому это закрытый список.
UNKNOWN_BUILD_CONFIG = "build-config-changed"
UNKNOWN_CAPABILITIES = "capabilities-or-skills-changed"
UNKNOWN_NON_PYTHON = "non-python-file"
UNKNOWN_OUTSIDE_GRAPH = "outside-graph"
UNKNOWN_PARSE_FAILED = "parse-failed"
UNKNOWN_REMOVED_REFERENCED = "removed-module-referenced"
UNKNOWN_DYNAMIC_IMPORT = "dynamic-import"
UNKNOWN_OVER_THRESHOLD = "related-tests-over-threshold"
UNKNOWN_GRAPH_DEGRADED = "graph-degraded"
UNKNOWN_UNSEEN_IMPORTER = "unseen-importer"

# Манифесты и конфиги сборки и проверок: их изменение влияет на каждый тест.
_BUILD_CONFIG_NAMES = frozenset(
    {"pyproject.toml", "uv.lock", "Makefile", "conftest.py"}
)
_BUILD_CONFIG_GLOBS = (".github/*", "scripts/verify.py", "scripts/verification/*")
_CAPABILITIES_GLOBS = ("harness/CAPABILITIES.json", "skills/*")
# Признаки динамического импорта в фактах парсера.
_DYNAMIC_IMPORT_MODULES = ("importlib", "runpy", "pkgutil")
_DYNAMIC_IMPORT_NAMES = frozenset({"__import__", "import_module"})

_STATUSES = {
    "A": "added",
    "M": "modified",
    "T": "modified",
    "D": "deleted",
    "R": "renamed",
}


@dataclass(frozen=True)
class ChangedPath:
    """Путь из diff: `added`, `modified`, `deleted` или `renamed`; для переименования — и прежний путь."""

    status: str
    path: str
    old_path: str | None = None


@dataclass(frozen=True)
class UnknownReason:
    """Причина, по которой влияние изменения неизвестно: код, путь (или пустая строка) и пояснение."""

    code: str
    path: str
    detail: str


@dataclass(frozen=True)
class ImpactSet:
    """Влияние изменения: пути diff, затронутые модули, связанные тесты и причины `unknown`."""

    changed: tuple[ChangedPath, ...]
    impacted_modules: tuple[str, ...]
    related_tests: tuple[str, ...]
    unknown: tuple[UnknownReason, ...]

    def to_json(self) -> dict[str, object]:
        """Представление для brief и отчёта."""
        return {
            "changed": [
                {"status": item.status, "path": item.path, "old_path": item.old_path}
                for item in self.changed
            ],
            "impacted_modules": list(self.impacted_modules),
            "related_tests": list(self.related_tests),
            "unknown": [
                {"code": item.code, "path": item.path, "detail": item.detail}
                for item in self.unknown
            ],
        }


@dataclass(frozen=True)
class _Graph:
    """Граф импортов одного коммита: обратные рёбра, факты и статусы разбора Python-файлов.

    `blind` — tracked-файлы Python, чьих импортов граф не видит: их скрывает политика Repo Map либо
    парсер не вернул факты (`too_large`, ошибка разбора).
    """

    importers: dict[str, set[str]]
    facts: dict[str, FileFacts]
    paths: frozenset[str]
    degraded: str | None = None
    blind: tuple[str, ...] = ()
    parsed: ParseOutcome | None = None


def is_test_path(path: str) -> bool:
    """Тестовый файл Python: `test_*.py` или `*_test.py`; вспомогательные модули тестов — не тесты."""
    name = PurePosixPath(path).name
    return name.endswith(".py") and (
        name.startswith("test_") or name.endswith("_test.py")
    )


def _diff(repo: Path, base: str, candidate: str, timeout: int) -> list[ChangedPath]:
    """Разобрать `git diff -M --name-status -z base candidate`."""
    raw = run_git(
        repo, timeout, "diff", "-M", "--name-status", "-z", base, candidate
    ).decode("utf-8", "surrogateescape")
    tokens = [token for token in raw.split("\0") if token]
    changed: list[ChangedPath] = []
    position = 0
    while position < len(tokens):
        code = tokens[position][0]
        if code == "R":
            changed.append(
                ChangedPath("renamed", tokens[position + 2], tokens[position + 1])
            )
            position += 3
        else:
            changed.append(
                ChangedPath(_STATUSES.get(code, "modified"), tokens[position + 1])
            )
            position += 2
    return sorted(changed, key=lambda item: (item.path, item.status))


def _graph(
    repo: Path, commit: str, backend: ParserBackend, policy: RepoMapPolicy
) -> _Graph:
    """Граф импортов коммита; деградация парсера или лимит файлов дают `degraded` с причиной."""
    tracked = tracked_paths(repo, commit, policy.timeout_seconds)
    paths = [path for path in tracked if path_allowed(path, policy)]
    if len(paths) > policy.max_files:
        return _Graph(
            {},
            {},
            frozenset(),
            f"{len(paths)} policy-approved files exceed repo_map_policy.max_files={policy.max_files}",
        )
    parsed = backend.parse(commit, paths)
    if not parsed.applied:
        return _Graph({}, {}, frozenset(), parsed.reason)
    importers = _importers(parsed, policy)
    blind = sorted(
        {
            path
            for path in tracked
            if path.endswith(".py") and path not in parsed.records
        }
        | {
            path
            for path, record in parsed.records.items()
            if path.endswith(".py") and record["parser_status"] != "ok"
        }
    )
    return _Graph(
        importers,
        parsed.facts,
        frozenset(parsed.records),
        blind=tuple(blind),
        parsed=parsed,
    )


def _importers(parsed: ParseOutcome, policy: RepoMapPolicy) -> dict[str, set[str]]:
    """Обратные рёбра импорта: цель — файлы, которые её импортируют."""
    edges = build_graph(
        parsed.records,
        parsed.facts,
        parsed.diagnostics,
        policy,
        parsed.extension_grammars,
    )
    importers: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if edge["kind"] == "import":
            importers[edge["target"]].add(edge["source"])
    return dict(importers)


def _base_graph(
    repo: Path,
    base: str,
    graph: _Graph,
    changed: list[ChangedPath],
    backend: ParserBackend,
    policy: RepoMapPolicy,
) -> _Graph:
    """Граф импортов `base` без повторного разбора всего репозитория.

    Неизменённый файл одинаков на `base` и в кандидате, поэтому его записи и факты берутся из графа
    кандидата; на `base` разбираются только прежние версии изменённых, удалённых и переименованных
    файлов. Так удаление или переименование не удваивает стоимость графа под lock ledger.
    """
    candidate = graph.parsed
    if candidate is None:
        return _Graph({}, {}, frozenset(), "candidate graph is unavailable")
    new_paths = {item.path for item in changed if item.status != "deleted"}
    old_paths = [
        old
        for item in changed
        if item.status != "added"
        and path_allowed(old := item.old_path or item.path, policy)
    ]
    parsed = backend.parse(base, old_paths)
    if not parsed.applied:
        return _Graph({}, {}, frozenset(), parsed.reason)
    records = {
        path: dict(record)
        for path, record in candidate.records.items()
        if path not in new_paths
    } | parsed.records
    facts = {
        path: record
        for path, record in candidate.facts.items()
        if path not in new_paths
    } | parsed.facts
    merged = ParseOutcome(
        True,
        parsed.reason,
        {},
        records,
        facts,
        list(parsed.diagnostics),
        candidate.extension_grammars,
    )
    return _Graph(_importers(merged, policy), facts, frozenset(records), parsed=merged)


def _module_name(path: str) -> str:
    """Имя, под которым другой файл импортирует модуль: stem файла или имя пакета `__init__.py`."""
    pure = PurePosixPath(path)
    return pure.parent.name if pure.stem == "__init__" else pure.stem


def _unseen_importers(
    repo: Path, commit: str, graph: _Graph, closure: set[str], timeout: int
) -> list[UnknownReason]:
    """Скрытые от графа файлы, которые могут импортировать модуль замыкания.

    Граф не знает их импортов, поэтому файл с именем модуля замыкания в тексте считается возможным
    импортёром: его тесты не попадают в `related_tests`, и вызывающий расширяет выбор до полного.
    Совпадение по слову консервативно: лишнее срабатывание даёт `full`, а не пропущенный тест.
    """
    names = {_module_name(path) for path in closure} - {""}
    if not names or not graph.blind:
        return []
    pattern = re.compile(r"\b(?:" + "|".join(map(re.escape, sorted(names))) + r")\b")
    contents = blob_contents(repo, commit, list(graph.blind), timeout)
    reasons: list[UnknownReason] = []
    for path in graph.blind:
        content = contents.get(path)
        if content is None:
            reasons.append(
                UnknownReason(UNKNOWN_UNSEEN_IMPORTER, path, "content is unreadable")
            )
        elif match := pattern.search(content.decode("utf-8", "replace")):
            reasons.append(
                UnknownReason(
                    UNKNOWN_UNSEEN_IMPORTER,
                    path,
                    f"not in the import graph and names {match.group(0)!r}",
                )
            )
    return reasons


_PATH_DETAILS = {
    UNKNOWN_BUILD_CONFIG: "build or verification config",
    UNKNOWN_CAPABILITIES: "capability catalog or skill",
}


def path_unknown_code(path: str) -> str | None:
    """Код `unknown`, который следует из одного пути без графа: конфиг сборки или capabilities.

    Правило `non-python-file` сюда не входит. Копию правил держит hook `impact-first-touch`
    (`harness/project/hooks/change_impact_hooks.py`); tests/core/test_change_impact_hooks.py сверяет её.
    """
    name = PurePosixPath(path).name
    if name in _BUILD_CONFIG_NAMES or any(
        fnmatch.fnmatchcase(path, pattern) for pattern in _BUILD_CONFIG_GLOBS
    ):
        return UNKNOWN_BUILD_CONFIG
    if any(fnmatch.fnmatchcase(path, pattern) for pattern in _CAPABILITIES_GLOBS):
        return UNKNOWN_CAPABILITIES
    return None


def _config_unknown(item: ChangedPath) -> list[UnknownReason]:
    """Причины `unknown`, которые следуют из одного лишь пути: конфиги, capabilities, не-Python."""
    reasons: list[UnknownReason] = []
    for path in (item.path, *(p for p in (item.old_path,) if p)):
        code = path_unknown_code(path)
        if code is not None:
            reasons.append(UnknownReason(code, path, _PATH_DETAILS[code]))
        elif not path.endswith(".py"):
            reasons.append(
                UnknownReason(
                    UNKNOWN_NON_PYTHON, path, "not covered by the import graph"
                )
            )
    return reasons


def _closure(seeds: set[str], importers: dict[str, set[str]]) -> set[str]:
    """Обратное транзитивное замыкание: сами seeds и все, кто импортирует их прямо или через цепочку."""
    seen = set(seeds)
    queue = deque(sorted(seeds))
    while queue:
        for importer in sorted(importers.get(queue.popleft(), ())):
            if importer not in seen:
                seen.add(importer)
                queue.append(importer)
    return seen


def _uses_dynamic_import(facts: FileFacts) -> bool:
    """Файл импортирует `importlib`-подобный модуль, `import_module` или вызывает `__import__`."""
    return any(
        imported["module"].split(".")[0] in _DYNAMIC_IMPORT_MODULES
        or _DYNAMIC_IMPORT_NAMES & set(imported["names"])
        for imported in facts["imports"]
    ) or bool(_DYNAMIC_IMPORT_NAMES & set(facts["references"]))


def compute_change_impact(
    repo: Path,
    base: str,
    candidate: str,
    *,
    backend: ParserBackend | None = None,
    policy: RepoMapPolicy | None = None,
    max_related_tests: int | None = None,
) -> ImpactSet:
    """Вычислить `ImpactSet` для diff `base..candidate`.

    `changed` — добавленные, изменённые, удалённые и переименованные пути. `impacted_modules` —
    Python-модули, изменённые или импортирующие изменённые прямо либо транзитивно по рёбрам импорта
    графа кандидата; `related_tests` — тестовые файлы того же замыкания, без отсечения по числу
    изменённых файлов. Удалённый или переименованный модуль, который импортировали на `base`, даёт
    `unknown`, а его импортёры попадают в замыкание. Недоступный парсер даёт `graph-degraded`:
    без графа замыкание пусто, а вызывающий обязан расширить выбор до полного.
    """
    effective_policy = policy or RepoMapPolicy()
    parser = backend or BundleParserBackend(repo, effective_policy)
    changed = _diff(repo, base, candidate, effective_policy.timeout_seconds)
    unknown = [reason for item in changed for reason in _config_unknown(item)]
    graph = _graph(repo, candidate, parser, effective_policy)
    if graph.degraded is not None:
        unknown.append(UnknownReason(UNKNOWN_GRAPH_DEGRADED, "", graph.degraded))
        return ImpactSet(tuple(changed), (), (), _ordered(unknown))
    seeds: set[str] = set()
    for item in changed:
        if not item.path.endswith(".py") or item.status == "deleted":
            continue
        if item.path not in graph.paths:
            unknown.append(
                UnknownReason(
                    UNKNOWN_OUTSIDE_GRAPH, item.path, "excluded by Repo Map policy"
                )
            )
        elif (
            item.path not in graph.facts
            or graph.facts[item.path]["parser_status"] != "ok"
        ):
            unknown.append(
                UnknownReason(
                    UNKNOWN_PARSE_FAILED, item.path, "parser reported no facts"
                )
            )
        else:
            seeds.add(item.path)
    removed = [
        old
        for item in changed
        for old in (
            (item.old_path,)
            if item.status == "renamed"
            else (item.path,)
            if item.status == "deleted"
            else ()
        )
        if old and old.endswith(".py")
    ]
    if removed:
        before = _base_graph(repo, base, graph, changed, parser, effective_policy)
        if before.degraded is not None:
            unknown.append(UnknownReason(UNKNOWN_GRAPH_DEGRADED, "", before.degraded))
        for old in removed:
            referencing = before.importers.get(old, set()) - set(removed)
            if referencing:
                unknown.append(
                    UnknownReason(
                        UNKNOWN_REMOVED_REFERENCED,
                        old,
                        "imported by " + ", ".join(sorted(referencing)),
                    )
                )
                seeds |= referencing & graph.paths
    closure = _closure(seeds, graph.importers)
    unknown.extend(
        _unseen_importers(
            repo, candidate, graph, closure, effective_policy.timeout_seconds
        )
    )
    for path in sorted(closure):
        facts = graph.facts.get(path)
        if facts is not None and _uses_dynamic_import(facts):
            unknown.append(
                UnknownReason(
                    UNKNOWN_DYNAMIC_IMPORT, path, "module imports dynamically"
                )
            )
    related_tests = tuple(sorted(path for path in closure if is_test_path(path)))
    if max_related_tests is not None and len(related_tests) > max_related_tests:
        unknown.append(
            UnknownReason(
                UNKNOWN_OVER_THRESHOLD,
                "",
                f"{len(related_tests)} related tests exceed the plan threshold {max_related_tests}",
            )
        )
    modules = tuple(sorted(path for path in closure if not is_test_path(path)))
    return ImpactSet(tuple(changed), modules, related_tests, _ordered(unknown))


def _ordered(reasons: list[UnknownReason]) -> tuple[UnknownReason, ...]:
    """Причины без повторов в стабильном порядке."""
    return tuple(
        sorted(set(reasons), key=lambda item: (item.code, item.path, item.detail))
    )


@dataclass(frozen=True)
class RustCrate:
    """A Cargo package found under `crates/<dir>`: its package name and whether it has `src/lib.rs`."""

    package: str
    has_lib: bool


@dataclass(frozen=True)
class CargoTarget:
    """One `cargo test` target of the ticket diff: `lib`, `bins` or a named integration `test`."""

    manifest: str
    package: str
    kind: str
    name: str | None = None

    @property
    def target_id(self) -> str:
        """A stable id such as `state::lib`, `app::bins` or `state::test::qa_evidence`."""
        parts = [self.package, self.kind] + ([self.name] if self.name else [])
        return "::".join(parts)

    def argv(self) -> list[str]:
        """The `cargo test` command line that runs exactly this target."""
        argv = ["cargo", "test", "--manifest-path", self.manifest, "-p", self.package]
        if self.kind == "test":
            return [*argv, "--test", str(self.name)]
        return [*argv, f"--{self.kind}"]


@dataclass(frozen=True)
class TicketDiffSelection:
    """The tests of a ticket's own `base..candidate` diff (ADR 0023): Python modules and cargo targets."""

    python_tests: tuple[str, ...] = ()
    cargo_targets: tuple[CargoTarget, ...] = ()
    changed: tuple[ChangedPath, ...] = ()

    @property
    def empty(self) -> bool:
        """No test is selected; the caller records `no tests in diff` and never widens to full."""
        return not self.python_tests and not self.cargo_targets


def _crate_of(path: str) -> tuple[str, str, tuple[str, ...]] | None:
    """Split `<workspace>/crates/<name>/(src|tests)/<rest>` into crate dir, `src` or `tests`, rest."""
    parts = PurePosixPath(path).parts
    if "crates" not in parts:
        return None
    index = parts.index("crates")
    rest = parts[index + 2 :]
    if len(rest) < 2 or rest[0] not in {"src", "tests"}:
        return None
    return "/".join(parts[: index + 2]), rest[0], rest[1:]


def _test_target_name(rest: tuple[str, ...]) -> str | None:
    """The cargo test target of a file under `tests/`: `foo.rs` or `foo/main.rs`; helpers give none."""
    if len(rest) == 1 and rest[0].endswith(".rs"):
        return rest[0][: -len(".rs")]
    if len(rest) == 2 and rest[1] == "main.rs":
        return rest[0]
    return None


def select_ticket_diff_tests(
    changes: Sequence[ChangedPath], crates: Mapping[str, RustCrate]
) -> TicketDiffSelection:
    """The tests selected by a name-status diff alone; `crates` maps a crate dir to its package.

    An added, modified or renamed (to its new path) Python test module is selected. A Rust
    `tests/foo.rs` (or `tests/foo/main.rs`) gives `--test foo`, and any `src/**` file gives the
    crate's unit tests: `--lib`, or `--bins` for a crate without `src/lib.rs`. Deleted files,
    helpers, fixtures and files of unknown crates add nothing, and nothing widens the selection.
    """
    python_tests: set[str] = set()
    targets: dict[str, CargoTarget] = {}
    for item in changes:
        if item.status == "deleted":
            continue
        if is_test_path(item.path):
            python_tests.add(item.path)
            continue
        located = _crate_of(item.path)
        if located is None or located[0] not in crates:
            continue
        crate_dir, area, rest = located
        crate = crates[crate_dir]
        manifest = str(PurePosixPath(crate_dir).parent.parent / "Cargo.toml")
        if area == "src":
            target = CargoTarget(
                manifest, crate.package, "lib" if crate.has_lib else "bins"
            )
        elif (name := _test_target_name(rest)) is not None:
            target = CargoTarget(manifest, crate.package, "test", name)
        else:
            continue
        targets[target.target_id] = target
    return TicketDiffSelection(
        tuple(sorted(python_tests)),
        tuple(targets[key] for key in sorted(targets)),
        tuple(changes),
    )


def ticket_diff_selection(
    repo: Path, base: str, candidate: str, *, policy: RepoMapPolicy | None = None
) -> TicketDiffSelection:
    """The `TicketDiffSelection` of `git diff base..candidate`; each crate is read from `candidate`."""
    timeout = (policy or RepoMapPolicy()).timeout_seconds
    changed = _diff(repo, base, candidate, timeout)
    dirs = sorted(
        {
            located[0]
            for item in changed
            if item.status != "deleted" and (located := _crate_of(item.path))
        }
    )
    paths = [f"{name}/{leaf}" for name in dirs for leaf in ("Cargo.toml", "src/lib.rs")]
    contents = blob_contents(repo, candidate, paths, timeout)
    crates: dict[str, RustCrate] = {}
    for name in dirs:
        package = _package_name(contents.get(f"{name}/Cargo.toml"))
        if package is not None:
            crates[name] = RustCrate(
                package, contents.get(f"{name}/src/lib.rs") is not None
            )
    return select_ticket_diff_tests(changed, crates)


def _package_name(manifest: bytes | None) -> str | None:
    """`package.name` of a Cargo manifest, or `None` for a missing or unparsable manifest."""
    if manifest is None:
        return None
    try:
        name = tomllib.loads(manifest.decode("utf-8")).get("package", {}).get("name")
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    return name if isinstance(name, str) and name else None
