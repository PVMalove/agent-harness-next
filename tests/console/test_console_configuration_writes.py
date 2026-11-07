"""Configuration writes as console server jobs: a draft travels as a set of changes against the
masked snapshot, the configuration CLI replays it onto the unmasked files after a digest check,
never writes a secret mask and reports a stale file with exit code 3."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.configuration import SECRET_MASK
from harness.configuration_store import ConfigurationStore, StaleConfiguration
from harness.console.kernel import configuration_cli, configuration_writes
from harness.console.kernel.configuration import ConfigurationDraft
from harness.console.kernel.configuration_snapshot import collect_configuration

PROJECT = {
    "language": "ru",
    "base_branch": "main",
    "branch_pattern": "^feature/issue-[0-9]+-.+",
    "qa_gate_commands": ["pytest"],
    "tracker": {"type": "local"},
}


@pytest.fixture(autouse=True)
def no_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    from harness.health import project_tracker

    monkeypatch.setattr(project_tracker, "_origin_url", lambda _repo: None)


def _project(repo: Path, document: object = PROJECT) -> Path:
    root = repo / ".harness"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "project.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _draft(repo: Path) -> ConfigurationDraft:
    return ConfigurationDraft.from_snapshot(
        repo, collect_configuration(repo), ("project.json",)
    )


def test_the_changes_are_the_changed_leaves_against_the_snapshot_base(
    tmp_path: Path,
) -> None:
    _project(tmp_path, {**PROJECT, "extra": {"a": 1, "b": 2}})
    draft = _draft(tmp_path)
    draft.set_value("project.json", ("language",), "en")
    draft.remove_value("project.json", ("extra", "b"))

    found = configuration_writes.draft_changes(draft)

    assert found == [
        {"file": "project.json", "path": ["language"], "value": "en"},
        {"file": "project.json", "path": ["extra", "b"], "remove": True},
    ]
    request = json.loads(configuration_writes.draft_request(draft, "почему"))
    assert request == {
        "changes": found,
        "expected": draft.digests,
        "description": "почему",
    }


def test_a_replay_keeps_an_untouched_secret_and_refuses_the_mask() -> None:
    current = {"project.json": {"language": "ru", "tracker": {"token": "abc"}}}

    found = configuration_writes.replay_changes(
        current, [{"file": "project.json", "path": ["language"], "value": "en"}]
    )

    assert found["project.json"] == {"language": "en", "tracker": {"token": "abc"}}
    assert current["project.json"]["language"] == "ru"
    for value in (SECRET_MASK, {"token": SECRET_MASK}, ["x", SECRET_MASK]):
        with pytest.raises(ValueError):
            configuration_writes.replay_changes(
                current, [{"file": "project.json", "path": ["tracker"], "value": value}]
            )
    broken_sets: list[list[object]] = [
        [{"file": "other.json", "path": ["x"], "value": 1}],
        [{"file": "project.json", "path": [], "value": 1}],
        [{"file": "project.json", "path": ["x"]}],
        [{"file": "project.json", "path": ["x"], "remove": False}],
    ]
    for broken in broken_sets:
        with pytest.raises(ValueError):
            configuration_writes.replay_changes(current, broken)


def test_apply_writes_the_changes_onto_the_current_file(tmp_path: Path) -> None:
    path = _project(tmp_path)
    draft = _draft(tmp_path)
    draft.set_value("project.json", ("language",), "en")

    message = configuration_writes.apply(tmp_path, configuration_writes.draft_request(draft))

    assert json.loads(path.read_text(encoding="utf-8")) == {**PROJECT, "language": "en"}
    assert "Предыдущая версия" in message
    assert len(ConfigurationStore(tmp_path).versions()) == 1


def test_a_stale_digest_refuses_with_exit_code_3_and_leaves_the_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _project(tmp_path)
    draft = _draft(tmp_path)
    draft.set_value("project.json", ("language",), "en")
    request = configuration_writes.draft_request(draft)
    path.write_text(json.dumps({**PROJECT, "base_branch": "dev"}), encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(StaleConfiguration):
        configuration_writes.apply(tmp_path, request)
    code = configuration_cli.main(["apply", "--repo", str(tmp_path), "--request", request])

    assert code == 3 and path.read_bytes() == before
    assert "другим процессом" in capsys.readouterr().err


def test_a_missing_file_is_replayed_onto_its_default_document(tmp_path: Path) -> None:
    (tmp_path / ".harness").mkdir()
    draft = _draft(tmp_path)
    assert draft.original == {"project.json": None}
    draft.set_value("project.json", ("language",), "en")

    configuration_writes.apply(tmp_path, configuration_writes.draft_request(draft))

    written = json.loads((tmp_path / ".harness/project.json").read_text(encoding="utf-8"))
    assert written["language"] == "en" and written["qa_gate_commands"] == []


def test_versions_are_saved_without_applying_and_restored_by_digest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _project(tmp_path)
    before = path.read_bytes()
    draft = _draft(tmp_path)
    draft.set_value("project.json", ("language",), "en")

    saved = configuration_writes.save_draft(
        tmp_path, configuration_writes.draft_request(draft, "черновик")
    )
    current = configuration_cli.main(
        [
            "save-current",
            "--repo",
            str(tmp_path),
            "--request",
            json.dumps({"description": ""}),
        ]
    )

    assert "Версия сохранена без применения" in saved and current == 0
    assert path.read_bytes() == before
    store = ConfigurationStore(tmp_path)
    by_description = {version.description: version.id for version in store.versions()}
    restore = json.dumps(
        {
            "version": by_description["черновик"],
            "expected": {"project.json": draft.digests["project.json"], "orchestration.json": ""},
        }
    )
    assert "Версия восстановлена" in configuration_writes.restore(tmp_path, restore)
    assert json.loads(path.read_text(encoding="utf-8"))["language"] == "en"
    with pytest.raises(StaleConfiguration):
        configuration_writes.restore(tmp_path, restore)
    assert configuration_cli.main(["recover", "--repo", str(tmp_path)]) == 0
    assert configuration_cli.main(["apply", "--repo", str(tmp_path), "--request", "{"]) == 2
    capsys.readouterr()
