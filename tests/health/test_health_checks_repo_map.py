"""Тесты проверок состояния группы 'repo_map'."""

from __future__ import annotations

import json
from pathlib import Path

from harness.health.checks import repo_map as checks
from harness.health.context import HealthContext


def test_check_tier_skipped_when_repo_map_not_installed(tmp_path: Path) -> None:
    """Проверить, что проверка tier пропускается, если repo_map не установлен."""
    result = checks.check_tier(HealthContext(repo=tmp_path, lock=None, online=False))

    assert result.id == "repo_map.tier"
    assert result.group == "repo_map"
    assert result.status == "skipped"
    assert result.fix is None


def test_check_tier_warns_when_policy_requests_minimal(tmp_path: Path) -> None:
    """Проверить, что проверка tier выдает предупреждение, когда политика запрашивает minimal."""
    (tmp_path / ".harness" / "repo_map").mkdir(parents=True)
    (tmp_path / ".harness" / "repo_map" / "repo_map.py").write_text(
        "", encoding="utf-8"
    )
    orchestration = tmp_path / ".harness" / "orchestration.json"
    orchestration.write_text(
        '{"repo_map_policy": {"tier": "minimal"}}', encoding="utf-8"
    )

    result = checks.check_tier(HealthContext(repo=tmp_path, lock=None, online=False))

    assert result.status == "warn"
    assert result.message.startswith("Repo Map: tier=minimal (requested by policy)")
    assert result.fix is None


def _installed_repo_map(repo: Path, source_roots: list[str]) -> None:
    """Проект с установленным Repo Map и корнями импорта Python в политике."""
    (repo / ".harness" / "repo_map").mkdir(parents=True)
    (repo / ".harness" / "repo_map" / "repo_map.py").write_text("", encoding="utf-8")
    (repo / ".harness" / "orchestration.json").write_text(
        json.dumps({"repo_map_policy": {"python_source_roots": source_roots}}),
        encoding="utf-8",
    )
    (repo / "api_gateway").mkdir()
    (repo / "libs" / "tare" / "src").mkdir(parents=True)
    (repo / "libs" / "README.md").write_text("", encoding="utf-8")


def test_check_tier_names_a_source_root_pattern_without_a_directory(
    tmp_path: Path,
) -> None:
    """Шаблон `python_source_roots`, которому не отвечает ни один каталог, назван в сообщении."""
    _installed_repo_map(
        tmp_path, ["api_gateway/", "libs/*/src", "auth_manager", "core/*/src"]
    )

    result = checks.check_tier(HealthContext(repo=tmp_path, lock=None, online=False))

    assert result.status == "warn"
    assert (
        "python_source_roots: нет каталогов для шаблонов auth_manager, core/*/src"
        in result.message
    )


def test_check_tier_is_silent_about_source_roots_that_all_match(tmp_path: Path) -> None:
    """Совпавшие шаблоны `python_source_roots` в сообщение не попадают."""
    _installed_repo_map(tmp_path, ["api_gateway", "libs/*/src"])

    result = checks.check_tier(HealthContext(repo=tmp_path, lock=None, online=False))

    assert "python_source_roots" not in result.message
