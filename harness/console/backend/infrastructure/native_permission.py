"""Native permission answers as console decision commands, and the script that sends one.

The coordinator CLI has no subcommand for a native permission answer, so the console runs this
file as a script: ``main`` calls ``respond_native_permission``, which rechecks the request digest,
the live dispatch state and the tool policy. The console decides nothing itself. Each command has
the job protocol of ``CatalogEntry``: ``JobService`` asks for the confirmation, takes the mutation
slot and journals it with masked values like any other command.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):
    # Run by path, this file's directory is on sys.path, where console modules could shadow the
    # standard library; the repository root goes first so `harness` resolves to the package.
    _ROOT = Path(__file__).resolve().parents[4]
    _OWN_DIR = Path(__file__).resolve().parent
    sys.path[:] = [
        entry
        for entry in sys.path
        if entry != str(_ROOT) and Path(entry or ".").resolve() != _OWN_DIR
    ]
    sys.path.insert(0, str(_ROOT))

from harness.console.kernel.catalog import Reversibility  # noqa: E402

_COORDINATOR_SCRIPT = ".harness/orchestration/coordinator.py"
_SCRIPT = Path(__file__).resolve()
_FIELDS = ("dispatch", "request_id", "request_sha256")
_FLAGS = {
    "dispatch": "--dispatch",
    "request_id": "--request-id",
    "request_sha256": "--request-sha256",
}
_DISPATCH = re.compile(r"dispatch-[0-9a-f-]+")
_SHA256 = re.compile(r"[0-9a-f]{64}")
# The runtime stages request ids of up to 256 characters (`runtime_permissions.stage_request`).
_MAX_ID_CHARS = 256


@dataclass(frozen=True)
class DecisionCommand:
    """A native permission answer with the job protocol of a catalog entry."""

    key: str
    title: str
    allow: bool
    reversibility: Reversibility = Reversibility.EXTERNAL_CHANGE
    read_only: bool = False

    @property
    def needs_confirmation(self) -> bool:
        """An answer reaches a live runtime and cannot be withdrawn: it always asks first."""
        return self.reversibility is not Reversibility.REVERSIBLE

    def available(self, repo: Path) -> bool:
        """Answers need the project's coordinator: its ledger holds the dispatch and the request."""
        return (repo / _COORDINATOR_SCRIPT).is_file()

    def accepts(self, values: Mapping[str, str]) -> bool:
        """Exactly the dispatch, the request id and its digest, each non-empty and bounded."""
        if set(values) != set(_FIELDS):
            return False
        if any(
            not value.strip() or len(value) > _MAX_ID_CHARS for value in values.values()
        ):
            return False
        return bool(
            _DISPATCH.fullmatch(values["dispatch"])
            and _SHA256.fullmatch(values["request_sha256"])
        )

    def cli_argv(
        self, repo: Path, values: Mapping[str, str] | None = None
    ) -> list[str]:
        """The script call for `repo`; `process_argv` replaces `python` with the console's own."""
        filled = values or {}
        argv = ["python", str(_SCRIPT), "--repo", str(repo)]
        for name in _FIELDS:
            argv.extend([_FLAGS[name], filled.get(name, f"<{name}>")])
        argv.append("--allow" if self.allow else "--deny")
        return argv

    def cli_line(self, repo: Path, values: Mapping[str, str] | None = None) -> str:
        """The escaped command line shown in the interface."""
        return shlex.join(self.cli_argv(repo, values))


NATIVE_PERMISSION_COMMANDS: tuple[DecisionCommand, ...] = (
    DecisionCommand(
        "native-permission-allow", "Разрешить запрос native permission", allow=True
    ),
    DecisionCommand(
        "native-permission-deny", "Отклонить запрос native permission", allow=False
    ),
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Answer one pending native permission request of a dispatch."
    )
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--dispatch", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--request-sha256", required=True)
    answer = parser.add_mutually_exclusive_group(required=True)
    answer.add_argument("--allow", action="store_true")
    answer.add_argument("--deny", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Send the answer and print its JSON result; a refused answer prints the reason, code 1."""
    from harness.orchestration.core.utils import CoordinatorError
    from harness.orchestration.workflow import delivery

    args = _parser().parse_args(argv)
    try:
        result = delivery.respond_native_permission(
            args.repo,
            args.dispatch,
            args.request_id,
            args.request_sha256,
            allow=args.allow,
        )
    except CoordinatorError as exc:
        print(f"ERROR: {exc.message}\nREMEDY: {exc.remedy}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
