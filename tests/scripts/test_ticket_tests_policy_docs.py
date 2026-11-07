#!/usr/bin/env python3
"""The ticket-tests policy docs name what the code names (issue #938).

ADR 0023 and ADR 0026 carry a dated amendment for the policy; ADR 0026 records decisions D2 and D4
of #812. The ADRs, the playbook and the ``to-pull-requests`` skill with its Russian description use
the flag, the ``selection`` value, the CI job and the ``collect-ci`` reason that the code of #935,
#936 and #937 defines. The names are read from the code and the workflow, and only names are pinned, not
wording; one test pins the four values the lookup is expected to find.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from harness.orchestration import contract
from harness.orchestration.core import ci_source
from harness.orchestration.core.constants import VERIFICATION_PLAN_SELECTIONS

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "verify.yml"
ADR_0023 = "docs/adr/0023-incremental-verification.md"
ADR_0026 = "docs/adr/0026-harness-next-consolidation.md"
PLAYBOOK = "harness/orchestration/playbook.md"
SKILL = "skills/first-party/engineering/to-pull-requests/SKILL.md"
SKILL_RU = "docs/skills/to-pull-requests.md"
AMENDMENT_DATE = "2026-11-07"
AMENDMENT = re.compile(rf"^#{{2,4}} .*Поправка.*{AMENDMENT_DATE}", re.MULTILINE)
ADRS = (ADR_0023, ADR_0026)
GUIDES = (PLAYBOOK, SKILL, SKILL_RU)


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _code_names() -> dict[str, str]:
    """The names of the policy as the code and the workflow define them."""
    flag = next(
        field for field in contract.VERIFICATION_PLAN_POLICY_FIELDS if field.endswith("_selection")
    )
    selection = next(value for value in VERIFICATION_PLAN_SELECTIONS if value.startswith("ticket"))
    light_jobs = re.findall(
        rf"^  ([a-z-]+{re.escape(ci_source.LIGHT_CHECK_SUFFIX)}):\s*$",
        WORKFLOW.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    reason = next(item for item in ci_source.REASONS if item.startswith("light_"))
    return {"flag": flag, "selection": selection, "job": light_jobs[0], "reason": reason}


class TicketTestsPolicyDocsTest(unittest.TestCase):
    def test_the_names_are_read_from_the_code(self) -> None:
        self.assertEqual(
            _code_names(),
            {
                "flag": "ticket_diff_selection",
                "selection": "ticket-diff",
                "job": "verify-light",
                "reason": "light_check",
            },
        )

    def test_each_adr_carries_the_dated_amendment_with_the_policy_names(self) -> None:
        names = _code_names()
        for path in ADRS:
            text = _text(path)
            with self.subTest(path=path):
                self.assertRegex(text, AMENDMENT)
                for key in ("flag", "selection", "job"):
                    self.assertIn(names[key], text, f"{path} lacks the {key} name")

    def test_adr_0026_records_the_decisions_d2_and_d4_of_812(self) -> None:
        text = _text(ADR_0026)
        self.assertRegex(text, r"\bD2\b")
        self.assertRegex(text, r"\bD4\b")
        self.assertIn("#812", text)

    def test_the_agent_guides_name_the_flag_selection_job_and_reason(self) -> None:
        names = _code_names()
        for path in GUIDES:
            text = _text(path)
            with self.subTest(path=path):
                for key, name in names.items():
                    self.assertIn(name, text, f"{path} lacks the {key} name {name!r}")


if __name__ == "__main__":
    unittest.main()
