"""Narrowing of decoded JSON values to the shapes the console snapshots read.

A strict reader returns the value when it has the asked shape and otherwise raises the error with
the caller's message, so every snapshot keeps its own wording; a message may be a function of the
rejected value. The lenient readers, which substitute an empty value, are in `json_fields`.
Standard library only."""

from __future__ import annotations

from collections.abc import Callable

Message = str | Callable[[object], str]


def _text(message: Message, value: object) -> str:
    return message if isinstance(message, str) else message(value)


def json_object(
    value: object,
    message: Message,
    fields: frozenset[str] | None = None,
    *,
    error: Callable[[str], Exception] = ValueError,
) -> dict[str, object]:
    """The JSON object with string keys; with `fields`, also exactly those keys."""
    if (
        not isinstance(value, dict)
        or not all(isinstance(key, str) for key in value)
        or (fields is not None and set(value) != fields)
    ):
        raise error(_text(message, value))
    return value


def json_list(value: object, message: Message) -> list[object]:
    """The JSON list."""
    if not isinstance(value, list):
        raise ValueError(_text(message, value))
    return value


def json_str(value: object, message: Message) -> str:
    """The string."""
    if not isinstance(value, str):
        raise ValueError(_text(message, value))
    return value


def json_int(value: object, message: Message) -> int:
    """An integer that is not a boolean."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(_text(message, value))
    return value


def json_bool(value: object, message: Message) -> bool:
    """The boolean."""
    if not isinstance(value, bool):
        raise ValueError(_text(message, value))
    return value
