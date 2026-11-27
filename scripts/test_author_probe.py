#!/usr/bin/env python3
# Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
# SPDX-License-Identifier: BUSL-1.1
# Licensed under the Business Source License 1.1 (BSL-1.1).
# Commercial use, sale, or use in commercial application development is strictly
# prohibited without prior written permission from the copyright holder.
# Removing or altering this header is prohibited and voids all license rights.

"""Живая проба test-author: только сценарии clean-room, которые вызывают настоящий Claude Code.

`isolated_test_runner` подтверждает guard и Red, `full_route_worktree` — вызов автора внешним
developer в worker. Оба читают из контекста только `test_root`, поэтому остальные сценарии им не
нужны. Это не QA-стадия: `scripts/verify.py` по-прежнему запускает весь `SCENARIOS` (ADR 0023).
`make test-author-probe` задаёт флаги пробы и вызывает этот файл.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import test_clean_room
from scripts.clean_room import full_route_worktree, isolated_test_runner

PROBE_SCENARIOS = (isolated_test_runner, full_route_worktree)


def main() -> None:
    """Запустить сценарии пробы с корнем запуска, очисткой и строками длительности clean-room."""
    test_clean_room.main(PROBE_SCENARIOS)


if __name__ == "__main__":
    main()
