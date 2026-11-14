"""Whether the runtime of a repository keeps the recovery records: its hello and what it lacks."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from pathlib import Path

from harness.orchestration.core.utils import JsonObject

# The features of the runtime hello that recovery reads and writes through, and the protocol
# that added the recovery records (minor 5).
RECOVERY_FEATURES = ("state.read", "state.write", "state.recovery")
RECOVERY_PROTOCOL = (1, 5)


def runtime_hello(repo: Path) -> JsonObject:
    """What the runtime of ``repo`` answers in ``hello``: its protocol, store and features."""
    from harness.orchestration.runtime_client import RuntimeClient

    reply = RuntimeClient(repo).call(
        "status", operation_id=f"recovery.status-{uuid.uuid4().hex}", timeout_seconds=30.0
    )
    features = reply.hello.get("features")
    return {
        "protocol": reply.hello.get("protocol"),
        "server_version": reply.hello.get("server_version"),
        "store_id": reply.hello.get("store_id"),
        "features": list(features) if isinstance(features, list) else [],
    }


def runtime_problems(hello: Mapping[str, object]) -> list[str]:
    """Why the runtime of ``hello`` cannot keep the recovery records; empty when it can."""
    problems = []
    protocol = hello.get("protocol")
    major, minor = RECOVERY_PROTOCOL
    if not (
        isinstance(protocol, dict)
        and protocol.get("major") == major
        and isinstance(protocol.get("minor"), int)
        and protocol["minor"] >= minor
    ):
        problems.append(
            f"the runtime speaks protocol {protocol!r}, recovery needs {major}.{minor} or a "
            "later minor"
        )
    if not hello.get("store_id"):
        problems.append("the runtime serves no store")
    features = hello.get("features")
    missing = [
        name
        for name in RECOVERY_FEATURES
        if not isinstance(features, list) or name not in features
    ]
    if missing:
        problems.append(f"the runtime lacks the features {', '.join(missing)}")
    return problems
