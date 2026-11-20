"""The step feed the Playwright spec mocks (tests/web/fixtures/live-steps.json) is a feed the
server can send: every reply validates against the reply models, and no step carries a field
outside the allowlist."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from harness.console.backend.api.schemas import REPLIES

FIXTURE = Path(__file__).resolve().parents[1] / "web" / "fixtures" / "live-steps.json"


def test_the_mocked_feed_validates_against_the_reply_schema() -> None:
    feed = cast(dict[str, dict[str, object]], json.loads(FIXTURE.read_text("utf-8")))
    envelope = {"v": 1, "id": "1-1", "type": "steps.subscribe", "ok": True}

    assert set(feed) == {"roster", "steps", "later"}
    for body in feed.values():
        REPLIES.validate_python({**envelope, **body})
    steps = [
        step
        for name in ("steps", "later")
        for step in cast(list[dict[str, object]], feed[name]["steps"])
    ]
    assert {step["origin"] for step in steps} == {"agent", "orchestration"}
    assert any(
        step.get("structure") == "unavailable" and step.get("source") == "plain"
        for step in steps
    )
    rendered = json.dumps(feed, ensure_ascii=False)
    for forbidden in ("thinking", '"input"', "tool_use"):
        assert forbidden not in rendered
