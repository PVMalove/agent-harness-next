"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

from harness.console.kernel.catalog import (
    CONFIRMATION_REASONS,
    HARNESS_COMMANDS,
    MEMORY_COMMANDS,
    CatalogEntry,
    Reversibility,
    process_argv,
)
from harness.console.launcher import BIN_HARNESS_PATH

ROOT = Path(__file__).resolve().parents[2]

REPO = Path("/work/project")

ENTRIES = {entry.key: entry for entry in HARNESS_COMMANDS}


def test_catalog_covers_every_harness_and_ledger_command() -> None:
    """Проверить, что каталог команд покрывает все команды харнесса и леджера."""
    assert {
        "init",
        "update",
        "update-force-managed",
        "update-force-seed",
        "diff",
        "adopt",
        "registry",
        "lock-project-skills",
        "list",
        "health",
        "cleanup",
        "cleanup-hard",
        "cleanup-apply",
        "cleanup-hard-apply",
        "uninstall",
        "uninstall-apply",
        "repo-map",
        "parser-bundle",
        "verify",
        "ledger-migrate",
        "ledger-clean",
        "ledger-reset",
        "worktree-remove",
    } <= ENTRIES.keys()
    assert len(ENTRIES) == len(HARNESS_COMMANDS)


def test_irreversible_commands_carry_their_confirmation_class() -> None:
    """Проверить, что необратимые команды содержат свой класс подтверждения."""
    irreversible = {
        entry.key: entry.reversibility
        for entry in HARNESS_COMMANDS
        if entry.needs_confirmation
    }
    assert irreversible == {
        "init": Reversibility.OVERWRITES_MANAGED_FILES,
        "update": Reversibility.OVERWRITES_MANAGED_FILES,
        "update-force-managed": Reversibility.OVERWRITES_MANAGED_FILES,
        "update-force-seed": Reversibility.OVERWRITES_MANAGED_FILES,
        "adopt": Reversibility.OVERWRITES_MANAGED_FILES,
        "health-online-fix": Reversibility.EXTERNAL_CHANGE,
        "cleanup-apply": Reversibility.DELETES_LOCAL_DATA,
        "cleanup-hard-apply": Reversibility.DELETES_LOCAL_DATA,
        "uninstall-apply": Reversibility.DELETES_LOCAL_DATA,
        "ledger-clean": Reversibility.DELETES_LOCAL_DATA,
        "ledger-reset": Reversibility.DELETES_LOCAL_DATA,
        "worktree-remove": Reversibility.DELETES_LOCAL_DATA,
    }
    assert set(CONFIRMATION_REASONS) == set(Reversibility) - {Reversibility.REVERSIBLE}


def test_commands_mutate_unless_declared_reads() -> None:
    """Reversibility controls confirmation; only a declared read runs beside a mutation."""
    reads = {"diff", "cleanup", "cleanup-hard", "uninstall", "list", "health"}
    assert {entry.key for entry in HARNESS_COMMANDS if entry.read_only} == reads
    assert not any(entry.read_only for entry in MEMORY_COMMANDS)
    # A read never needs a confirmation: every irreversible class writes.
    assert all(
        entry.reversibility is Reversibility.REVERSIBLE
        for entry in HARNESS_COMMANDS
        if entry.read_only
    )
    # Reversible writers still take the mutation slot.
    assert ENTRIES["registry"].reversibility is Reversibility.REVERSIBLE
    assert not ENTRIES["registry"].read_only and not ENTRIES["health-fix"].read_only


def test_typed_confirmations_match_the_cli_safeguard_words() -> None:
    """Проверить, что фразы подтверждения совпадают со словами защиты CLI."""
    reset = ENTRIES["ledger-reset"]
    assert reset.typed_confirmation == "RESET"
    assert reset.argv[-2:] == ("--confirm", "RESET")
    assert ENTRIES["update-force-managed"].argv[-1] == "--force-managed-files"
    assert ENTRIES["update-force-seed"].argv[-1] == "--force-seed-files"
    assert ENTRIES["cleanup-hard"].argv[-2:] == ("--mode", "hard")
    uninstall = ENTRIES["uninstall-apply"]
    assert uninstall.typed_confirmation == "UNINSTALL"
    assert uninstall.argv[-2:] == ("--confirm", "UNINSTALL")
    hard = ENTRIES["cleanup-hard-apply"]
    assert hard.typed_confirmation == "HARD"
    assert hard.argv[-2:] == ("--confirm", "HARD")


@pytest.mark.parametrize(
    "entry",
    [e for e in HARNESS_COMMANDS if e.argv[0] == "harness"],
    ids=lambda e: e.key,
)
def test_harness_cli_argv_dispatches_to_the_named_function(entry: CatalogEntry) -> None:
    """Проверить, что аргументы CLI команды харнесса вызывают указанную функцию."""
    cli = runpy.run_path(str(BIN_HARNESS_PATH))
    args = cli["parser"]().parse_args(entry.cli_argv(REPO)[1:])
    module, name = entry.function.split(":")
    assert module == "harness/bin/harness.py"
    assert args.func.__name__ == name
    assert args.repo == str(REPO)


@pytest.mark.parametrize(
    "entry",
    [e for e in HARNESS_COMMANDS if e.key.startswith("ledger-")],
    ids=lambda e: e.key,
)
def test_coordinator_argv_dispatches_to_the_named_handler(entry: CatalogEntry) -> None:
    """Проверить, что аргументы координатора диспетчеризуются в соответствующий обработчик."""
    from harness.orchestration import coordinator

    argv = entry.cli_argv(REPO)
    assert argv[:2] == ["python", ".harness/orchestration/coordinator.py"]
    args = coordinator.parser().parse_args(argv[2:])
    module, name = entry.function.split(":")
    assert module == "harness.orchestration.coordinator"
    assert args.handler is getattr(coordinator, name)
    assert args.repo == str(REPO)


@pytest.mark.parametrize(
    "key, source",
    [
        ("repo-map", "harness/repo_map/repo_map.py"),
        ("parser-bundle", "scripts/build_parser_bundle.py"),
        ("verify", "scripts/verify.py"),
    ],
)
def test_script_entries_name_an_existing_main(key: str, source: str) -> None:
    """Проверить, что команды скриптов ссылаются на существующую функцию main."""
    entry = ENTRIES[key]
    assert entry.function == f"{source}:main"
    assert entry.argv[1] in (source, f".harness/{source.removeprefix('harness/')}")
    assert "\ndef main(" in (ROOT / source).read_text(encoding="utf-8")


def test_inputs_are_asked_and_filled_into_the_cli_equivalent() -> None:
    """Проверить, что параметры запрашиваются и подставляются в эквивалент команды CLI."""
    entry = ENTRIES["parser-bundle"]
    assert entry.inputs == ("wheelhouse",)
    assert "<wheelhouse>" in entry.cli_line(REPO)
    assert entry.cli_argv(REPO, {"wheelhouse": "wheels"})[3] == "wheels"


def test_process_argv_runs_the_cli_equivalent_under_this_interpreter() -> None:
    """Проверить, что аргументы процесса используют текущий интерпретатор."""
    assert process_argv(["harness", "diff", "r"]) == [
        sys.executable,
        str(BIN_HARNESS_PATH),
        "diff",
        "r",
    ]
    assert process_argv(["python", "scripts/verify.py"]) == [
        sys.executable,
        "scripts/verify.py",
    ]


def test_only_verify_runs_under_the_repository_dev_environment(tmp_path: Path) -> None:
    """Проверить, что только verify запускается в виртуальном окружении репозитория."""
    venv_python = (
        tmp_path
        / ".harness"
        / ".venv"
        / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    )
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")

    assert [key for key, entry in ENTRIES.items() if entry.dev_environment] == [
        "verify"
    ]
    assert process_argv(["python", "x.py"], tmp_path, dev_environment=True) == [
        str(venv_python),
        "x.py",
    ]
    assert process_argv(["python", "x.py"], tmp_path) == [sys.executable, "x.py"]


def test_worktree_removal_uses_the_guarded_cli_boundary() -> None:
    entry = ENTRIES["worktree-remove"]
    assert entry.inputs == ("worktree",)
    assert entry.cli_argv(REPO, {"worktree": "wt"}) == [
        "harness",
        "worktree-remove",
        str(REPO),
        "wt",
    ]
    assert process_argv(entry.cli_argv(REPO, {"worktree": "wt"}))[0] == sys.executable


def test_repo_map_commands_dispatch_to_their_cli_functions() -> None:
    """The Repo Map section's memory and parser commands reach the CLI functions they name."""
    from harness.console.kernel.catalog import MEMORY_COMMANDS, parsers_install_entry

    cli = runpy.run_path(str(BIN_HARNESS_PATH))
    install = parsers_install_entry(["python", "go"])
    assert install.reversibility in CONFIRMATION_REASONS
    assert install.cli_argv(REPO)[2:] == [
        "install",
        str(REPO),
        "--language",
        "python",
        "--language",
        "go",
    ]
    for entry in (*MEMORY_COMMANDS, install):
        args = cli["parser"]().parse_args(entry.cli_argv(REPO)[1:])
        assert args.func.__name__ == entry.function.split(":")[1]
        assert args.repo == str(REPO)
    assert install.needs_confirmation
    assert not any(entry.needs_confirmation for entry in MEMORY_COMMANDS)


def test_diagnostics_fixes_print_the_json_report_through_cmd_health() -> None:
    """The Diagnostics fixes are their own commands, kept out of the Harness menu: the same
    `harness health --fix` with `--json`, so the screen reads the applied fixes back."""
    from harness.console.kernel.catalog import DIAGNOSTICS_COMMANDS
    from harness.console.kernel.i18n_strings import EN

    by_key = {entry.key: entry for entry in DIAGNOSTICS_COMMANDS}
    assert set(by_key) == {"diagnostics-fix", "diagnostics-online-fix"}
    assert not set(by_key) & set(ENTRIES)
    cli = runpy.run_path(str(BIN_HARNESS_PATH))
    for entry in DIAGNOSTICS_COMMANDS:
        args = cli["parser"]().parse_args(entry.cli_argv(REPO)[1:])
        assert args.func.__name__ == entry.function.split(":")[1] == "cmd_health"
        assert (args.repo, args.fix, args.json) == (str(REPO), True, True)
        assert args.online is (entry.key == "diagnostics-online-fix")
        assert not entry.read_only and not entry.inputs and entry.title in EN
    assert by_key["diagnostics-fix"].reversibility is Reversibility.REVERSIBLE
    online = by_key["diagnostics-online-fix"]
    assert online.reversibility is ENTRIES["health-online-fix"].reversibility
    assert online.needs_confirmation and online.typed_confirmation is None


@pytest.mark.parametrize(
    "paths",
    ["", "\n", "-x", "/abs/file.md", "a/../b.md", "..", "a\n-b", "a\\b.md"],
)
def test_the_seed_update_job_refuses_unsafe_or_empty_paths(paths: str) -> None:
    from harness.console.kernel.catalog import UPDATE_SEED_SELECTED

    assert not UPDATE_SEED_SELECTED.accepts({"paths": paths})


def test_the_seed_update_job_overwrites_the_given_files_as_seed_update_entry() -> None:
    from harness.console.kernel.catalog import UPDATE_SEED_SELECTED, seed_update_entry

    values = {"paths": ".claude/rules/one.md\n\nAGENTS.md\n"}
    assert UPDATE_SEED_SELECTED.accepts(values)
    assert not UPDATE_SEED_SELECTED.accepts({"paths": "a.md", "extra": "x"})
    assert UPDATE_SEED_SELECTED.cli_argv(REPO, values) == seed_update_entry(
        [".claude/rules/one.md", "AGENTS.md"]
    ).cli_argv(REPO)
    assert UPDATE_SEED_SELECTED.key == "update-seed-selected"
    assert UPDATE_SEED_SELECTED.reversibility is Reversibility.OVERWRITES_MANAGED_FILES
    assert UPDATE_SEED_SELECTED.needs_confirmation and not UPDATE_SEED_SELECTED.read_only
    assert UPDATE_SEED_SELECTED.available(REPO)
    cli = runpy.run_path(str(BIN_HARNESS_PATH))
    args = cli["parser"]().parse_args(UPDATE_SEED_SELECTED.cli_argv(REPO, values)[1:])
    assert args.func.__name__ == "cmd_update"


def test_the_configuration_writes_run_the_configuration_cli_by_reversibility() -> None:
    from harness.console.kernel.catalog import CONFIGURATION_COMMANDS
    from harness.console.kernel.i18n_strings import EN

    by_key = {entry.key: entry for entry in CONFIGURATION_COMMANDS}
    assert {key: entry.reversibility for key, entry in by_key.items()} == {
        "configuration-save-draft": Reversibility.REVERSIBLE,
        "configuration-save-current": Reversibility.REVERSIBLE,
        "configuration-apply": Reversibility.OVERWRITES_MANAGED_FILES,
        "configuration-adapters": Reversibility.OVERWRITES_MANAGED_FILES,
        "configuration-recover": Reversibility.REVERSIBLE,
        "configuration-restore": Reversibility.OVERWRITES_MANAGED_FILES,
    }
    assert not set(by_key) & set(ENTRIES)
    for entry in CONFIGURATION_COMMANDS:
        script = Path(entry.argv[2])
        assert entry.argv[:2] == ("python", "-B") and script.is_absolute()
        assert entry.function == "harness/console/kernel/configuration_cli.py:main"
        assert "\ndef main(" in script.read_text(encoding="utf-8")
        assert entry.available(REPO) and not entry.read_only and entry.title in EN
        assert entry.typed_confirmation is None
        assert entry.inputs == (() if entry.key == "configuration-recover" else ("request",))
