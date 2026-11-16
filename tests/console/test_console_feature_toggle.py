"""A feature switch of the Diagnostics screen is the existing confirmed configuration write: the
request the web page builds (one boolean change and the digests of the snapshot it showed) passes
`configuration_writes.apply`, and a file changed since then is refused with the stale exit code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from harness.console.kernel import configuration_cli
from harness.console.kernel.configuration_writes import _STALE, apply
from harness.console.kernel.features import collect_features


def _project(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".harness").mkdir()
    (repo / ".harness/project.json").write_text(
        json.dumps(
            {
                "base_branch": "main",
                "branch_pattern": "^issue/[0-9]+-[a-z0-9-]+$",
                "language": "ru",
                "qa_gate_commands": ["make lint"],
            }
        ),
        encoding="utf-8",
    )
    return repo.resolve()


def _request(repo: Path, enabled: bool) -> str:
    """The request `togglePlan` + `draftRequest` build for the memory switch."""
    snapshot = collect_features(repo, which=lambda name: None)
    digests = cast(dict[str, str], snapshot["config_digests"])
    return json.dumps(
        {
            "changes": [{"file": "project.json", "path": ["memory", "enabled"], "value": enabled}],
            "expected": {"project.json": digests["project.json"]},
            "description": "Включить функцию «Память проекта»",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _memory(repo: Path) -> dict[str, object]:
    features = cast(list[dict[str, object]], collect_features(repo)["features"])
    return next(item for item in features if item["id"] == "memory")


def test_the_page_request_switches_the_feature_through_apply(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    assert _memory(repo)["state"] == "disabled"

    message = apply(repo, _request(repo, True))

    assert message.startswith("Конфигурация применена")
    document = json.loads((repo / ".harness/project.json").read_text(encoding="utf-8"))
    assert document["memory"] == {"enabled": True}
    assert document["base_branch"] == "main"
    assert _memory(repo)["state"] == "partial"


def test_a_file_changed_after_the_snapshot_is_the_stale_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _project(tmp_path)
    request = _request(repo, True)
    (repo / ".harness/project.json").write_text(
        json.dumps({"base_branch": "develop"}), encoding="utf-8"
    )

    code = configuration_cli.main(["apply", "--repo", str(repo), "--request", request])

    assert code == configuration_cli.STALE_EXIT
    assert capsys.readouterr().err.strip() == _STALE
    assert "memory" not in json.loads((repo / ".harness/project.json").read_text())
