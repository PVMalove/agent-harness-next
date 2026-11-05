"""Тесты проверок состояния каталогов и механизма их восстановления через --fix."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from harness.health.checks import directories
from harness.health.context import HealthContext


def _context(repo: Path, lock: dict[str, object] | None = None) -> HealthContext:
    """Создать контекст проверки для указанного репозитория и lock-файла."""
    return HealthContext(repo=repo, lock=lock, online=False)


def _check(
    check_id: str, repo: Path, lock: dict[str, object] | None = None
) -> dict[str, str]:
    """Выполнить указанную проверку каталога и вернуть словарь со статусом и сообщением."""
    result = directories.make_check(check_id)(_context(repo, lock))
    return {"status": result.status, "message": result.message}


# --- Unit: classification ---------------------------------------------------------------------


def test_missing_directory_with_writable_parent_is_ok_and_will_be_created(
    tmp_path: Path,
) -> None:
    """Проверить, что отсутствующий каталог при доступном для записи родителе считается ok."""
    result = _check("directories.cache", tmp_path)

    assert result["status"] == "ok"
    assert "будет создан" in result["message"]
    assert not (tmp_path / ".harness").exists()  # the check itself creates nothing


def test_file_in_place_of_directory_fails(tmp_path: Path) -> None:
    """Проверить, что наличие файла на месте ожидаемого каталога приводит к ошибке."""
    (tmp_path / ".harness").mkdir()
    (tmp_path / ".harness" / ".sandboxes").write_text("", encoding="utf-8")

    assert _check("directories.sandboxes", tmp_path)["status"] == "fail"


def test_existing_unwritable_directory_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Проверить, что существующий каталог, недоступный для записи, приводит к ошибке."""
    logs = tmp_path / ".harness" / ".sandboxes" / "logs"
    logs.mkdir(parents=True)
    real_access = os.access
    monkeypatch.setattr(
        os,
        "access",
        lambda path, mode: False if Path(path) == logs else real_access(path, mode),
    )

    result = _check("directories.logs", tmp_path)

    assert result["status"] == "fail"
    assert ".harness/.sandboxes/logs" in result["message"]


def test_missing_directory_under_unwritable_ancestor_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Проверить, что невозможность создать каталог из-за недоступного предка приводит к ошибке."""
    harness = tmp_path / ".harness"
    harness.mkdir()
    real_access = os.access
    monkeypatch.setattr(
        os,
        "access",
        lambda path, mode: False if Path(path) == harness else real_access(path, mode),
    )

    assert _check("directories.runs", tmp_path)["status"] == "fail"


def test_orchestration_state_depends_on_the_capability(tmp_path: Path) -> None:
    """Проверить, что проверка каталога состояния оркестрации зависит от соответствующей возможности."""
    assert _check("directories.orchestration_state", tmp_path)["status"] == "skipped"
    lock: dict[str, object] = {"capabilities": ["backend-orchestration"]}
    assert _check("directories.orchestration_state", tmp_path, lock)["status"] == "ok"


# --- Process: `harness health --json [--fix]` -------------------------------------------------
