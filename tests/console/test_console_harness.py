"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

import pytest

pytest.importorskip("textual")

from harness.console.catalog import (
    HARNESS_COMMANDS,
)


def test_every_harness_command_belongs_to_a_menu_group() -> None:
    from harness.console.screens.harness import _GROUPS

    assert {entry.key for entry in HARNESS_COMMANDS} <= set(_GROUPS)
