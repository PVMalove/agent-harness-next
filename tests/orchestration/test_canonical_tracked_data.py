"""The read-only canonical check of tracked orchestration configs and negative fixtures (#685).

Positive configs must be canonical: a value the runtime normalizer could repair fails the check
with the file, JSON pointer, code, allowed and received values. Each negative fixture is listed in
the manifest with its exact diagnostics, and the inventory is complete in both directions.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import inspect
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path

import pytest

from harness.orchestration.config_boundary import inspect_configuration
from scripts import verify

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_canonical_tracked_data.py"
ROLES = ROOT / "harness" / "orchestration" / "roles"


def _load() -> types.ModuleType:
    loader = importlib.machinery.SourceFileLoader("canonical_under_test", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


check_module = _load()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repo holding a copy of the tracked inventory the check reads."""
    copied = [
        *check_module.POSITIVE,
        check_module.NEGATIVE_MANIFEST,
        *(
            str(path.relative_to(ROOT))
            for path in (ROOT / check_module.NEGATIVE_DIR).iterdir()
        ),
    ]
    for relative in copied:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    return tmp_path


def _check(repo: Path) -> list[str]:
    problems: list[str] = check_module.check(repo, roles_root=ROLES)
    return problems


def _mutate(path: Path, change: dict[str, object]) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    document.update(change)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def test_the_tracked_inventory_is_canonical() -> None:
    assert check_module.check() == []


def test_the_copied_inventory_is_canonical(repo: Path) -> None:
    assert _check(repo) == []


@pytest.mark.parametrize("relative", check_module.POSITIVE)
def test_a_value_the_normalizer_repairs_fails_with_a_full_diagnostic(
    repo: Path, relative: str
) -> None:
    _mutate(repo / relative, {"approval_policy": "MILESTONE"})

    assert _check(repo) == [
        f"{relative}:/approval_policy: config-noncanonical: "
        'allowed=["manual_all", "milestone", "low_risk", "auto"]; '
        'received="MILESTONE"; write the suggested canonical enum'
    ]


def test_a_transport_alias_names_its_pointer(repo: Path) -> None:
    relative = check_module.POSITIVE[0]
    path = repo / relative
    document = json.loads(path.read_text(encoding="utf-8"))
    role = next(iter(document["assignment_plans"]))
    document["assignment_plans"][role]["transport"] = "in_process"
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")

    assert _check(repo) == [
        f"{relative}:/assignment_plans/{role}/transport: config-noncanonical: "
        'allowed=["in-process", "external"]; received="in_process"; '
        "write the suggested canonical enum"
    ]


@pytest.mark.parametrize(
    ("raw", "detail"),
    [
        (b'{"approval_policy": "auto",', "Некорректное JSON-значение"),
        (
            b'{"approval_policy": "milestone", "approval_policy": "auto"}',
            "duplicate JSON key",
        ),
    ],
)
def test_malformed_json_and_duplicate_keys_are_refused(
    repo: Path, raw: bytes, detail: str
) -> None:
    relative = check_module.POSITIVE[1]
    (repo / relative).write_bytes(raw)

    [line] = _check(repo)

    assert line.startswith(f"{relative}:: config-invalid: ")
    assert detail in line


def test_runtime_normalization_keeps_its_warning_semantics() -> None:
    raw = (ROOT / check_module.NEGATIVE_DIR / "transport-alias.json").read_bytes()

    result = inspect_configuration(ROOT, raw, canonical=False, roles_root=ROLES)

    assert result.valid
    assert [(item.code, item.severity) for item in result.diagnostics] == [
        ("config-normalized", "warning")
    ]
    assert result.document["assignment_plans"]["developer"]["transport"] == "in-process"


def test_the_check_never_rewrites_a_file(repo: Path) -> None:
    relative = check_module.POSITIVE[2]
    _mutate(repo / relative, {"approval_policy": "MILESTONE"})
    paths = [path for path in repo.rglob("*.json") if ".git" not in path.parts]
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}

    assert _check(repo)

    assert {
        path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths
    } == before


def test_the_check_imports_no_writer() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "ConfigurationStore" not in source
    assert "write_bytes" not in source and "write_text" not in source


def test_every_negative_fixture_is_listed_with_its_diagnostics() -> None:
    manifest = json.loads(
        (ROOT / check_module.NEGATIVE_MANIFEST).read_text(encoding="utf-8")
    )
    listed = sorted(entry["file"] for entry in manifest["fixtures"])

    assert listed == sorted(
        path.name for path in (ROOT / check_module.NEGATIVE_DIR).iterdir()
    )
    assert all(entry["expected"] for entry in manifest["fixtures"])
    assert {"config-invalid", "config-noncanonical", "config-schema"} <= {
        item["code"] for entry in manifest["fixtures"] for item in entry["expected"]
    }


def test_an_unlisted_negative_fixture_fails(repo: Path) -> None:
    extra = f"{check_module.NEGATIVE_DIR}/extra.json"
    shutil.copyfile(
        repo / check_module.NEGATIVE_DIR / "unknown-enum.json", repo / extra
    )

    assert _check(repo) == [
        f"{extra}: unlisted negative fixture; add it to {check_module.NEGATIVE_MANIFEST}"
    ]


def test_a_listed_but_missing_negative_fixture_fails(repo: Path) -> None:
    missing = f"{check_module.NEGATIVE_DIR}/malformed.json"
    (repo / missing).unlink()

    assert _check(repo) == [f"{missing}: listed negative fixture is missing"]


def test_a_negative_fixture_refused_for_another_reason_fails(repo: Path) -> None:
    manifest_path = repo / check_module.NEGATIVE_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = next(
        item for item in manifest["fixtures"] if item["file"] == "transport-alias.json"
    )
    entry["expected"] = [{"code": "config-noncanonical", "pointer": "/approval_policy"}]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    [line] = _check(repo)

    assert line.startswith(
        f"{check_module.NEGATIVE_DIR}/transport-alias.json: expected diagnostics "
    )
    assert "/assignment_plans/developer/transport" in line


def test_a_negative_fixture_without_its_expected_message_fails(repo: Path) -> None:
    manifest_path = repo / check_module.NEGATIVE_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = next(
        item for item in manifest["fixtures"] if item["file"] == "malformed.json"
    )
    entry["expected"][0]["message_contains"] = "duplicate JSON key"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert _check(repo) == [
        f"{check_module.NEGATIVE_DIR}/malformed.json: no config-invalid diagnostic "
        "contains 'duplicate JSON key'"
    ]


def test_an_unlisted_tracked_config_fails(repo: Path) -> None:
    extra = "examples/orchestration.json"
    (repo / "examples").mkdir()
    shutil.copyfile(repo / check_module.POSITIVE[0], repo / extra)
    _git(repo, "add", extra)

    assert _check(repo) == [
        f"{extra}: unlisted tracked config; add it to POSITIVE or "
        f"{check_module.NEGATIVE_MANIFEST}"
    ]


def test_the_command_exits_nonzero_and_prints_each_problem(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _mutate(repo / check_module.POSITIVE[0], {"approval_policy": "MILESTONE"})
    original = check_module.check
    monkeypatch.setattr(check_module, "check", lambda: original(repo, ROLES))

    assert check_module.main() == 1
    err = capsys.readouterr().err
    assert "config-noncanonical" in err
    assert "canonical-tracked-data: 1 problem(s)" in err


def test_the_command_succeeds_on_the_tracked_inventory() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "canonical-tracked-data: ok\n"


def test_make_verify_runs_the_check_before_the_tests() -> None:
    source = inspect.getsource(verify._static_checks)

    assert "check_canonical_tracked_data.py" in source
