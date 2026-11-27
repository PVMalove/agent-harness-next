"""The shared look of a worker session: a role label, the ticket, the dispatch and a status caption.

The dashboard's session list and the worker view's session list build their cards here, so a role
and a state read the same on both. Status is never colour alone: the caption is the status symbol
plus words, and the role label is the role's name."""

from __future__ import annotations

from datetime import datetime
import unicodedata

from rich.table import Table
from rich.text import Text

from ..kernel import brand
from ..kernel.duration import compact_duration
from ..kernel.status import Status, session_status
from . import icons


def role_label(role: str) -> Text:
    """The role name in its own colour; a role outside `brand.ROLE_COLORS` is shown plainly in the muted tone."""
    color = brand.ROLE_COLORS.get(role, brand.PALETTE["muted"])
    return Text(role, style=f"bold {color}")


def status_caption(status: Status, language: str) -> Text:
    """The status as symbol plus words, in the status colour."""
    return Text(icons.render_status(status, language), style=status.color)


def session_card(
    *,
    ticket: str,
    role: str,
    dispatch_id: str,
    state: str,
    language: str,
    id_limit: int,
    stacked: bool = False,
    outcome: str = "",
) -> Text:
    """Ticket and role on the first line, then the shortened dispatch ID and the status caption:
    on one line, or each on its own when `stacked` (a narrow list). A failed or blocked report
    `outcome` replaces the «Отчёт получен» caption."""
    card = Text(f"{ticket}  ·  ", style=brand.PALETTE["foreground"])
    card.append_text(role_label(role))
    card.append("\n")
    card.append(
        brand.shorten(brand.short_dispatch(dispatch_id), id_limit)
        + ("\n" if stacked else " · "),
        style=brand.PALETTE["muted"],
    )
    card.append_text(status_caption(session_status(state, outcome), language))
    return card


def elapsed_text(start: datetime | None, now: datetime, language: str) -> str:
    """How long ago `start` was, in the largest unit of `compact_duration`: `2 мин`, `3 ч`,
    `2 дн` — as the web console cuts an age; empty when the start is unknown or later than `now`."""
    if start is None or start > now:
        return ""
    whole = compact_duration(int((now - start).total_seconds()), language)
    return " ".join(whole.split()[:2])


def session_row(
    *,
    ticket: str,
    role: str,
    dispatch_id: str,
    state: str,
    language: str,
    elapsed: str,
    title: str = "",
    narrow: bool = False,
) -> Table:
    """One line per session: ticket and role, the dispatch (cut to the room left), the status
    caption and how long ago the dispatch was recorded."""
    # Fixed widths for all but the dispatch, so the rows of a list line up in columns.
    row = Table.grid(expand=True, padding=(0, 1))
    row.add_column(min_width=16, no_wrap=True)
    row.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    row.add_column(width=22, no_wrap=True, overflow="ellipsis")
    row.add_column(width=6, justify="right", no_wrap=True)
    identity = Text(ticket, style=f"bold {brand.PALETTE['foreground']}")
    identity.append(" ")
    identity.append_text(role_label(role))
    title = " ".join(
        "".join(
            " " if unicodedata.category(char).startswith("C") else char
            for char in title
        ).split()
    )
    description = brand.short_dispatch(dispatch_id)
    if title and not narrow:
        # A dispatch ID of another form must leave room for the title in the home column.
        description = f"{brand.shorten(description, 16)} · {title}"
    row.add_row(
        identity,
        Text(description, style=brand.PALETTE["muted"]),
        status_caption(session_status(state), language),
        Text(elapsed, style=brand.PALETTE["muted"]),
    )
    return row
