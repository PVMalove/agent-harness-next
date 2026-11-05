"""Wire constants of the console protocol that the server and the TUI client share: the protocol
version, the Home request types, the request and message limits and the JSON-string clipping that
keeps a reply below them. Standard library only."""

from __future__ import annotations

import re

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 4096
MAX_ID_CHARS = 64
HOME_REQUEST = "home.snapshot"
HOME_PROBLEMS_REQUEST = "home.problems"

MESSAGE_BYTES = 300
ID_BYTES = 100
MESSAGE_LIMIT = 65536

_SHORT_ESCAPES = frozenset('"\\\b\f\n\r\t')

# json.loads accepts "\ud800"; the str cannot be encoded as UTF-8, so a reply carries it escaped.
_LONE_SURROGATE = re.compile("[\ud800-\udfff]")


def _wire_cost(char: str) -> int:
    """Bytes `char` takes inside a JSON string: a quote, a backslash or a short escape is two,
    any other control character and a lone surrogate (sent as `\\udXXX`) is six, everything
    else is its UTF-8 length."""
    if char in _SHORT_ESCAPES:
        return 2
    if char < " " or _LONE_SURROGATE.match(char):
        return 6
    return len(char.encode("utf-8"))


def _clip(text: str, limit: int) -> str:
    """The longest prefix of `text` that takes at most `limit` bytes as a JSON string."""
    used = 0
    for index, char in enumerate(text[:limit]):
        used += _wire_cost(char)
        if used > limit:
            return text[:index]
    return text[:limit]
