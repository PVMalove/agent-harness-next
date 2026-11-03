"""Fixtures shared by the orchestration tests, and the strict mode of the fault-injection matrix.

With ``HARNESS_REQUIRE_FAULT_INJECTION=1`` (the CI fault-injection job), the selected tests that
carry the ``fault_injection`` marker must be exactly the registry of ``fault_injection_matrix``, and
a skip of a marked test is a failure. Without the variable both hooks change nothing.
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest

from . import fault_injection_matrix
from .release_1x import release_1x as release_1x

__all__ = ["release_1x"]


def _required() -> bool:
    return os.environ.get(fault_injection_matrix.REQUIRE_ENV) == "1"


def pytest_collection_finish(session: pytest.Session) -> None:
    """In the strict mode, end the session before any test runs when the selected marked tests
    differ from the registry."""
    if not _required():
        return
    marked = [
        item.nodeid
        for item in session.items
        if item.get_closest_marker(fault_injection_matrix.MARKER) is not None
    ]
    problems = fault_injection_matrix.registry_problems(
        marked, fault_injection_matrix.SCENARIOS
    )
    if problems:
        pytest.exit(
            f"{fault_injection_matrix.REQUIRE_ENV}=1: the selected tests do not match the "
            "fault-injection registry: " + "; ".join(problems),
            returncode=pytest.ExitCode.TESTS_FAILED,
        )


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """In the strict mode, a skipped marked test fails with the reason of its skip."""
    report = yield
    if (
        report.skipped
        and _required()
        and item.get_closest_marker(fault_injection_matrix.MARKER) is not None
    ):
        longrepr = report.longrepr
        reason = longrepr[2] if isinstance(longrepr, tuple) else str(longrepr)
        report.outcome = "failed"
        report.longrepr = (
            f"{fault_injection_matrix.REQUIRE_ENV}=1: a scenario of the fault-injection "
            f"matrix may not skip: {reason}"
        )
    return report
