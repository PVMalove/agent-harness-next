"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

import re

import pytest

from harness.console.kernel import i18n
from harness.console.kernel.i18n_strings import EN, EN_PHRASES
from harness.console.tui.help_text import HELP_MARKDOWN, HELP_MARKDOWN_EN, help_markdown


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


# ----------------------------------------------------------------------------- container route (#711)

import ast  # noqa: E402
import inspect  # noqa: E402
from collections.abc import Callable  # noqa: E402
from pathlib import Path  # noqa: E402

from harness.console.kernel import container_route as route_model  # noqa: E402
from harness.console.tui.screens import container_route as route_screen  # noqa: E402
from harness.console.tui.screens.orchestration import OrchestrationScreen  # noqa: E402
from tests.console.test_console_container_route import (  # noqa: E402
    AUTHORED_DOCUMENT,
    SECRET,
    ScriptedCoordinator,
    make_session,
    plan_document,
    preflight_document,
    verification,
)

_CYRILLIC = re.compile("[А-Яа-я]")


def _russian_fixed_texts(module: object) -> set[str]:
    """Every Russian string literal of a module outside docstrings."""
    tree = ast.parse(inspect.getsource(module))  # type: ignore[arg-type]
    documentation = {
        ast.get_docstring(node, clean=False)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef))
    }
    found: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _CYRILLIC.search(node.value)
            and node.value not in documentation
        ):
            found.add(node.value)
    return found


@pytest.mark.parametrize("module", [route_model, route_screen])
def test_every_fixed_text_of_the_container_route_has_an_english_form(
    module: object,
) -> None:
    missing = sorted(
        text
        for text in _russian_fixed_texts(module)
        if _CYRILLIC.search(i18n.tr_text("en", text))
    )
    assert missing == []


def test_english_rendering_of_a_populated_pane_has_no_russian_left() -> None:
    session, scripted = make_session()
    scripted.reply(
        "dispatch preflight",
        preflight_document(
            verified=verification(
                "verified",
                evidence={
                    "engine": "podman",
                    "engine_mode": "rootless",
                    "transport": "external",
                },
            )
        ),
    )
    session.select("batch-1")
    session.recheck()
    for stage in route_model.Stage:
        text = route_screen.render_view(session.view(stage), "en", narrow=False)
        assert not _CYRILLIC.search(text), (
            stage,
            [line for line in text.split("\n") if _CYRILLIC.search(line)],
        )


def test_a_row_is_an_icon_plus_label_and_a_long_value_is_never_cut() -> None:
    digest = "sha256:" + "f" * 64
    row = route_model.Row("plan_digest", digest, route_model.State.OK)
    wide = route_screen.render_row(row, "ru", narrow=False)
    narrow = route_screen.render_row(row, "ru", narrow=True)
    assert wide == f"✔ ок  plan_digest: {digest}"
    assert narrow == f"✔ ок  plan_digest\n    {digest}"
    assert "…" not in wide and "…" not in narrow
    assert route_screen.render_row(row, "en", narrow=False).startswith(
        "✔ ok  plan_digest"
    )
    unknown = route_model.Row("Состояние", "", route_model.State.NOT_CHECKED)
    assert (
        route_screen.render_row(unknown, "en", narrow=False) == "○ not checked  Status"
    )


def test_a_multiline_value_keeps_every_line_reachable_in_both_layouts() -> None:
    row = route_model.Row("Монтирования", "a /one\nb /two\nc /three")
    for narrow in (False, True):
        text = route_screen.render_row(row, "ru", narrow)
        assert all(line in text for line in ("a /one", "b /two", "c /three"))


def test_the_pane_lists_blockers_first_and_every_unavailable_action_with_its_reason() -> (
    None
):
    session, _ = make_session()
    view = session.view(route_model.Stage.PREFLIGHT)
    text = route_screen.render_view(view, "ru", narrow=True)
    assert "✖ недоступно: Перепроверить — выберите batch и роль" in text
    english = route_screen.render_view(view, "en", narrow=True)
    assert "✖ unavailable: Re-check — choose a batch and a role" in english
    blocked = route_model.StageView(route_model.Stage.PLAN, (), (), ("ERROR: x",))
    assert route_screen.render_view(blocked, "ru", False).startswith(
        "✖ Блокирует маршрут\n  ERROR: x"
    )


def test_tab_labels_pair_an_icon_with_the_title_and_bracket_the_current_one() -> None:
    session, _ = make_session()
    tabs = session.tabs()
    labels = [
        route_screen.tab_label(tab, "ru", tab.stage is route_model.Stage.SETUP)
        for tab in tabs
    ]
    assert labels[0] == "[· Setup]"
    assert labels[1].startswith("○ Preflight")
    assert route_screen.tab_label(tabs[2], "ru", False).startswith("✖ ")


def test_the_screen_is_a_shell_view_inside_orchestration_with_a_narrow_layout() -> None:
    from harness.console.tui.shell import ConsoleShell

    screen = route_screen.ContainerRouteScreen
    assert issubclass(screen, ConsoleShell)
    assert screen.SECTION == "Orchestration" and screen.IS_SECTION_ROOT is False
    assert i18n.tr("en", screen.CRUMBS) == "Home › Orchestration › Container route"
    assert "ContainerRouteScreen.-narrow #route-select { layout: vertical" in screen.CSS
    assert (
        "ContainerRouteScreen.-narrow #route-actions { layout: vertical" in screen.CSS
    )
    assert {"escape", "enter", "f2"} <= set(screen.NARROW_FOOTER_KEYS or ())
    assert ("Orchestration" in OrchestrationScreen.SECTION) and hasattr(
        OrchestrationScreen, "open_container_route"
    )
    assert "container-route" in inspect.getsource(OrchestrationScreen.compose_content)


def test_every_stage_fits_the_fixed_pool_of_action_buttons() -> None:
    session, _ = make_session()
    for stage in route_model.Stage:
        assert len(session.view(stage).actions) <= route_screen.MAX_ACTIONS


def test_the_route_screen_never_names_a_forbidden_flag_or_a_secret() -> None:
    source = Path(inspect.getsourcefile(route_screen) or "").read_text(encoding="utf-8")
    for token in ("--docker", "--auto-approve", "dangerously", "permission-mode"):
        assert token not in source
    session, _ = make_session()
    assert SECRET not in "".join(
        route_screen.render_view(session.view(stage), "ru", False)
        for stage in route_model.Stage
    )
    assert AUTHORED_DOCUMENT and plan_document()["plan_digest"]


def test_executor_context_strip_joins_worker_qa_and_labels() -> None:
    text = route_screen.context_text(
        (("Worker", "dispatch-1"), ("QA", "не создан")), "en"
    )
    assert text == "Worker: dispatch-1  ·  QA: not created"
    assert isinstance(ScriptedCoordinator(), ScriptedCoordinator)


# ----------------------------------------------------------------------------- recovery screen (#711)

from harness.console.kernel import batch_history as history_model  # noqa: E402
from harness.console.kernel import recovery_view as recovery_model  # noqa: E402
from harness.console.tui.screens import recovery as recovery_screen  # noqa: E402
from tests.console.test_console_recovery_view import (  # noqa: E402
    held_document,
    session_with,
    status_document,
    unknown_document,
)


@pytest.mark.parametrize("module", [recovery_model, history_model, recovery_screen])
def test_every_fixed_text_of_the_recovery_screen_has_an_english_form(
    module: object,
) -> None:
    missing = sorted(
        text
        for text in _russian_fixed_texts(module)
        if _CYRILLIC.search(i18n.tr_text("en", text))
    )
    assert missing == []


@pytest.mark.parametrize("document", [held_document, status_document, unknown_document])
def test_english_recovery_pane_has_no_russian_left_and_ru_keeps_the_banner(
    document: Callable[[], dict[str, object]],
) -> None:
    session, _ = session_with(document())
    view = session.view()
    english = route_screen.render_body(
        view.rows, view.blockers, view.notes, view.actions, "en", narrow=False
    )
    assert not _CYRILLIC.search(english), [
        line for line in english.split("\n") if _CYRILLIC.search(line)
    ]
    russian = route_screen.render_body(
        view.rows, view.blockers, view.notes, view.actions, "ru", narrow=True
    )
    if view.unknown_outcome:
        assert "Мы не знаем, запустился ли агент" in russian
        assert "We do not know whether the agent started" in english
        assert "effect_state" in english and "no engine response" in english


def test_the_reason_precedes_every_action_and_unavailable_actions_carry_their_reason() -> (
    None
):
    session, _ = session_with(held_document())
    view = session.view()
    text = route_screen.render_body(
        view.rows, view.blockers, view.notes, view.actions, "ru", narrow=False
    )
    assert text.index("Причина") < text.index("недоступно")
    assert "✖ недоступно: Resume — core reason for resume" in text


def test_the_recovery_screen_is_a_shell_view_inside_orchestration_in_both_layouts() -> (
    None
):
    from harness.console.tui.shell import ConsoleShell

    screen = recovery_screen.RecoveryScreen
    assert issubclass(screen, ConsoleShell)
    assert screen.SECTION == "Orchestration" and screen.IS_SECTION_ROOT is False
    assert i18n.tr("en", screen.CRUMBS) == "Home › Orchestration › Recovery"
    assert "RecoveryScreen.-narrow #recovery-actions { layout: vertical" in screen.CSS
    assert hasattr(OrchestrationScreen, "open_recovery")
    assert "open-recovery" in inspect.getsource(OrchestrationScreen.compose_content)


def test_every_recovery_view_fits_the_fixed_pool_of_action_buttons() -> None:
    for document in (held_document, status_document, unknown_document):
        session, _ = session_with(document())
        assert (
            len(session.view().actions) + 1 <= recovery_screen.MAX_ACTIONS
        )  # + the write action


def test_a_long_pointer_and_diagnostic_value_stay_fully_reachable_in_the_pane() -> None:
    pointer = "/access_policy/roles/" + "very-long-role-name/" * 8 + "mode"
    session, _ = session_with(
        status_document(
            resumable=False,
            diagnostics=[
                {
                    "id": "d1",
                    "code": "config-invalid",
                    "check": "config",
                    "pointer": pointer,
                    "fatal": True,
                    "received_redacted": "x" * 300,
                }
            ],
        )
    )
    view = session.view()
    for narrow in (False, True):
        text = route_screen.render_body(
            view.rows, view.blockers, view.notes, view.actions, "ru", narrow
        )
        assert pointer in text and "x" * 300 in text and "…" not in text
