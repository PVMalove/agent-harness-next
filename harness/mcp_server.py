# Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
# SPDX-License-Identifier: BUSL-1.1
# Licensed under the Business Source License 1.1 (BSL-1.1).
# Commercial use, sale, or use in commercial application development is strictly
# prohibited without prior written permission from the copyright holder.
# Removing or altering this header is prohibited and voids all license rights.


"""Local stdio access to project artifacts, repository context and accepted QA."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

from harness.errors import HarnessError
from harness.json_types import JsonObject

MAX_FRAME = 1 << 20
VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
INVENTORY = "skill_inventory"
ARTIFACTS = "artifact_inventory"
REPO_MAP = "repo_map"
CONTEXT = "context_package"
COMMIT = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
CONTEXT_SECTIONS = ("summary", "diff", "symbol_graph", "file_hashes", "full")
QA = "accepted_qa"
QA_KEYS = ("ticket", "branch", "candidate_commit")
TOOLS = [
    {
        "name": name,
        "description": description,
        "annotations": {"readOnlyHint": True},
        "inputSchema": {
            "type": "object",
            "properties": {key: {"type": "string", "minLength": 1} for key in keys},
            "required": required,
            "additionalProperties": False,
        },
    }
    for name, description, keys, required in (
        (INVENTORY, "Read the installed project skill inventory.", ("name",), []),
        (ARTIFACTS, "Read the installed artifact inventory.", ("kind",), []),
        (
            REPO_MAP,
            "Read the Repo Map at a full commit ID.",
            ("commit", "seed"),
            ["commit"],
        ),
        (
            CONTEXT,
            "Read an immutable batch Context Package.",
            ("batch_id", "package_id", "section"),
            ["batch_id", "package_id"],
        ),
        (
            QA,
            "Read the accepted QA result for an exact candidate commit.",
            QA_KEYS,
            list(QA_KEYS),
        ),
    )
]


def _qa(repo: Path, arguments: JsonObject) -> JsonObject:
    from harness.orchestration.core.constants import STATE_REL
    from harness.orchestration.ledger.ledger_ops import command_state
    from harness.orchestration.workflow.history import (
        _accepted_qa_for_candidate,
        _batch_for_ticket_branch,
    )

    candidate = arguments["candidate_commit"]
    root = (repo / STATE_REL).resolve()
    with command_state(argparse.Namespace(repo=str(repo))):
        batch = _batch_for_ticket_branch(
            root, arguments["ticket"], arguments["branch"], candidate
        )
        report = _accepted_qa_for_candidate(root, batch, candidate)
    return {
        "candidate_commit": candidate,
        "batch_id": batch["batch_id"],
        "outcome": report["outcome"],
    }


def _repo_map(repo: Path, args: JsonObject) -> JsonObject:
    from harness.repo_map.policy import DEFAULT_MAX_TOKENS, load_policy
    from harness.repo_map.repo_map import build_map

    policy = load_policy(repo / ".harness/orchestration.json", explicit=False)
    budget = min(DEFAULT_MAX_TOKENS, policy.max_tokens or DEFAULT_MAX_TOKENS)
    result: JsonObject = json.loads(
        build_map(
            repo,
            args["commit"],
            budget,
            [args["seed"]] if "seed" in args else [],
            policy,
            read_only=True,
        )
    )
    return result


def _context(repo: Path, args: JsonObject) -> JsonObject:
    from harness.orchestration.core.constants import STATE_REL
    from harness.orchestration.ledger.ledger_ops import (
        _load_batch,
        _load_context_package,
        command_state,
    )
    from harness.orchestration.workflow.history import (
        _context_package_summary,
        _validate_batch_integrity,
        _validate_context_package,
    )

    root = (repo / STATE_REL).resolve()
    with command_state(argparse.Namespace(repo=str(repo))):
        batch = _load_batch(root, args["batch_id"])
        _validate_batch_integrity(root, batch)
        package = _load_context_package(root, args["package_id"])
        _validate_context_package(root, batch, package)
    section = args.get("section", "summary")
    if section == "full":
        return package
    data = (
        _context_package_summary(package) if section == "summary" else package[section]
    )
    return {
        "context_package_id": package["context_package_id"],
        "candidate_commit": package["candidate_commit"],
        section: data,
    }


def _error(code: int, message: str) -> JsonObject:
    return {"error": {"code": code, "message": message}}


def _tool_result(value: JsonObject, *, error: bool = False) -> JsonObject:
    return {
        "result": {
            "content": [
                {"type": "text", "text": json.dumps(value, ensure_ascii=False)}
            ],
            "structuredContent": value,
            "isError": error,
        }
    }


def _request(
    method: str, params: JsonObject, repo: Path, inventory: Callable[[Path], JsonObject]
) -> JsonObject:
    if method == "initialize":
        requested = params.get("protocolVersion")
        if not isinstance(requested, str):
            return _error(-32602, "protocolVersion is required")
        return {
            "result": {
                "protocolVersion": requested if requested in VERSIONS else VERSIONS[0],
                "serverInfo": {"name": "agent-harness", "version": "1.0"},
                "capabilities": {"tools": {}},
            }
        }
    if method == "ping":
        return {"result": {}}
    if method == "tools/list":
        return {"result": {"tools": TOOLS}}
    if method != "tools/call":
        return _error(-32601, "Method not found")

    name = params.get("name")
    arguments = params.get("arguments", {})
    if not isinstance(arguments, dict) or not all(
        isinstance(value, str) and value.strip() for value in arguments.values()
    ):
        return _error(-32602, "Expected non-empty string arguments")
    if name == INVENTORY and set(arguments) <= {"name"}:
        all_artifacts = inventory(repo)
        result = {key: all_artifacts[key] for key in ("schema_version", "skills")}
        if "name" in arguments:
            result["skills"] = [
                skill
                for skill in result["skills"]
                if skill["name"] == arguments["name"]
            ]
        return _tool_result(result)
    if name == ARTIFACTS and set(arguments) <= {"kind"}:
        kind = arguments.get("kind")
        if kind not in (None, "skills", "hooks", "templates"):
            return _error(-32602, "kind must be skills, hooks or templates")
        artifact_result = inventory(repo)
        if kind:
            artifact_result = {
                "schema_version": artifact_result["schema_version"],
                kind: artifact_result[kind],
            }
        return _tool_result(artifact_result)
    if (
        name == REPO_MAP
        and "commit" in arguments
        and set(arguments) <= {"commit", "seed"}
    ):
        if not COMMIT.fullmatch(arguments["commit"]):
            return _error(-32602, "commit must be a full lowercase Git object ID")
        return _tool_result(_repo_map(repo, arguments))
    if name == CONTEXT and {"batch_id", "package_id"} <= set(arguments) <= {
        "batch_id",
        "package_id",
        "section",
    }:
        if arguments.get("section", "summary") not in CONTEXT_SECTIONS:
            return _error(-32602, "Unknown Context Package section")
        return _tool_result(_context(repo, arguments))
    if name == QA and arguments.keys() == set(QA_KEYS):
        if not COMMIT.fullmatch(arguments["candidate_commit"]):
            return _error(
                -32602, "candidate_commit must be a full lowercase Git object ID"
            )
        try:
            return _tool_result(_qa(repo, arguments))
        except HarnessError:
            return _tool_result(
                {"error": {"code": "qa_evidence_unavailable", "retryable": True}},
                error=True,
            )
    return _error(-32602, "Unknown tool or invalid arguments")


def _response(
    line: bytes, repo: Path, inventory: Callable[[Path], JsonObject]
) -> tuple[object, JsonObject] | None:
    try:
        request = json.loads(line.decode("utf-8"))
    except (ValueError, RecursionError):
        return None, _error(-32700, "Parse error")
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
        return None, _error(-32600, "Invalid request")
    method = request.get("method")
    request_id = request.get("id")
    if not isinstance(method, str) or type(request_id) not in (str, int, type(None)):
        return None, _error(-32600, "Invalid request")
    if "id" not in request:
        return None
    params = request.get("params", {})
    if not isinstance(params, dict):
        return request_id, _error(-32602, "Expected named parameters")
    try:
        return request_id, _request(method, params, repo, inventory)
    except (HarnessError, OSError, ValueError, SystemExit):
        return request_id, _error(-32603, "Project data unavailable")


def serve(
    repo: Path,
    inventory: Callable[[Path], JsonObject],
    source: BinaryIO,
    sink: BinaryIO,
) -> None:
    while line := source.readline(MAX_FRAME + 1):
        if len(line) > MAX_FRAME:
            while line and not line.endswith(b"\n"):
                line = source.readline(MAX_FRAME + 1)
            result: tuple[object, JsonObject] | None = (
                None,
                _error(-32700, "Request too large"),
            )
        else:
            result = _response(line, repo, inventory)
        if result is None:
            continue
        request_id, response = result
        frame = json.dumps({"jsonrpc": "2.0", "id": request_id, **response}).encode(
            "utf-8"
        )
        if len(frame) > MAX_FRAME:
            frame = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_id if len(str(request_id)) <= 256 else None,
                    **_error(
                        -32000, "Response too large. Filter inventory by skill name."
                    ),
                }
            ).encode("utf-8")
        sink.write(frame + b"\n")
        sink.flush()
