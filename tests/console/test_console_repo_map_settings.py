"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.configuration_store import ConfigurationStore
from harness.console.kernel.repo_map_settings import (
    DEFAULT_MEMORY_POLICY,
    apply_tier,
    enable_memory,
    tier_setting,
)
from harness.repo_map.bundle_fetch import ParserStatus
from tests.console._configuration_fixture import (
    _orchestration_project,
    installed_project,
)


def test_the_tier_cannot_be_changed_without_orchestration(tmp_path: Path) -> None:
    installed_project(tmp_path)
    setting = tier_setting(tmp_path)
    assert (setting.tier, setting.editable) == ("full", False)
    assert "backend-orchestration" in setting.reason


def test_the_tier_is_written_to_the_policy_and_the_previous_files_are_kept(
    tmp_path: Path,
) -> None:
    _orchestration_project(tmp_path)
    assert tier_setting(tmp_path).tier == "full"
    backup = apply_tier(tmp_path, "minimal")
    written = json.loads((tmp_path / ".harness/orchestration.json").read_bytes())
    assert written["repo_map_policy"]["tier"] == "minimal"
    assert tier_setting(tmp_path).tier == "minimal"
    assert backup in {version.id for version in ConfigurationStore(tmp_path).versions()}
    apply_tier(tmp_path, "full")
    assert tier_setting(tmp_path).tier == "full"
    with pytest.raises(ValueError):
        apply_tier(tmp_path, "huge")


def test_an_existing_memory_policy_is_kept(tmp_path: Path) -> None:
    installed_project(tmp_path)
    path = tmp_path / ".harness/project.json"
    document = json.loads(path.read_bytes())
    own = {**DEFAULT_MEMORY_POLICY, "top_k": 9}
    document["memory_policy"] = own
    path.write_text(json.dumps(document))
    enable_memory(tmp_path)
    assert json.loads(path.read_bytes())["memory_policy"] == own


def _status(*, ready: bool, languages: tuple[str, ...] = ()) -> ParserStatus:
    return ParserStatus(
        Path("/registry"),
        "cp314-linux_x86_64" if ready else None,
        "local-cache" if ready else None,
        tuple(languages),
        None if ready else "offline parser bundle unavailable",
    )


def _checks(**given: object) -> list[tuple[str, str]]:
    from harness.console.kernel.repo_map_settings import (
        MemoryStatus,
        TierSetting,
        repo_map_checks,
    )

    base: dict[str, object] = {
        "head": "a" * 40,
        "tier": TierSetting("full", True),
        "parsers": _status(ready=False),
        "files": {"python": 3, "go": 2},
        "memory": MemoryStatus(False, False, (), None),
        "view": None,
    }
    result = repo_map_checks(**{**base, **given})  # type: ignore[arg-type]
    return [(check.level, check.text) for check in result]


def test_the_checks_name_what_blocks_the_full_map_and_how_to_fix_it() -> None:
    lines = _checks()
    assert lines[0] == ("ok", "HEAD aaaaaaaaaaaa")
    text = "\n".join(f"{level}: {line}" for level, line in lines)
    assert "fail: Bundle парсеров не готов: offline parser bundle unavailable" in text
    assert "«Установить выбранные»" in text
    assert "skipped: Карта для HEAD не построена" in text
    assert "skipped: Память проекта выключена" in text


def test_the_checks_compare_project_languages_with_installed_parsers() -> None:
    lines = _checks(parsers=_status(ready=True, languages=("python",)))
    text = "\n".join(f"{level}: {line}" for level, line in lines)
    assert "ok: Python: парсер установлен, файлов: 3" in text
    assert "warn: Go: парсер не установлен" in text
    assert "ok: Bundle парсеров готов: cp314-linux_x86_64" in text


def test_minimal_mode_and_a_missing_head_are_reported() -> None:
    from harness.console.kernel.repo_map_settings import TierSetting

    lines = _checks(head=None, tier=TierSetting("minimal", True))
    text = "\n".join(f"{level}: {line}" for level, line in lines)
    assert "fail: HEAD не найден" in text
    assert "skipped: Режим minimal: парсер не нужен" in text
    assert "Bundle" not in text


def test_enabling_memory_without_any_documents_says_so(tmp_path: Path) -> None:
    from harness.console.kernel.repo_map_settings import plan_memory_enable

    installed_project(tmp_path)
    path = tmp_path / ".harness/project.json"
    document = json.loads(path.read_bytes())
    document["memory"] = {"enabled": True}
    document["memory_policy"] = {**DEFAULT_MEMORY_POLICY, "allow_paths": []}
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="нет документов для памяти"):
        plan_memory_enable(tmp_path)
