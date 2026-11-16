"""The `features.snapshot` reply: one typed reply of the feature registry that validates against
the reply models, is cached like the other screens and stays below the message limit."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

from harness.console.backend import composition
from harness.console.backend.api.protocol.screens import respond
from harness.console.backend.api.schemas import REPLIES, FeaturesSnapshotReply
from harness.console.kernel.features import collect_features
from harness.console.kernel.protocol import MESSAGE_LIMIT


def _ask(service: object, request: dict[str, object]) -> dict[str, object]:
    raw = asyncio.run(respond(json.dumps({"id": 7, **request}), service))  # type: ignore[arg-type]
    assert len(raw.encode("utf-8")) < MESSAGE_LIMIT
    reply = json.loads(raw)
    assert isinstance(reply, dict)
    return reply


def test_the_reply_of_the_real_registry_validates_and_fits_one_frame(tmp_path: Path) -> None:
    (tmp_path / ".harness").mkdir()
    (tmp_path / ".harness/project.json").write_text('{"memory": {"enabled": true}}')
    service = composition.screen_service(tmp_path, features=collect_features)

    reply = _ask(service, {"type": "features.snapshot"})

    model = REPLIES.validate_python(reply)
    assert isinstance(model, FeaturesSnapshotReply)
    assert len(model.features) == 26
    assert reply["cached"] is False and "snapshot_id" not in reply
    assert set(cast(dict[str, str], reply["config_digests"])) == {
        "project.json",
        "orchestration.json",
    }


def test_the_reply_is_cached_until_forced(tmp_path: Path) -> None:
    calls: list[Path] = []

    def collect(repo: Path) -> dict[str, object]:
        calls.append(repo)
        return collect_features(repo)

    service = composition.screen_service(tmp_path, features=collect)

    async def scenario() -> list[dict[str, object]]:
        replies = []
        for request in (
            {"type": "features.snapshot"},
            {"type": "features.snapshot"},
            {"type": "features.snapshot", "force": True},
        ):
            replies.append(json.loads(await respond(json.dumps({"id": 1, **request}), service)))
        return replies

    first, second, forced = asyncio.run(scenario())

    assert (first["cached"], second["cached"], forced["cached"]) == (False, True, False)
    assert len(calls) == 2


def test_an_unknown_or_malformed_field_is_a_bad_request(tmp_path: Path) -> None:
    service = composition.screen_service(tmp_path, features=collect_features)

    requests: list[dict[str, object]] = [
        {"type": "features.snapshot", "online": True},
        {"type": "features.snapshot", "force": "yes"},
    ]
    for request in requests:
        reply = _ask(service, request)
        assert reply["ok"] is False
        assert cast(dict[str, object], reply["error"])["code"] == "bad_request"
