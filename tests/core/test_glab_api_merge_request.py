"""Issue #1266: a merge request opened through ``glab api`` meets the same hooks as ``glab mr create``.

A sandbox can keep ``.git/config`` read-only, and ``glab mr create`` writes it before the API
request, so the delivery instructions open a GitLab MR with a POST to
``projects/<id>/merge_requests``. That form must not escape the attribution check or the QA gate.
"""

from __future__ import annotations

import importlib.util
import shlex
import sys
from pathlib import Path
from types import ModuleType

import pytest

from scripts.clean_room.support import run_hook

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "harness" / "project" / "hooks"
ATTRIBUTION = HOOKS / "block-public-attribution.sh"
ALLOWS, BLOCKS = 0, 2
API_CREATE = (
    "GITLAB_HOST=gitlab.example.invalid glab api projects/7/merge_requests -X POST "
    "-f source_branch=feature/issue-7-demo -f target_branch=main -f title='fix: demo' "
    "-F description=@{path}"
)
MR_CREATE = "glab mr create -R group/demo --target-branch main --description-file {path}"


def _pr_commands() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "pr_commands_api_mr", HOOKS / "pr_commands.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve postponed annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("form", [MR_CREATE, API_CREATE], ids=["mr-create", "api"])
@pytest.mark.parametrize(
    ("body", "expected"),
    [
        pytest.param("## Summary\n\nThe fix keeps the branch.\n", ALLOWS, id="clean"),
        pytest.param(
            "## Summary\n\nGenerated with Claude Code\n", BLOCKS, id="attributed"
        ),
    ],
)
def test_the_api_description_file_meets_the_description_file_check(
    tmp_path: Path, form: str, body: str, expected: int
) -> None:
    path = tmp_path / "pr-body-7-demo.md"
    path.write_text(body, encoding="utf-8")

    result = run_hook(ATTRIBUTION, tmp_path, form.format(path=shlex.quote(str(path))))

    assert result.returncode == expected, result.stderr


@pytest.mark.parametrize(
    ("command", "heads"),
    [
        (API_CREATE.format(path="b.md"), {"feature/issue-7-demo"}),
        ("glab api projects/7/merge_requests -f source_branch=b -F description=@b.md", {"b"}),
        ("glab api --method POST projects/7/merge_requests", {""}),
    ],
)
def test_an_api_post_to_merge_requests_creates_a_merge_request(
    command: str, heads: set[str]
) -> None:
    pr_commands = _pr_commands()

    assert pr_commands.CREATE_TEXT.search(command)
    assert pr_commands.create_heads(command) == heads


@pytest.mark.parametrize(
    "command",
    [
        "glab api projects/7/merge_requests/42/notes -F body=@c.md",
        "glab api 'projects/7/merge_requests?source_branch=b'",
        "glab api projects/7/merge_requests -X GET -f state=opened",
        "glab api projects/7/merge_requests/42 -X PUT -f title=x",
    ],
)
def test_other_merge_request_api_calls_open_nothing(command: str) -> None:
    assert not _pr_commands().CREATE_TEXT.search(command)
