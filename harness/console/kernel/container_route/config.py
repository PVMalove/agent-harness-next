"""The authored `.harness/orchestration.json` the Setup stage shows, read-only."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .model import JsonObject


@dataclass(frozen=True)
class Authored:
    """The authored `.harness/orchestration.json`, read-only; a problem is shown, never hidden."""

    document: JsonObject | None
    problem: str = ""

    def to_payload(self) -> dict[str, object]:
        """The JSON-safe form a console server reply carries."""
        return {"document": self.document, "problem": self.problem}

    @classmethod
    def from_payload(cls, payload: object) -> Authored:
        """The configuration a `to_payload` result describes; any schema break is `ValueError`."""
        if not isinstance(payload, dict) or set(payload) != {"document", "problem"}:
            raise ValueError("Authored: unexpected fields")
        document = payload["document"]
        problem = payload["problem"]
        if document is not None and not isinstance(document, dict):
            raise ValueError("Authored: the document is not an object")
        if not isinstance(problem, str):
            raise ValueError("Authored: the problem is not a string")
        return cls(document, problem)


def read_authored(repo: Path) -> Authored:
    path = repo / ".harness" / "orchestration.json"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return Authored(None, f"конфигурация не прочитана: {exc.strerror or exc}")
    try:
        document = json.loads(text)
    except ValueError:
        return Authored(None, "конфигурация не разбирается как JSON")
    if not isinstance(document, dict):
        return Authored(None, "конфигурация не является объектом JSON")
    return Authored(document)
