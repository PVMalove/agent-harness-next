"""Repo Map over real FastAPI/WebSocket and the production CLI process in a disposable Git repo."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

from websockets.asyncio.client import connect
from websockets.typing import Origin

from harness.console.backend.server import ConsoleServer
from harness.console.kernel import web_catalog
from harness.console.kernel.repo_map import BUILD_WARNING
from harness.console.kernel.repo_map_snapshot import RepoMapFacts
from harness.repo_map.contract import validation_error


def test_browser_reads_tui_facts_and_builds_a_pinned_map_across_disconnect(
    tmp_path: Path,
) -> None:
    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(tmp_path), *args], text=True
        ).strip()

    git("init", "-q")
    (tmp_path / "example.py").write_text(
        "def example():\n    return 1\n", encoding="utf-8"
    )
    config = tmp_path / ".harness"
    config.mkdir()
    (config / "orchestration" / "roles").mkdir(parents=True)
    (config / "orchestration.json").write_text(
        json.dumps({"repo_map_policy": {"tier": "minimal"}}), encoding="utf-8"
    )
    git("add", "example.py", ".harness/orchestration.json")
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )
    head = git("rev-parse", "HEAD")

    async def scenario() -> None:
        server = ConsoleServer(
            tmp_path, idle_grace_seconds=60, static_root=tmp_path / "no-build"
        )
        await server.start()
        url = f"ws://127.0.0.1:{server.port}/ws"
        # The browser session uses the same cookie the launch URL sets.
        headers = {"Cookie": f"console_token_{server.port}={server.token}"}
        origin = Origin(f"http://127.0.0.1:{server.port}")
        try:
            async with connect(
                url, additional_headers=headers, origin=origin
            ) as socket:
                await socket.send(
                    json.dumps({"id": "facts", "type": "repo_map.snapshot"})
                )
                reply = json.loads(await socket.recv())
                assert reply["ok"] is True and reply["done"] is True
                facts = RepoMapFacts.from_payload(json.loads(reply["text"]))
                assert facts.head == head and facts.view is None
                assert facts.tier.tier == "minimal"
                await socket.send(
                    json.dumps(
                        {
                            "id": "build",
                            "type": "job.start",
                            "client": "browser",
                            "command_id": "repo-map-build",
                            "values": {"commit": head},
                        }
                    )
                )
                started = json.loads(await socket.recv())
                assert started["ok"] is True
                job_id = started["job"]["id"]
            async with connect(
                url, additional_headers=headers, origin=origin
            ) as socket:
                await socket.send(
                    json.dumps(
                        {
                            "id": "resume",
                            "type": "job.subscribe",
                            "job_id": job_id,
                            "cursor": 0,
                        }
                    )
                )
                output: list[str] = []
                while True:
                    reply = json.loads(await socket.recv())
                    assert reply["ok"] is True
                    job = reply["job"]
                    output.extend(
                        part["text"]
                        for part in job["output"]
                        if part["channel"] == "stdout"
                    )
                    if job["done"]:
                        assert job["phase"] == "completed" and job["returncode"] == 0
                        break
                payload = json.loads("".join(output))
                assert validation_error(payload) is None
                assert payload["commit"] == head and payload["tier"] == "minimal"
                assert {row["path"] for row in payload["files"]} == {
                    "example.py",
                    ".harness/orchestration.json",
                }
        finally:
            await server.close()

    asyncio.run(asyncio.wait_for(scenario(), timeout=30))
    catalog = json.loads(web_catalog.render())["en"]
    assert catalog["Перестроить"] == "Rebuild"
    assert catalog["Сигнатуры"] == "Signatures"
    assert catalog["Документов в индексе"] == "Indexed documents"
    assert "offline parser bundle" in catalog[BUILD_WARNING]


def test_browser_fixture_is_the_existing_tui_snapshot() -> None:
    from tests.console._screen_facts import repo_map_facts

    path = Path(__file__).parent / "fixtures" / "repo-map.json"
    assert json.loads(path.read_text(encoding="utf-8")) == repo_map_facts().to_payload()
