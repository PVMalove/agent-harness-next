"""The AI advisor port over the shared kernel advisor: the user's own Codex or Claude Code CLI
login, the saved configuration read on the server, and only the allowlisted facts of one
parameter sent to the CLI. Nothing is written."""

from __future__ import annotations

import dataclasses
import threading
from collections.abc import Mapping
from pathlib import Path

from ...kernel.configuration import ConfigurationDraft
from ...kernel.configuration_advisor import (
    FALLBACK,
    AdviceRejected,
    AdvisorUnavailable,
    advise,
    check_cli,
)
from ...kernel.configuration_steps import steps_for
from ..application.ports import AdviceNotFound

UNREADABLE = "CLI недоступен или его ответ несовместим." + FALLBACK


def _fallback(cause: str, reason: str) -> dict[str, object]:
    return {"outcome": "fallback", "cause": cause, "reason": reason}


class CliAdvisor:
    """`AdvisorPort` of one project. The browser draft is never sent: compatibility is checked
    against the saved files, and the confirmed configuration write validates the draft again."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo

    def check(self, provider: str, cancel: threading.Event) -> Mapping[str, object]:
        return dataclasses.asdict(check_cli(provider, cancel))

    def ask(
        self,
        provider: str,
        file: str,
        path: tuple[str, ...],
        cancel: threading.Event,
    ) -> Mapping[str, object]:
        try:
            draft = ConfigurationDraft.load(self.repo, (file,))
        except (OSError, ValueError):
            return _fallback("refused", UNREADABLE)
        step = next(
            (s for s in steps_for(draft) if s.file == file and s.path == path), None
        )
        if step is None:
            raise AdviceNotFound(path)
        try:
            advice = advise(provider, draft, step, cancel)
        except AdviceRejected as exc:
            return _fallback("invalid", str(exc))
        except AdvisorUnavailable as exc:
            return _fallback("refused", str(exc))
        except (OSError, ValueError):
            return _fallback("refused", UNREADABLE)
        return {
            "outcome": "advice",
            "advice": {
                "value": advice.value,
                "why": advice.why,
                "impact": advice.impact,
                "comparison": [
                    {"option": option, "tradeoff": tradeoff}
                    for option, tradeoff in advice.comparison
                ],
            },
        }
