# Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
# SPDX-License-Identifier: BUSL-1.1
# Licensed under the Business Source License 1.1 (BSL-1.1).
# Commercial use, sale, or use in commercial application development is strictly
# prohibited without prior written permission from the copyright holder.
# Removing or altering this header is prohibited and voids all license rights.

"""Общий базовый класс ошибок для Python-модулей harness.

Каждое специфичное для harness исключение содержит `.message` (описание проблемы) и `.remedy`
(конкретное действие для исправления) вместо простой строки, чтобы вызывающая сторона могла
отреагировать на ошибку без чтения исходного кода. Конструктор принимает ровно один из именованных
параметров: `remedy` (текст) или `fmea` (`FmeaId`), и тогда remedy берётся из поля `recovery`
записи каталога `harness/fmea/catalog.toml`.
См. docs/adr/0007-python-quality.md и docs/adr/0041-fmea-catalog-remedy.md.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from harness.fmea.ids import FmeaId


class HarnessError(Exception):
    """Базовый класс для всех ошибок harness. Подклассы не добавляют собственного поведения."""

    @overload
    def __init__(self, message: str, *, remedy: str) -> None: ...

    @overload
    def __init__(self, message: str, *, fmea: FmeaId) -> None: ...

    def __init__(
        self, message: str, *, remedy: str | None = None, fmea: FmeaId | None = None
    ) -> None:
        """Инициализировать ошибку сообщением и remedy: текстом или id режима отказа FMEA."""
        super().__init__(message)
        self.message = message
        self.fmea = fmea
        self.fmea_title: str | None = None
        if remedy is not None and fmea is None:
            self.remedy = remedy
            return
        if remedy is not None or fmea is None:
            raise TypeError("HarnessError needs exactly one of remedy and fmea")
        # Lazy import: harness.fmea.catalog imports this module at load time.
        from harness.fmea.catalog import find_entry

        entry = find_entry(fmea)
        if entry is None or not entry.recovery:
            raise HarnessError(
                f"FMEA id {fmea} is not in harness/fmea/catalog.toml or has no recovery",
                remedy=INTERNAL_INVARIANT_REMEDY,
            )
        self.remedy = entry.recovery
        self.fmea_title = entry.title


class PolicyError(HarnessError):
    """Проектная политика не может быть безопасно применена."""


INTERNAL_INVARIANT_REMEDY = (
    "internal invariant violated -- stop and run the RCA phase of the diagnosing-bugs skill"
    " with this traceback"
)


def print_and_exit(exc: HarnessError) -> int:
    """Вывести сообщение и рекомендацию HarnessError в stderr и вернуть код завершения CLI.

    Возвращает 2 вместо прямого вызова `sys.exit`, сохраняя стандартный контракт точек входа.
    """
    text = f"ERROR: {exc.message}\nREMEDY: {exc.remedy}"
    if exc.fmea is not None:
        text += f"\nFMEA: {exc.fmea.value} ({exc.fmea_title})"
    print(text, file=sys.stderr)
    return 2
