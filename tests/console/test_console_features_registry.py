"""The feature registry of the Diagnostics screen: the 26 features of the package catalog, the
state rule, the dependency graph and the settings rows read from a project."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from harness.console.kernel.features import CATEGORIES, collect_features
from harness.console.kernel.project_target import capability_options
from harness.health.hook_settings import HOOK_CATALOG


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _settings_with(*scripts: str) -> str:
    """A `.claude/settings.local.json` wiring each script on its catalog event and tools."""
    hooks: dict[str, list[dict[str, object]]] = {}
    for spec in HOOK_CATALOG:
        if spec.script not in scripts or spec.wiring != "settings":
            continue
        hooks.setdefault(spec.event, []).append(
            {
                "matcher": "|".join(spec.tools),
                "hooks": [
                    {
                        "type": "command",
                        "command": f'"$CLAUDE_PROJECT_DIR"/.claude/hooks/{spec.script}',
                    }
                ],
            }
        )
    return json.dumps({"hooks": hooks})


def _project(tmp_path: Path, project: dict[str, object] | None = None) -> Path:
    repo = tmp_path / "repo"
    (repo / ".harness").mkdir(parents=True)
    if project is not None:
        _write(repo / ".harness/project.json", json.dumps(project))
    return repo


def _by_id(repo: Path) -> dict[str, dict[str, object]]:
    payload = collect_features(repo, which=lambda name: None)
    features = cast(list[dict[str, object]], payload["features"])
    return {cast(str, item["id"]): item for item in features}


def test_the_registry_lists_26_features_of_the_real_catalog_in_8_categories(
    tmp_path: Path,
) -> None:
    features = _by_id(_project(tmp_path))

    assert len(features) == 26
    assert len(features) == 22 + len(capability_options())
    assert {item["category"] for item in features.values()} == set(CATEGORIES)
    for name, _ in capability_options():
        assert f"capability:{name}" in features


def test_dependencies_resolve_have_no_cycle_and_required_by_is_their_reverse(
    tmp_path: Path,
) -> None:
    features = _by_id(_project(tmp_path))

    for feature_id, item in features.items():
        for parent in cast(list[str], item["depends_on"]):
            assert parent in features
            assert feature_id in cast(list[str], features[parent]["required_by"])
        for child in cast(list[str], item["required_by"]):
            assert feature_id in cast(list[str], features[child]["depends_on"])

    def visit(node: str, path: tuple[str, ...]) -> None:
        assert node not in path, path
        for parent in cast(list[str], features[node]["depends_on"]):
            visit(parent, (*path, node))

    for feature_id in features:
        visit(feature_id, ())


def test_a_feature_without_its_boolean_key_is_disabled_with_a_toggle(
    tmp_path: Path,
) -> None:
    features = _by_id(_project(tmp_path, {"base_branch": "main"}))

    memory = features["memory"]
    assert memory["state"] == "disabled"
    memory_toggle = cast(dict[str, object], memory["toggle"])
    assert {key: memory_toggle[key] for key in ("file", "path", "enabled")} == {
        "file": "project.json",
        "path": ["memory", "enabled"],
        "enabled": False,
    }
    attestation_toggle = cast(dict[str, object], features["attestation"]["toggle"])
    assert {key: attestation_toggle[key] for key in ("file", "path", "enabled")} == {
        "file": "orchestration.json",
        "path": ["worker_attestation_required"],
        "enabled": False,
    }
    assert cast(dict[str, object], features["retry"]["toggle"])["path"] == [
        "infrastructure_retry_policy",
        "enabled",
    ]
    toggled = {key for key, item in features.items() if item["toggle"] is not None}
    assert toggled == {"memory", "attestation", "retry"}


def test_a_missing_hook_file_makes_the_feature_not_working(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    _write(repo / ".claude/hooks/block-public-attribution.sh", "")

    features = _by_id(repo)

    assert features["artifact-location"]["state"] == "not_working"
    assert features["artifact-location"]["requirements"] == [
        {
            "title": "Файл хука отсутствует",
            "state": "err",
            "detail": ".claude/hooks/block-scratch-outside-docs-tasks.sh",
        }
    ]
    # Present but not wired anywhere: a critical hook is an error too.
    assert features["attribution"]["state"] == "not_working"


def test_an_unwired_non_critical_hook_makes_the_feature_partial(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    for script in ("protect-hook-policy.sh", "sensitive-path-recheck.sh"):
        _write(repo / ".claude/hooks" / script, "")
    _write(repo / ".claude/settings.local.json", _settings_with("protect-hook-policy.sh"))

    feature = _by_id(repo)["hook-policy"]

    assert feature["state"] == "partial"
    assert [item["state"] for item in cast(list[dict[str, str]], feature["requirements"])] == [
        "ok",
        "warn",
    ]
    assert cast(list[dict[str, object]], feature["settings"])[0] == {
        "file": "project.json",
        "path": ["hook_policy", "profile"],
        "present": False,
        "value": "standard (по умолчанию)",
    }


def test_wired_hooks_make_the_feature_working(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    _write(repo / ".claude/hooks/block-public-attribution.sh", "")
    _write(
        repo / ".claude/settings.local.json", _settings_with("block-public-attribution.sh")
    )

    assert _by_id(repo)["attribution"]["state"] == "working"


def test_enabled_memory_without_sources_is_partial(tmp_path: Path) -> None:
    features = _by_id(_project(tmp_path, {"memory": {"enabled": True}}))

    assert features["memory"]["state"] == "partial"
    assert cast(dict[str, object], features["memory"]["toggle"])["enabled"] is True


def test_enabling_memory_without_sources_is_forecast_partial(tmp_path: Path) -> None:
    # The "memory enabled without sources" requirement exists only once memory is enabled, so the
    # forecast evaluates the feature with the key flipped instead of reusing today's requirements.
    memory = _by_id(_project(tmp_path, {"base_branch": "main"}))["memory"]

    assert memory["state"] == "disabled"
    assert memory["requirements"] == []
    toggle = cast(dict[str, object], memory["toggle"])
    assert toggle["state_after"] == "partial"
    assert toggle["requirements_after"] == [
        {
            "title": "Память включена без источников",
            "state": "warn",
            "detail": "memory_policy.source_types, memory_policy.allow_paths",
        }
    ]


def test_the_forecast_follows_the_other_keys_and_the_switch_direction(tmp_path: Path) -> None:
    repo = _project(
        tmp_path,
        {"memory_policy": {"source_types": ["adr"], "allow_paths": ["docs/adr/"]}},
    )
    _write(
        repo / ".harness/orchestration.json",
        json.dumps({"worker_attestation_required": True}),
    )

    features = _by_id(repo)

    assert cast(dict[str, object], features["memory"]["toggle"])["state_after"] == "working"
    assert features["attestation"]["state"] == "working"
    assert cast(dict[str, object], features["attestation"]["toggle"])["state_after"] == "disabled"
    assert cast(dict[str, object], features["retry"]["toggle"])["state_after"] == "working"


def test_settings_values_are_masked_and_clipped(tmp_path: Path) -> None:
    repo = _project(
        tmp_path,
        {
            "qa_gate_commands": ["make lint", "x" * 300],
            "tracker": {"type": "github", "token": "ghp_secret"},
        },
    )

    features = _by_id(repo)

    qa_row = cast(list[dict[str, object]], features["qa-gate"]["settings"])[0]
    assert qa_row["present"] is True
    assert len(cast(str, qa_row["value"])) == 120
    tracker_row = cast(list[dict[str, object]], features["tracker"]["settings"])[0]
    assert "ghp_secret" not in cast(str, tracker_row["value"])
    assert features["tracker"]["requirements"] == [
        {"title": "CLI трекера не найден в PATH", "state": "warn", "detail": "gh"}
    ]


def test_an_unreadable_file_hides_its_rows_and_breaks_its_features(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    _write(repo / ".harness/project.json", "{not json")

    features = _by_id(repo)

    row = cast(list[dict[str, object]], features["ci-checks"]["settings"])[0]
    assert row["present"] is False
    assert {
        "title": "Файл конфигурации не читается",
        "state": "err",
        "detail": ".harness/project.json",
    } in cast(list[dict[str, object]], features["worktrees"]["requirements"])


def test_capabilities_follow_the_lock_and_digests_match_the_files(tmp_path: Path) -> None:
    repo = _project(tmp_path, {"base_branch": "main"})
    _write(
        repo / ".harness/harness.lock",
        json.dumps({"package_version": "1", "capabilities": ["mattpocock-suite"], "files": {}}),
    )

    payload = collect_features(repo, which=lambda name: None)
    features = {
        cast(str, item["id"]): item
        for item in cast(list[dict[str, object]], payload["features"])
    }

    assert features["capability:mattpocock-suite"]["state"] == "working"
    assert features["capability:engineering-suite"]["state"] == "disabled"
    assert features["capability:engineering-suite"]["depends_on"] == [
        "capability:mattpocock-suite"
    ]
    digests = cast(dict[str, str], payload["config_digests"])
    assert digests["orchestration.json"] == ""
    assert len(digests["project.json"]) == 64
    assert payload["transaction_pending"] is False


@pytest.mark.parametrize("engine", ["docker", "podman"])
def test_a_container_engine_missing_from_path_breaks_the_container_feature(
    tmp_path: Path, engine: str
) -> None:
    repo = _project(tmp_path)
    _write(
        repo / ".harness/orchestration.json",
        json.dumps(
            {"access_policy": {"defaults": {"container": {"engine": engine, "worker_image": "w"}}}}
        ),
    )

    features = _by_id(repo)

    assert features["containers"]["state"] == "not_working"
    assert {
        "title": "Движок контейнеров не найден в PATH",
        "state": "err",
        "detail": engine,
    } in cast(list[dict[str, object]], features["containers"]["requirements"])
