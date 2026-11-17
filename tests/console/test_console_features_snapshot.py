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


def test_a_finished_configuration_job_drops_the_cached_digests_of_both_screens(
    tmp_path: Path,
) -> None:
    from harness.console.backend.application.jobs import JobService
    from harness.console.kernel.catalog import CONFIGURATION_COMMANDS, HARNESS_COMMANDS

    calls = {"features": 0, "configuration": 0}

    def features(repo: Path) -> dict[str, object]:
        calls["features"] += 1
        return {"features": [], "config_digests": {"project.json": str(calls["features"])}}

    def configuration(repo: Path) -> dict[str, object]:
        calls["configuration"] += 1
        return {"files": {}, "pending": None}

    async def executor(
        argv: object, *, cwd: Path, on_output: object, cancel_event: object
    ) -> int:
        return 0

    jobs = JobService(
        tmp_path,
        catalog={entry.key: entry for entry in (*CONFIGURATION_COMMANDS, *HARNESS_COMMANDS)},
        executor=executor,
        journal=lambda repo, record: None,
        new_id=iter(f"job-{index}" for index in range(10)).__next__,
        now=lambda: "t",
    )
    screens = composition.screen_service(
        tmp_path, features=features, configuration=configuration
    )
    composition.compose(tmp_path, jobs=jobs, screens=screens)

    async def run(command_id: str) -> None:
        job = jobs.start({"command_id": command_id, "client": "browser", "confirmed": True})
        while job.phase == "running":
            await asyncio.sleep(0.01)
        assert job.phase == "completed"

    async def scenario() -> None:
        await screens.features()
        await screens.configuration()
        await screens.features()
        await screens.configuration()
        assert calls == {"features": 1, "configuration": 1}
        # A job of another section leaves the digests cached.
        await run("diff")
        await screens.features()
        await screens.configuration()
        assert calls == {"features": 1, "configuration": 1}
        # A configuration write makes both sources stale at once.
        await run("configuration-recover")
        served = await screens.features()
        await screens.configuration()
        assert served["cached"] is False
        assert calls == {"features": 2, "configuration": 2}

    asyncio.run(scenario())
