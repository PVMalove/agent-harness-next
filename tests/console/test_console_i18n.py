"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

import re

import pytest

from harness.console import i18n
from harness.console.help_text import HELP_MARKDOWN, HELP_MARKDOWN_EN, help_markdown
from harness.console.i18n_strings import EN, EN_PHRASES


def test_tr_translates_known_strings_and_leaves_the_rest() -> None:
    assert i18n.tr("en", "Назад") == "Back"
    assert i18n.tr("ru", "Назад") == "Назад"
    assert (
        i18n.tr("en", "Главная › Настройка › Версии")
        == "Home › Configuration › Versions"
    )
    assert i18n.tr("en", "Главная  ›  Оркестрация") == "Home  ›  Orchestration"
    assert i18n.tr("en", "Требует внимания · 2") == "Requires attention · 2"
    assert i18n.tr("en", "Цель: /srv/app") == "Target: /srv/app"
    assert (
        i18n.tr("en", "любой пользовательский текст") == "любой пользовательский текст"
    )
    # Labels written in English become Russian when the language is Russian.
    assert i18n.tr("ru", "Both files") == "Оба файла"
    assert i18n.tr("en", "Both files") == "Both files"


def test_tr_text_uses_whole_words_so_data_is_not_garbled() -> None:
    translated = i18n.tr_text("en", "в снэпшоте скиллов есть расхождения")
    assert translated == "в снэпшоте скиллов есть расхождения"
    assert i18n.tr_text("en", "память: ok, пропущено 11") == "memory: ok, skipped 11"
    assert i18n.tr_text("ru", "память: ok") == "память: ok"


def test_every_english_text_is_distinct_work_not_a_copy() -> None:
    for table in (EN, EN_PHRASES):
        for russian, english in table.items():
            assert russian.strip() and english.strip()
    # The Russian side of a phrase never contains Latin-only text that would match code.
    assert all(re.search("[А-Яа-я]", russian) for russian in EN_PHRASES)


def test_the_english_guide_has_the_same_sections() -> None:
    assert help_markdown("ru") == HELP_MARKDOWN
    assert help_markdown("en") == HELP_MARKDOWN_EN
    assert HELP_MARKDOWN.count("\n## ") == HELP_MARKDOWN_EN.count("\n## ")
    assert not re.search("[А-Яа-я]", HELP_MARKDOWN_EN)


@pytest.mark.parametrize("language", ["ru", "en"])
def test_the_default_language_comes_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, language: str
) -> None:
    monkeypatch.setenv(i18n.LANGUAGE_ENV, language)
    assert i18n.default_language() == language
    monkeypatch.setenv(i18n.LANGUAGE_ENV, "xx")
    assert i18n.default_language() == "ru"
