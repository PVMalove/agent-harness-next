"""One duration wording for the whole console, the same as the web console's `compactDuration`."""

from __future__ import annotations

import pytest

from harness.console.kernel.duration import compact_duration


@pytest.mark.parametrize(
    ("seconds", "language", "shown"),
    [
        (None, "ru", "—"),
        (42, "ru", "42 с"),
        (5 * 60 + 12, "ru", "5 мин"),
        (2 * 3600 + 7 * 60, "ru", "2 ч 7 мин"),
        (2 * 3600, "ru", "2 ч"),
        (6 * 86400 + 3600 + 59, "ru", "6 дн 1 ч"),
        (6 * 86400, "ru", "6 дн"),
        (6 * 86400 + 3600, "en", "6 d 1 h"),
        (-5, "en", "0 s"),
    ],
)
def test_the_two_largest_units_and_seconds_only_under_a_minute(
    seconds: int | None, language: str, shown: str
) -> None:
    assert compact_duration(seconds, language) == shown
