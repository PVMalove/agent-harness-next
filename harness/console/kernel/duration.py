"""One duration wording for the whole console, the same as the web console's `compactDuration`:
the two largest units of `дн`, `ч`, `мин` (`d`, `h`, `min`), and seconds only under a minute."""

from __future__ import annotations


def compact_duration(seconds: int | float | None, language: str = "ru") -> str:
    """`6 дн 1 ч`, `2 ч 7 мин`, `5 мин`, `42 с`; a zero second unit is left out, and an unknown
    duration is `—`."""
    if seconds is None:
        return "—"
    total = max(0, int(seconds))
    day, hour, minute, second = (
        ("d", "h", "min", "s") if language == "en" else ("дн", "ч", "мин", "с")
    )
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days} {day} {hours} {hour}" if hours else f"{days} {day}"
    if hours:
        return f"{hours} {hour} {minutes} {minute}" if minutes else f"{hours} {hour}"
    if minutes:
        return f"{minutes} {minute}"
    return f"{total} {second}"
