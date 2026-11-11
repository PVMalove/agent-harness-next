"""The Repo Map screen's facts as one value: HEAD, the map cached for it, the tier the policy asks
for, the parser bundle, the project languages and the memory status, with what the kernel derives
from the map (`repo_map_coverage`): the kind of each signature and the coverage by file class. `RepoMapFacts.to_payload` and
`RepoMapFacts.from_payload` are the wire codec of a `repo_map.snapshot` reply; reading the payload
back is strict, so a reply off the schema is a `ValueError`, never a half-filled screen."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from harness.repo_map.bundle_fetch import ParserStatus

from .repo_map import RepoMapView, parse_map
from .repo_map_coverage import coverage, symbol_kinds
from .repo_map_settings import MemoryStatus, TierSetting

T = TypeVar("T")

_FIELDS = frozenset(
    {
        "head",
        "map",
        "stale_map",
        "tier",
        "memory",
        "parsers",
        "language_files",
        "symbol_kinds",
        "coverage",
    }
)
_COVERAGE_FIELDS = frozenset({"source", "docs", "tests", "excluded"})
_TIER_FIELDS = frozenset({"tier", "editable", "reason"})
_MEMORY_FIELDS = frozenset(
    {
        "enabled",
        "active",
        "source_types",
        "indexed",
        "problem",
        "inactive",
        "top_k",
        "max_tokens",
    }
)
_PARSER_FIELDS = frozenset({"registry", "pair", "source", "grammars", "problem"})


@dataclass(frozen=True)
class RepoMapFacts:
    """What the Repo Map screen shows; `head` is None outside a Git repository with commits,
    `view` without a cached map for HEAD and `parsers` when the bundle cannot be read.
    `excluded` counts the files tracked at the map's commit that the map leaves out; None when
    there is no map or Git cannot tell."""

    head: str | None
    view: RepoMapView | None
    tier: TierSetting
    memory: MemoryStatus
    parsers: ParserStatus | None
    language_files: dict[str, int]
    excluded: int | None = None
    # The latest cached map of another commit when HEAD has none: shown "stale for HEAD".
    stale: RepoMapView | None = None

    def to_payload(self) -> dict[str, object]:
        """The JSON object of a `repo_map.snapshot` reply."""
        memory, parsers = self.memory, self.parsers
        return {
            "head": self.head,
            "map": None if self.view is None else self.view.payload,
            "stale_map": None if self.stale is None else self.stale.payload,
            "tier": {
                "tier": self.tier.tier,
                "editable": self.tier.editable,
                "reason": self.tier.reason,
            },
            "memory": {
                "enabled": memory.enabled,
                "active": memory.active,
                "source_types": list(memory.source_types),
                "indexed": memory.indexed,
                "problem": memory.problem,
                "inactive": memory.inactive,
                "top_k": memory.top_k,
                "max_tokens": memory.max_tokens,
            },
            "parsers": None
            if parsers is None
            else {
                "registry": str(parsers.registry),
                "pair": parsers.pair,
                "source": parsers.source,
                "grammars": list(parsers.grammars),
                "problem": parsers.problem,
            },
            "language_files": dict(self.language_files),
            "symbol_kinds": None if self.view is None else symbol_kinds(self.view),
            "coverage": None
            if self.view is None
            else coverage(self.view, self.excluded).to_payload(),
        }

    @classmethod
    def from_payload(cls, payload: object) -> RepoMapFacts:
        """The facts a `to_payload` result (read back from JSON) describes; a map that fails the
        schema v1 check is refused like any other field off the schema."""
        found = _object(payload, _FIELDS)
        view: RepoMapView | None = None
        if found["map"] is not None:
            parsed = parse_map(found["map"], origin="кэш")
            if isinstance(parsed, str):
                raise ValueError(parsed)
            view = parsed
        stale: RepoMapView | None = None
        if found["stale_map"] is not None:
            parsed_stale = parse_map(found["stale_map"], origin="кэш")
            if isinstance(parsed_stale, str):
                raise ValueError(parsed_stale)
            stale = parsed_stale
        files = _object(found["language_files"], None)
        excluded = _derived(view, found["symbol_kinds"], found["coverage"])
        return cls(
            head=_optional(found["head"], _str),
            view=view,
            tier=_tier(found["tier"]),
            memory=_memory(found["memory"]),
            parsers=_optional(found["parsers"], _parsers),
            language_files={key: _int(count) for key, count in files.items()},
            excluded=excluded,
            stale=stale,
        )


def _derived(view: RepoMapView | None, kinds: object, found: object) -> int | None:
    """The `excluded` count of the payload; the kinds and the class counts must be the ones the
    kernel derives from the map, and both are null without a map."""
    if view is None:
        if kinds is not None or found is not None:
            raise ValueError("symbol kinds and coverage need a map")
        return None
    fields = _object(found, _COVERAGE_FIELDS)
    excluded = _optional(fields["excluded"], _int)
    if kinds != symbol_kinds(view) or found != coverage(view, excluded).to_payload():
        raise ValueError("symbol kinds or coverage do not match the map")
    return excluded


def _object(value: object, fields: frozenset[str] | None) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("expected a JSON object")
    if fields is not None and set(value) != fields:
        raise ValueError(f"expected the fields {sorted(fields)}")
    return value


def _optional(value: object, read: Callable[[object], T]) -> T | None:
    return None if value is None else read(value)


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expected an integer")
    return value


def _str(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("expected a string")
    return value


def _bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("expected a boolean")
    return value


def _strs(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("expected a list of strings")
    return tuple(_str(item) for item in value)


def _tier(value: object) -> TierSetting:
    found = _object(value, _TIER_FIELDS)
    return TierSetting(
        _str(found["tier"]), _bool(found["editable"]), _str(found["reason"])
    )


def _memory(value: object) -> MemoryStatus:
    found = _object(value, _MEMORY_FIELDS)
    return MemoryStatus(
        enabled=_bool(found["enabled"]),
        active=_bool(found["active"]),
        source_types=_strs(found["source_types"]),
        indexed=_optional(found["indexed"], _int),
        problem=_str(found["problem"]),
        inactive=_str(found["inactive"]),
        top_k=_optional(found["top_k"], _int),
        max_tokens=_optional(found["max_tokens"], _int),
    )


def _parsers(value: object) -> ParserStatus:
    found = _object(value, _PARSER_FIELDS)
    return ParserStatus(
        registry=Path(_str(found["registry"])),
        pair=_optional(found["pair"], _str),
        source=_optional(found["source"], _str),
        grammars=_strs(found["grammars"]),
        problem=_optional(found["problem"], _str),
    )


def shown_view(facts: RepoMapFacts, built: RepoMapView | None) -> RepoMapView | None:
    """The map the Repo Map screen shows after a snapshot: the server's map for HEAD, else the
    map `built` on the screen for that same HEAD (a degraded build is not cached), else none."""
    if facts.view is not None:
        return facts.view
    if built is not None and facts.head is not None and built.commit == facts.head:
        return built
    return None
