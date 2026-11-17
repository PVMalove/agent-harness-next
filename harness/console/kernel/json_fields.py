"""Lenient readers of the JSON data the console only shows (ledger records, completion reports,
the repository map): a field of the wrong type reads as an empty value instead of failing the
screen. The strict readers, which raise an error, are in `json_shape`."""

from __future__ import annotations


def text(value: object, default: str = "") -> str:
    """The value when it is a string, otherwise the default."""
    return value if isinstance(value, str) else default


def strings(value: object) -> list[str]:
    """The string items of a JSON list; items of other types are dropped."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def mapping_or_empty(value: object) -> dict[str, object]:
    """The JSON object when the value is one, otherwise an empty object."""
    return value if isinstance(value, dict) else {}


def items_or_empty(value: object) -> list[object]:
    """The JSON list when the value is one, otherwise an empty list."""
    return value if isinstance(value, list) else []
