"""The «Обновить Harness» facts of the one project a console server serves: what the harness
installed there, the package version and the `harness diff --json` drift report (none when the
harness is not installed). `UpdateHarnessFacts.to_payload` and `UpdateHarnessFacts.from_payload`
are the wire codec of an `update_harness.snapshot` reply; reading it back is strict, so a reply
off the schema is a `ValueError`. `diff_paths` names the only files `update_harness.diff` reads."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import cast

from .harness_facts import HarnessState
from .home_snapshot import StoreFacts, store_from_payload

# The drift report fields that list files the update touches or the screen shows a diff of.
DIFF_FIELDS = (
    "conflict",
    "package_changed",
    "added",
    "missing",
    "retired",
    "local_changed",
    "seed_differing",
)
_FIELDS = frozenset(
    {"state", "package_version", "drift", "store", "store_target_schema"}
)


@dataclass(frozen=True)
class UpdateHarnessFacts:
    """The installed harness, the available package version and the drift report; `store` is
    the runtime-store authority of the project (`StoreFacts`, None when unread) and
    `store_target_schema` the ledger schema an update migrates the store to."""

    state: HarnessState
    package_version: str
    drift: dict[str, object] | None
    store: StoreFacts | None = None
    store_target_schema: int | None = None

    def to_payload(self) -> dict[str, object]:
        """The JSON object of an `update_harness.snapshot` reply."""
        return {
            "state": self.state.to_payload(),
            "package_version": self.package_version,
            "drift": self.drift,
            "store": asdict(self.store) if self.store is not None else None,
            "store_target_schema": self.store_target_schema,
        }

    @classmethod
    def from_payload(cls, payload: object) -> UpdateHarnessFacts:
        """The facts of an `update_harness.snapshot` reply; anything off the schema is a
        `ValueError`."""
        if not isinstance(payload, dict) or set(payload) != _FIELDS:
            raise ValueError("update harness snapshot off the schema")
        found = cast(dict[str, object], payload)
        version, drift = found["package_version"], found["drift"]
        if not isinstance(version, str):
            raise ValueError("update harness package version")
        if drift is not None and not isinstance(drift, dict):
            raise ValueError("update harness drift")
        target = found["store_target_schema"]
        if target is not None and (isinstance(target, bool) or not isinstance(target, int)):
            raise ValueError("update harness store target schema")
        store = found["store"]
        return cls(
            HarnessState.from_payload(found["state"]),
            version,
            cast("dict[str, object] | None", drift),
            store_from_payload(store) if store is not None else None,
            target,
        )


def diff_paths(drift: dict[str, object] | None) -> frozenset[str]:
    """Every file a drift report lists in `DIFF_FIELDS`; a field that is not a list (a bare
    counter) names no file."""
    if drift is None:
        return frozenset()
    found: set[str] = set()
    for field in DIFF_FIELDS:
        value = drift.get(field)
        if isinstance(value, list):
            found.update(item for item in value if isinstance(item, str))
    return frozenset(found)
