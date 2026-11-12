"""Fixture payloads name their fake project as a POSIX path (`/work/project/...`). A payload
built through `Path` renders it with backslashes on Windows; `posix` restores the fixture form."""

from __future__ import annotations

import re

_FAKE_ROOT = re.compile(r"^\\work(\\|$)")


def posix(value: object) -> object:
    """`value` with every string under the fake `\\work` root written with `/` again."""
    if isinstance(value, str):
        return value.replace("\\", "/") if _FAKE_ROOT.match(value) else value
    if isinstance(value, dict):
        return {key: posix(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [posix(item) for item in value]
    return value
