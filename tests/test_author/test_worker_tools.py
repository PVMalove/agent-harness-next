"""The optional author grants no tools to other workers or explicit project policies."""

import pytest

from harness.orchestration.contract import resolve_allowed_tools


def test_opted_in_developer_can_call_only_the_named_author() -> None:
    assert resolve_allowed_tools({}, "developer", "write", test_author=True) == [
        "Read",
        "Grep",
        "Glob",
        "Bash",
        "Edit",
        "Write",
        "Agent(test-author)",
    ]


@pytest.mark.parametrize(
    "role,mode", [("architect", "read-only"), ("migrator", "write")]
)
def test_author_opt_in_does_not_grant_delegation_to_other_roles(
    role: str, mode: str
) -> None:
    assert not any(
        tool.startswith("Agent")
        for tool in resolve_allowed_tools({}, role, mode, test_author=True)
    )


def test_explicit_project_policy_keeps_its_exact_tool_ceiling() -> None:
    config = {"tool_policy": {"modes": {"write": ["Read", "Write"]}}}

    assert resolve_allowed_tools(config, "developer", "write", test_author=True) == [
        "Read",
        "Write",
    ]
