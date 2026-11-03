"""Тесты заполнения поля tracker в .harness/project.json при установке харнесса из origin."""

from __future__ import annotations

import ctypes
import sys
from types import SimpleNamespace

import pytest

from harness.bin import harness as harness_cli

# Every non-tracker project.json value, so that only the tracker is left to prompt for.


class _CharacterDevice:
    """Заглушка stdin — символьное устройство, для которого `isatty()` истинен (консоль или NUL)."""

    def isatty(self) -> bool:
        return True

    def fileno(self) -> int:
        return 0


@pytest.mark.parametrize(("console_mode_result", "expected"), [(0, False), (1, True)])
def test_windows_stdin_is_a_terminal_only_for_a_console(
    monkeypatch: pytest.MonkeyPatch, console_mode_result: int, expected: bool
) -> None:
    """Проверить, что на Windows stdin NUL — не терминал, хотя `isatty()` для него истинен."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "stdin", _CharacterDevice())
    monkeypatch.setitem(
        sys.modules, "msvcrt", SimpleNamespace(get_osfhandle=lambda fd: 7)
    )
    kernel32 = SimpleNamespace(GetConsoleMode=lambda handle, mode: console_mode_result)
    monkeypatch.setattr(
        ctypes, "windll", SimpleNamespace(kernel32=kernel32), raising=False
    )

    assert harness_cli._stdin_is_terminal() is expected
