"""The `repo_map.snapshot` codec and which map the Repo Map screen shows; no processes."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from harness.console.kernel.repo_map import RepoMapView, parse_map
from harness.console.kernel.repo_map_settings import MemoryStatus
from harness.console.kernel.repo_map_snapshot import RepoMapFacts, shown_view

from ._console_repo_map_fixture import map_payload
from ._screen_facts import HEAD, repo_map_facts


def _wire(facts: RepoMapFacts) -> dict[str, object]:
    payload = json.loads(json.dumps(facts.to_payload()))
    assert isinstance(payload, dict)
    return payload


def test_the_facts_survive_the_json_round_trip_with_and_without_optional_values() -> (
    None
):
    full = repo_map_facts()
    empty = replace(
        full,
        head=None,
        view=None,
        excluded=None,
        parsers=None,
        memory=MemoryStatus(False, False, (), None, "нет Git"),
        language_files={},
    )
    stale = replace(empty, head="c" * 40, stale=full.view)
    for facts in (full, empty, stale):
        assert RepoMapFacts.from_payload(_wire(facts)) == facts
    assert _wire(stale)["map"] is None
    assert _wire(stale)["stale_map"] == full.view.payload  # type: ignore[union-attr]
    assert _wire(full)["stale_map"] is None


def _set(payload: dict[str, object], path: tuple[str, ...], value: object) -> None:
    target = payload
    for key in path[:-1]:
        inner = target[key]
        assert isinstance(inner, dict)
        target = inner
    target[path[-1]] = value


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("extra",), 1),
        (("head",), 7),
        (("map",), {"schema_version": 1}),
        (("tier", "editable"), "yes"),
        (("tier", "extra"), ""),
        (("memory", "indexed"), True),
        (("memory", "source_types"), "adr"),
        (("parsers", "grammars"), [1]),
        (("parsers", "pair"), 3),
        (("language_files", "python"), "3"),
        (("language_files", "python"), False),
    ],
    ids=lambda item: ".".join(item) if isinstance(item, tuple) else None,
)
def test_a_payload_off_the_schema_is_refused(
    path: tuple[str, ...], value: object
) -> None:
    payload = _wire(repo_map_facts())
    _set(payload, path, value)
    with pytest.raises(ValueError):
        RepoMapFacts.from_payload(payload)


def test_a_payload_without_a_field_is_refused() -> None:
    for field in ("head", "map", "tier", "memory", "parsers", "language_files"):
        payload = _wire(repo_map_facts())
        del payload[field]
        with pytest.raises(ValueError):
            RepoMapFacts.from_payload(payload)


def _built(commit: str) -> RepoMapView:
    view = parse_map(map_payload(commit), origin="построена")
    assert not isinstance(view, str)
    return view


def test_the_server_map_is_shown_unless_a_map_built_here_is_newer_for_the_same_head() -> (
    None
):
    facts = repo_map_facts()
    cached = facts.view
    built = _built(HEAD)
    uncached = replace(facts, view=None)
    # The server cache answers for HEAD: its map is shown.
    assert shown_view(facts, None) is cached
    assert shown_view(facts, built) is cached
    # A degraded build is not cached: the map built here stays for the same HEAD only.
    assert shown_view(uncached, built) is built
    assert shown_view(uncached, _built("b" * 40)) is None
    assert shown_view(replace(uncached, head=None), built) is None
