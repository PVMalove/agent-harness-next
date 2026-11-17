"""The «Настройка» snapshot: its wire codec and the facts the console server collects. The
collector masks secrets, digests the raw bytes, never creates the version store, never moves a
legacy one and never recovers a pending transaction."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

from harness.configuration import SECRET_MASK
from harness.console.backend import composition
from harness.console.backend.infrastructure import screen_facts
from harness.console.kernel.configuration_snapshot import (
    ConfigurationFacts,
    collect_configuration,
    config_digest,
)
from harness.console.kernel.configuration_wizard import wizard_parameters

PROJECT = {
    "language": "ru",
    "base_branch": "main",
    "branch_pattern": "^feature/issue-[0-9]+-.+",
    "qa_gate_commands": ["pytest"],
    "tracker": {"type": "local", "token": "abc"},
}


def _project(repo: Path, document: object = PROJECT) -> bytes:
    root = repo / ".harness"
    root.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(document).encode()
    (root / "project.json").write_bytes(raw)
    return raw


def test_the_files_are_masked_and_digested_and_a_missing_one_is_its_default(
    tmp_path: Path,
) -> None:
    raw = _project(tmp_path)

    sut = collect_configuration(tmp_path)

    project = sut.files["project.json"]
    assert (project.exists, project.digest, project.error) == (
        True,
        hashlib.sha256(raw).hexdigest(),
        "",
    )
    assert project.document["tracker"] == {"type": "local", "token": SECRET_MASK}
    orchestration = sut.files["orchestration.json"]
    assert (orchestration.exists, orchestration.digest) == (False, "")
    assert isinstance(orchestration.document.get("provider_profiles"), dict)
    assert config_digest(None) == "" and config_digest(raw) == project.digest


def test_the_collector_never_creates_the_store_nor_moves_a_legacy_one(
    tmp_path: Path,
) -> None:
    _project(tmp_path)
    legacy = tmp_path / ".harness/config-versions"
    legacy.mkdir()

    sut = collect_configuration(tmp_path)

    assert legacy.is_dir()
    assert not (tmp_path / ".harness/config_versions").exists()
    assert sut.store_root == str(tmp_path.resolve() / ".harness/config_versions")
    assert (sut.schema_installed, sut.orchestration_installed) == (False, False)


def test_a_prepared_transaction_is_reported_and_never_recovered(tmp_path: Path) -> None:
    raw = _project(tmp_path, {"language": "en"})
    store = tmp_path / ".harness/config_versions"
    store.mkdir()

    def encoded(data: bytes | None) -> object:
        return None if data is None else base64.b64encode(data).decode()

    journal = {
        "schema": 1,
        "state": "prepared",
        "id": "x",
        "before": {"project.json": encoded(raw), "orchestration.json": None},
        "after": {"project.json": encoded(b"{}"), "orchestration.json": None},
    }
    marker = store / ".transaction.json"
    marker.write_text(json.dumps(journal), encoding="utf-8")

    sut = collect_configuration(tmp_path)

    assert sut.transaction_pending is True
    assert json.loads(marker.read_text(encoding="utf-8"))["state"] == "prepared"


def test_an_unparsed_file_carries_its_error_and_no_document(tmp_path: Path) -> None:
    root = tmp_path / ".harness"
    root.mkdir()
    (root / "project.json").write_bytes(b"{not json")

    found = collect_configuration(tmp_path).files["project.json"]

    assert found.exists is True and found.error and found.document == {}


def test_the_facts_round_trip_and_a_payload_off_the_schema_is_a_value_error(
    tmp_path: Path,
) -> None:
    _project(tmp_path)
    sut = collect_configuration(tmp_path)
    payload = sut.to_payload()

    assert ConfigurationFacts.from_payload(json.loads(json.dumps(payload))) == sut
    for broken in (
        None,
        {**payload, "extra": 1},
        {**payload, "files": {"project.json": {}}},
        {**payload, "transaction_pending": "no"},
        {**payload, "adapters": {"preview": None}},
    ):
        with pytest.raises(ValueError):
            ConfigurationFacts.from_payload(broken)


def test_the_screen_facts_adapter_is_the_kernel_collector(tmp_path: Path) -> None:
    _project(tmp_path)

    payload = screen_facts.configuration_facts(tmp_path)
    wizard = payload.pop("wizard")
    assert payload.pop("versions") == []

    found = ConfigurationFacts.from_payload(payload)

    assert found == collect_configuration(tmp_path)
    assert wizard == wizard_parameters(tmp_path, found)
    service = composition.screen_service(tmp_path)
    assert service._collect_configuration is screen_facts.configuration_facts


def _saved_version(repo: Path) -> str:
    from harness.configuration_store import ConfigurationStore
    from tests.console._configuration_fixture import installed_project

    raw = installed_project(repo)
    version = ConfigurationStore(repo).save(
        {"project.json": raw, "orchestration.json": None}, "первая"
    )
    (repo / ".harness/project.json").write_text(
        json.dumps({**json.loads(raw), "language": "en"}), encoding="utf-8"
    )
    return version.id


def test_versions_are_listed_without_creating_the_store_or_moving_a_legacy_one(
    tmp_path: Path,
) -> None:
    from harness.console.kernel.configuration_snapshot import list_versions, read_version

    _project(tmp_path)
    legacy = tmp_path / ".harness/config-versions"
    legacy.mkdir()

    assert list_versions(tmp_path) == []
    missing = read_version(tmp_path, "20260101T000000Z-0123456789ab")

    assert legacy.is_dir()
    assert not (tmp_path / ".harness/config_versions").exists()
    assert missing["files"] == {}
    assert "20260101T000000Z-0123456789ab" in str(missing["error"])
    assert ".harness/config_versions" in str(missing["error"])


def test_the_selected_version_is_its_own_masked_content(tmp_path: Path) -> None:
    from harness.console.kernel.configuration_snapshot import list_versions, read_version

    identifier = _saved_version(tmp_path)

    listed = list_versions(tmp_path)
    found = read_version(tmp_path, identifier)

    assert [item["id"] for item in listed] == [identifier]
    assert listed[0]["description"] == "первая"
    assert listed[0]["files"] == ["project.json"]
    assert found["id"] == identifier and found["error"] == ""
    files = found["files"]
    assert isinstance(files, dict)
    assert files["project.json"]["document"]["language"] == "ru"
    assert files["project.json"]["exists"] is True and files["project.json"]["digest"]
    assert files["orchestration.json"] == {
        "exists": False,
        "digest": "",
        "document": {},
        "error": "",
    }
    for bad in ("../x", "nonsense"):
        broken = read_version(tmp_path, bad)
        assert broken["files"] == {} and bad in str(broken["error"])


def test_a_damaged_version_names_the_store_problem(tmp_path: Path) -> None:
    from harness.console.kernel.configuration_snapshot import read_version

    identifier = _saved_version(tmp_path)
    stored = tmp_path / ".harness/config_versions" / identifier / "project.json"
    stored.write_text("{}", encoding="utf-8")

    found = read_version(tmp_path, identifier)

    assert found["files"] == {} and "хеш" in str(found["error"])


def test_the_snapshot_merges_the_selected_version_uncached(tmp_path: Path) -> None:
    import asyncio

    identifier = _saved_version(tmp_path)
    service = composition.screen_service(tmp_path)

    async def scenario() -> tuple[dict[str, object], dict[str, object]]:
        plain = await service.configuration()
        chosen = await service.configuration(version=identifier)
        return json.loads(plain.text), json.loads(chosen.text)

    plain, chosen = asyncio.run(scenario())

    assert "version" not in plain
    versions, selected = plain["versions"], chosen["version"]
    assert isinstance(versions, list) and isinstance(selected, dict)
    assert [item["id"] for item in versions] == [identifier]
    assert selected["id"] == identifier
    assert {key: chosen[key] for key in plain} == plain


@pytest.mark.parametrize("version", ["../x", "", 5, "20260101T000000Z-XYZ"])
def test_a_malformed_version_field_is_a_bad_request(
    tmp_path: Path, version: object
) -> None:
    import asyncio

    from harness.console.backend.api.protocol.screens import respond

    service = composition.screen_service(tmp_path)
    frame = json.dumps({"id": 1, "type": "configuration.snapshot", "version": version})
    reply = json.loads(asyncio.run(respond(frame, service)))
    assert reply["error"]["code"] == "bad_request"


def test_the_wizard_carries_the_console_recommendation(tmp_path: Path) -> None:
    from tests.console._configuration_fixture import installed_project

    installed_project(tmp_path)
    facts = collect_configuration(tmp_path)
    by_path = {
        ".".join(item["path"]): item  # type: ignore[arg-type]
        for item in wizard_parameters(tmp_path, facts)
    }
    language = by_path["language"]["recommendation"]
    assert isinstance(language, dict)
    assert language["value"] == "ru" and language["reason"]
    assert all("recommendation" in item for item in by_path.values())
    # Without the facts there is no draft to recommend from.
    assert all(item["recommendation"] is None for item in wizard_parameters(tmp_path))


@pytest.fixture(autouse=True)
def no_remote_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    from harness.console.kernel import project_facts

    monkeypatch.setattr(project_facts, "_default_branch", lambda _repo: None)
