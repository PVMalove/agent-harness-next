"""Ticket-diff selection: the tests of the ticket's own `base..candidate` diff (ADR 0023).

The selection is read from the name-status diff alone: an added or modified Python test module is
selected, a Rust `crates/X/tests/foo.rs` becomes `cargo test -p X --test foo` and any
`crates/X/src/**` change becomes the unit tests of that crate (`--lib`, or `--bins` for a crate
without a library). A deleted file, a changed helper or fixture and an empty diff select nothing,
and nothing ever widens the selection to the whole suite.
"""

from __future__ import annotations

from pathlib import Path

from harness.repo_map.change_impact import (
    CargoTarget,
    ChangedPath,
    RustCrate,
    TicketDiffSelection,
    select_ticket_diff_tests,
    ticket_diff_selection,
)
from tests.repo_map.test_change_impact import _commit, _git, _init, _write

WORKSPACE = "native/harness-runtime"
STATE = f"{WORKSPACE}/crates/state"
APP = f"{WORKSPACE}/crates/app"
CRATES = {
    STATE: RustCrate(package="state", has_lib=True),
    APP: RustCrate(package="app", has_lib=False),
}
MANIFEST = f"{WORKSPACE}/Cargo.toml"


def _select(*changes: ChangedPath) -> TicketDiffSelection:
    return select_ticket_diff_tests(changes, CRATES)


def _added(path: str) -> ChangedPath:
    return ChangedPath("added", path)


def _modified(path: str) -> ChangedPath:
    return ChangedPath("modified", path)


def _deleted(path: str) -> ChangedPath:
    return ChangedPath("deleted", path)


def test_added_and_modified_python_test_modules_are_selected_in_sorted_order() -> None:
    selection = _select(
        _modified("tests/test_b.py"),
        _added("tests/core/test_a.py"),
        _added("tests/core/other_test.py"),
    )

    assert selection.python_tests == (
        "tests/core/other_test.py",
        "tests/core/test_a.py",
        "tests/test_b.py",
    )
    assert selection.cargo_targets == ()


def test_a_deleted_python_test_module_adds_nothing() -> None:
    assert _select(_deleted("tests/test_gone.py")).empty


def test_changed_helpers_and_fixtures_add_no_python_tests() -> None:
    selection = _select(
        _modified("tests/conftest.py"),
        _modified("tests/helpers.py"),
        _modified("tests/fixtures/data.json"),
        _modified("harness/orchestration/verification_plan.py"),
        _modified("tests/__init__.py"),
    )

    assert selection.empty


def test_a_renamed_python_test_module_is_selected_under_its_new_path() -> None:
    renamed = ChangedPath("renamed", "tests/test_new.py", "tests/test_old.py")

    assert _select(renamed).python_tests == ("tests/test_new.py",)


def test_a_rust_integration_test_file_becomes_a_cargo_test_target() -> None:
    selection = _select(_modified(f"{STATE}/tests/qa_evidence.rs"))

    (target,) = selection.cargo_targets
    assert target == CargoTarget(MANIFEST, "state", "test", "qa_evidence")
    assert target.argv() == [
        "cargo",
        "test",
        "--manifest-path",
        MANIFEST,
        "-p",
        "state",
        "--test",
        "qa_evidence",
    ]
    assert selection.python_tests == ()


def test_a_rust_test_directory_target_is_named_by_its_directory() -> None:
    selection = _select(_added(f"{STATE}/tests/windows_job/main.rs"))

    assert [(t.kind, t.name) for t in selection.cargo_targets] == [
        ("test", "windows_job")
    ]


def test_rust_test_helpers_and_fixtures_add_nothing() -> None:
    selection = _select(
        _modified(f"{STATE}/tests/common/mod.rs"),
        _modified(f"{STATE}/tests/common/qa_store.rs"),
        _modified(f"{STATE}/tests/fixtures/stage-evidence.v1.json"),
    )

    assert selection.empty


def test_a_changed_lib_source_runs_the_lib_tests_of_its_crate_once() -> None:
    selection = _select(
        _modified(f"{STATE}/src/lib.rs"),
        _added(f"{STATE}/src/qa/evidence.rs"),
    )

    assert [(t.package, t.kind, t.name) for t in selection.cargo_targets] == [
        ("state", "lib", None)
    ]
    assert selection.cargo_targets[0].argv()[-1] == "--lib"


def test_a_changed_source_of_a_binary_only_crate_runs_its_bins() -> None:
    selection = _select(_modified(f"{APP}/src/main.rs"))

    (target,) = selection.cargo_targets
    assert (target.package, target.kind, target.name) == ("app", "bins", None)
    assert target.argv()[-1] == "--bins"


def test_cargo_targets_are_ordered_and_have_stable_ids() -> None:
    selection = _select(
        _modified(f"{STATE}/src/lib.rs"),
        _modified(f"{STATE}/tests/b.rs"),
        _modified(f"{STATE}/tests/a.rs"),
        _modified(f"{APP}/src/main.rs"),
    )

    assert [t.target_id for t in selection.cargo_targets] == [
        "app::bins",
        "state::lib",
        "state::test::a",
        "state::test::b",
    ]


def test_deleted_rust_files_and_files_of_unknown_crates_add_nothing() -> None:
    selection = _select(
        _deleted(f"{STATE}/tests/old.rs"),
        _deleted(f"{STATE}/src/old.rs"),
        _modified(f"{WORKSPACE}/crates/ghost/src/lib.rs"),
        _modified(f"{WORKSPACE}/Cargo.toml"),
    )

    assert selection.empty


def test_a_diff_without_tests_selects_nothing_and_is_never_widened() -> None:
    selection = _select(
        _modified("harness/core.py"),
        _modified("Makefile"),
        _modified("pyproject.toml"),
    )

    assert selection.empty
    assert selection.python_tests == () and selection.cargo_targets == ()


def test_a_workspace_at_the_repository_root_names_its_own_manifest() -> None:
    selection = select_ticket_diff_tests(
        [_modified("crates/core/tests/smoke.rs")],
        {"crates/core": RustCrate("core", True)},
    )

    assert selection.cargo_targets[0].manifest == "Cargo.toml"


def test_the_git_diff_yields_the_selection_and_reads_each_crate_from_the_candidate(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    _write(
        repo,
        {
            "tests/test_old.py": "def test_old():\n    pass\n",
            "tests/helpers.py": "VALUE = 1\n",
            f"{STATE}/Cargo.toml": '[package]\nname = "state-crate"\n',
            f"{STATE}/src/lib.rs": "",
            f"{APP}/Cargo.toml": '[package]\nname = "app"\n',
            f"{APP}/src/main.rs": "fn main() {}\n",
        },
    )
    base = _commit(repo, "base")
    _write(
        repo,
        {
            "tests/test_new.py": "def test_new():\n    pass\n",
            "tests/helpers.py": "VALUE = 2\n",
            f"{STATE}/tests/x.rs": "",
            f"{APP}/src/main.rs": "fn main() { println!(); }\n",
        },
    )
    _git(repo, "rm", "-q", "tests/test_old.py")
    candidate = _commit(repo, "change")

    selection = ticket_diff_selection(repo, base, candidate)

    assert selection.python_tests == ("tests/test_new.py",)
    assert [(t.package, t.kind, t.name) for t in selection.cargo_targets] == [
        ("app", "bins", None),
        ("state-crate", "test", "x"),
    ]
    assert {item.path for item in selection.changed} == {
        "tests/test_new.py",
        "tests/test_old.py",
        "tests/helpers.py",
        f"{STATE}/tests/x.rs",
        f"{APP}/src/main.rs",
    }


def test_an_empty_git_diff_selects_nothing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    _write(repo, {"tests/test_a.py": "def test_a():\n    pass\n"})
    head = _commit(repo, "base")

    selection = ticket_diff_selection(repo, head, head)

    assert selection.empty and selection.changed == ()
