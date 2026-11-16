"""The fixture the Diagnostics features tab replays is a `features.snapshot` reply the server
sends: it validates against the reply models and shows every state and category."""

from __future__ import annotations

import json
from pathlib import Path

from harness.console.backend.api.schemas import REPLIES, FeaturesSnapshotReply
from harness.console.kernel.features import CATEGORIES, STATES

FIXTURES = Path(__file__).resolve().parents[1] / "web" / "fixtures"


def test_the_features_fixture_is_a_features_snapshot_reply() -> None:
    payload = json.loads((FIXTURES / "features-snapshot.json").read_text(encoding="utf-8"))
    reply = {"v": 1, "id": 1, "type": "features.snapshot", "ok": True, **payload}

    model = REPLIES.validate_python(reply)

    assert isinstance(model, FeaturesSnapshotReply)
    assert len(model.features) == 26
    assert {item.category for item in model.features} == set(CATEGORIES)
    assert {item.state for item in model.features} == set(STATES)
    assert sum(item.toggle is not None for item in model.features) == 3
