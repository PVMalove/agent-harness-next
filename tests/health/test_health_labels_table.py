"""Модульные тесты парсера GFM-таблиц канонических меток."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from harness.health.checks import tracker
from harness.health.context import HealthContext
from harness.health.labels_table import parse_canonical_labels
from harness.health.project_tracker import ProjectTracker
from harness.uninstall import PROJECT_TEMPLATE_DIR, SEED_FOLDERS, seed_sources

HARNESS_ROOT = Path(__file__).resolve().parents[2]
GITHUB = ProjectTracker("github", "github.com", "acme/widgets", "origin")
NEW_LABELS = {"pr::ticket", "pr::integration", "rca::done", "status::done"}
TYPE_LABELS = {
    "type::bug",
    "type::feature",
    "type::refactoring",
    "type::chore",
    "type::security",
    "type::performance",
    "type::hotfix",
}


def test_parses_a_simple_label_color_table() -> None:
    """Проверить, что простая таблица меток и цветов корректно парсится."""
    text = """
| Label | Color | Meaning |
| --- | --- | --- |
| `hitl` | yellow `#fbca04` | Human-in-the-loop |
| `afk` | light blue `#54c1e8` | Away-from-keyboard |
"""
    assert parse_canonical_labels(text) == [
        ("hitl", "#fbca04"),
        ("afk", "#54c1e8"),
    ]


def test_ignores_a_table_without_a_color_column() -> None:
    """Проверить, что таблица без колонки цвета игнорируется."""
    text = """
| Label | Meaning |
| --- | --- |
| `type::bug` | Something is broken |
"""
    assert parse_canonical_labels(text) == []


def test_reads_multiple_tables_and_normalizes_case() -> None:
    """Проверить, что считываются несколько таблиц с нормализацией регистра цветов."""
    text = """
## Axis A

| Label | Color | Meaning |
| --- | --- | --- |
| `status::ready` | green `#0E8A16` | Ready |

## Axis B

| Label | Color | Applied by | Meaning |
| --- | --- | --- | --- |
| `task-report::required` | gray `#6a737d` | `/to-spec` | Required |
"""
    assert parse_canonical_labels(text) == [
        ("status::ready", "#0e8a16"),
        ("task-report::required", "#6a737d"),
    ]


def test_duplicate_label_keeps_first_occurrence() -> None:
    """Проверить, что при наличии дубликатов меток сохраняется первое вхождение."""
    text = """
| Label | Color | Meaning |
| --- | --- | --- |
| `hitl` | `#111111` | first |
| `hitl` | `#222222` | second |
"""
    assert parse_canonical_labels(text) == [("hitl", "#111111")]


def test_label_without_code_span_and_bare_hex_color() -> None:
    """Проверить, что распознаются метки без обратных кавычек и шестнадцатеричные цвета без префикса."""
    text = """
| Label | Color |
| --- | --- |
| bare-label | #abcdef |
"""
    assert parse_canonical_labels(text) == [("bare-label", "#abcdef")]


def test_row_missing_a_color_cell_is_skipped() -> None:
    """Проверить, что строки без корректного шестнадцатеричного цвета пропускаются."""
    text = """
| Label | Color | Meaning |
| --- | --- | --- |
| `no-color` | no hex here | Missing color |
| `ok-label` | `#123456` | Fine |
"""
    assert parse_canonical_labels(text) == [("ok-label", "#123456")]


def test_no_tables_returns_empty() -> None:
    """Проверить, что текст без таблиц возвращает пустой список меток."""
    assert parse_canonical_labels("Just prose, no tables here.\n") == []


def test_repository_triage_labels_are_recognized_with_expected_colors() -> None:
    """Проверить, что канонические метки репозитория распознаются с ожидаемыми цветами."""
    text = (HARNESS_ROOT / "harness" / "project" / "instructions" / "triage-labels.md").read_text(
        encoding="utf-8"
    )

    labels = dict(parse_canonical_labels(text))

    assert labels["status::ready"] == "#0e8a16"
    assert labels["hitl"] == "#fbca04"
    assert labels["afk"] == "#54c1e8"
    assert labels["task-report::required"] == "#6a737d"


REPOSITORY_TRIAGE_LABELS = HARNESS_ROOT / "harness" / "project" / "instructions" / "triage-labels.md"


def _repository_labels() -> dict[str, str]:
    return dict(parse_canonical_labels(REPOSITORY_TRIAGE_LABELS.read_text(encoding="utf-8")))


def test_pr_rca_and_done_labels_are_canonical_with_their_colors() -> None:
    """Проверить, что метки PR, RCA и терминального статуса разобраны со своими цветами (#1024)."""
    labels = _repository_labels()

    assert labels["pr::ticket"] == "#0075ca"
    assert labels["pr::integration"] == "#006b75"
    assert labels["rca::done"] == "#d4c5f9"
    assert labels["status::done"] == "#2ea44f"


def test_every_canonical_label_has_a_distinct_color() -> None:
    """Проверить, что ни одна каноническая метка не делит цвет с другой."""
    colors = list(_repository_labels().values())

    assert len(colors) == len(set(colors)), sorted(colors)


def test_type_axis_is_parsed_while_informational_axes_are_skipped() -> None:
    """Проверить, что вся ось `type::*` разбирается, а `priority::*`/`severity::*`/`env::*` пропускаются."""
    labels = _repository_labels()

    assert {name for name in labels if name.startswith("type::")} == TYPE_LABELS
    informational = {"priority", "severity", "env"}
    assert [name for name in labels if name.split("::")[0] in informational] == []


def test_tracker_labels_reads_the_seeded_guide_and_reports_the_new_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Проверить, что `tracker.labels` по сидированной копии гайда видит четыре новые метки отсутствующими."""
    target_dir, suffixes = next(
        (target, suffixes) for folder, target, suffixes in SEED_FOLDERS if folder == "instructions"
    )
    sources = {source.resolve() for source in seed_sources(PROJECT_TEMPLATE_DIR, "instructions", suffixes)}
    assert REPOSITORY_TRIAGE_LABELS.resolve() in sources

    seeded = tmp_path / target_dir / REPOSITORY_TRIAGE_LABELS.name
    seeded.parent.mkdir(parents=True)
    shutil.copyfile(REPOSITORY_TRIAGE_LABELS, seeded)
    existing = [(name, color) for name, color in _repository_labels().items() if name not in NEW_LABELS]
    monkeypatch.setattr(tracker, "detect_tracker", lambda _context: GITHUB)
    monkeypatch.setattr(shutil, "which", lambda tool: f"/usr/bin/{tool}")
    monkeypatch.setattr(tracker, "_list_repo_labels", lambda *_args: existing)

    result = tracker.check_labels(HealthContext(repo=tmp_path, lock=None, online=True))

    assert result.status == "warn"
    missing = result.message.split("отсутствуют: ", 1)[1].split(";")[0]
    assert set(missing.split(", ")) == NEW_LABELS
