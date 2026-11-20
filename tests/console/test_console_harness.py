"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

import pytest

pytest.importorskip("textual")

from harness.console.kernel.catalog import (
    HARNESS_COMMANDS,
)


def test_every_harness_command_belongs_to_a_menu_group() -> None:
    from harness.console.tui.screens.harness import _GROUPS

    assert {entry.key for entry in HARNESS_COMMANDS} <= set(_GROUPS)


def test_the_harness_screen_is_a_console_server_client() -> None:
    """Harness reads its facts and runs its commands through the server client only: no local
    runner, ledger, drift or cleanup collection is injected or referenced."""
    import ast
    import inspect
    from pathlib import Path

    from harness.console.tui.screens import harness

    parameters = inspect.signature(harness.HarnessScreen).parameters
    assert parameters["client"].default is inspect.Parameter.empty
    assert not {"command_runner", "load_drift", "load_view"} & set(parameters)
    assert "client" in inspect.signature(harness.CommandFormScreen).parameters
    tree = ast.parse(Path(harness.__file__).read_text(encoding="utf-8"))
    names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    names |= {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    local = {
        "plan_cleanup",
        "worktree_facts",
        "load_maintenance",
        "path_size",
        "capturing_runner",
        "load_ledger_view",
        "drift_state",
        "harness_state",
    }
    assert not local & names
    assert "ServerJobRunner" in names
