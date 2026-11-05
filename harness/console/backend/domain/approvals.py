"""When a console decision needs an explicit human confirmation, and which native permission
answers are well formed."""

from __future__ import annotations

import re
from collections.abc import Mapping

CANCEL_KEEPS_CHANGES = (
    "Cancelling stops the command; the changes it has already made are not rolled back."
)
NATIVE_ANSWER_FIELDS = ("dispatch", "request_id", "request_sha256")
_DISPATCH = re.compile(r"dispatch-[0-9a-f-]+")
_SHA256 = re.compile(r"[0-9a-f]{64}")
# The runtime stages request ids of up to 256 characters (`runtime_permissions.stage_request`).
_MAX_ID_CHARS = 256


def start_confirmed(
    *,
    needs_confirmation: bool,
    typed_confirmation: str | None,
    confirmed: bool,
    confirmation: object,
) -> bool:
    """A start carries every confirmation its command asks for: the flag, and the typed text when
    the command has one."""
    return not (
        (needs_confirmation and not confirmed)
        or (typed_confirmation is not None and confirmation != typed_confirmation)
    )


def cancel_confirmation_message(*, holds_mutation_slot: bool) -> str | None:
    """What an unconfirmed cancel says: a mutation is warned that its changes stay."""
    return CANCEL_KEEPS_CHANGES if holds_mutation_slot else None


def native_answer_accepts(values: Mapping[str, str]) -> bool:
    """Exactly the dispatch, the request id and its digest, each non-empty and bounded."""
    if set(values) != set(NATIVE_ANSWER_FIELDS):
        return False
    if any(
        not value.strip() or len(value) > _MAX_ID_CHARS for value in values.values()
    ):
        return False
    return bool(
        _DISPATCH.fullmatch(values["dispatch"])
        and _SHA256.fullmatch(values["request_sha256"])
    )
