"""Fixture payloads name their fake project as a POSIX path (`/work/project/...`). A payload
built through `Path` renders it with backslashes on Windows, and `shlex.quote` then wraps such a
path in quotes; `posix` restores the fixture form. It changes nothing on other platforms."""

from __future__ import annotations

import os
import re

_FAKE_ROOT = re.compile(r"'?\\work(?:\\[^\s'\"]*)*'?")


def _posix_path(found: re.Match[str]) -> str:
    return found.group().strip("'").replace("\\", "/")


def posix(value: object) -> object:
    """`value` with every fake `\\work` path inside its strings written as the fixture has it."""
    if os.name != "nt":
        return value
    if isinstance(value, str):
        return _FAKE_ROOT.sub(_posix_path, value)
    if isinstance(value, dict):
        return {key: posix(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [posix(item) for item in value]
    return value
