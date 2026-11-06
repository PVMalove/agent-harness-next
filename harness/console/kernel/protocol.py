"""Wire constants of the console protocol that the server and the TUI client share: the protocol
version, the Home request types, the request and message limits and the JSON-string clipping that
keeps a reply below them, and the screen snapshot request types. Standard library only."""

from __future__ import annotations

import re

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 4096
MAX_ID_CHARS = 64
HOME_REQUEST = "home.snapshot"
HOME_PROBLEMS_REQUEST = "home.problems"
# The screen snapshots of Reports, Orchestration, Recovery and Container route; every reply is the
# first page of a JSON text the client completes with `snapshot.page`.
REPORTS_REQUEST = "reports.snapshot"
REPORT_REQUEST = "reports.report"
TIMELINE_REQUEST = "reports.timeline"
ORCHESTRATION_REQUEST = "orchestration.snapshot"
LOCK_REQUEST = "orchestration.lock"
RECOVERY_REQUEST = "recovery.snapshot"
ROUTE_REQUEST = "container_route.snapshot"
PAGE_REQUEST = "snapshot.page"
# The task board: the open specs and the board of one spec, paged like the screen snapshots.
TASK_BOARD_SPECS_REQUEST = "task_board.specs"
TASK_BOARD_REQUEST = "task_board.snapshot"
# The Diagnostics health report and the Harness screen: its state, drift and pipeline usage, and
# its maintenance facts apart, because sizing the cleanup plan is slow. Paged like the others.
DIAGNOSTICS_REQUEST = "diagnostics.snapshot"
HARNESS_REQUEST = "harness.snapshot"
MAINTENANCE_REQUEST = "harness.maintenance"
# The Harness screen of the Web console: the same state and drift as `harness.snapshot` with the
# pipeline usage counted on the server, one typed reply instead of the paged ledger.
HARNESS_OVERVIEW_REQUEST = "harness.overview"
# The Repo Map screen: HEAD, its cached map, the tier, the parser bundle and the memory status.
REPO_MAP_REQUEST = "repo_map.snapshot"
# «Открыть проект»: the installation state of the served project and the candidate projects, each
# with the command that starts the Web console there; the server never switches its project.
OPEN_PROJECT_REQUEST = "open_project.snapshot"
# «Справка»: the console guide in the requested language, split into its sections.
HELP_REQUEST = "help.snapshot"
# «Обновить Harness»: the installed harness, the package version and the drift report, and the
# diff of one file the drift report lists against what `harness update` writes there.
UPDATE_HARNESS_REQUEST = "update_harness.snapshot"
UPDATE_DIFF_REQUEST = "update_harness.diff"
# «Настройка»: the configuration files with their secrets masked and their digests, the version
# store, a pending transaction and the runtime adapter preview; never written or recovered.
CONFIGURATION_REQUEST = "configuration.snapshot"
# The longest project-relative path a request may name.
MAX_PATH_CHARS = 512
# Worker steps: one page of a dispatch's worker log from a byte offset the client keeps, and a
# stream of such pages in a subscription slot.
WORKER_STEPS_REQUEST = "worker.steps"
WORKER_SUBSCRIBE_REQUEST = "worker.subscribe"
# How many diagnostics one `recovery.snapshot` may skip.
MAX_SKIPPED = 32

MESSAGE_BYTES = 300
ID_BYTES = 100
MESSAGE_LIMIT = 65536

_SHORT_ESCAPES = frozenset('"\\\b\f\n\r\t')

# json.loads accepts "\ud800"; the str cannot be encoded as UTF-8, so a reply carries it escaped.
_LONE_SURROGATE = re.compile("[\ud800-\udfff]")


def _wire_cost(char: str) -> int:
    """Bytes `char` takes inside a JSON string: a quote, a backslash or a short escape is two,
    any other control character and a lone surrogate (sent as `\\udXXX`) is six, everything
    else is its UTF-8 length."""
    if char in _SHORT_ESCAPES:
        return 2
    if char < " " or _LONE_SURROGATE.match(char):
        return 6
    return len(char.encode("utf-8"))


def _clip(text: str, limit: int) -> str:
    """The longest prefix of `text` that takes at most `limit` bytes as a JSON string."""
    used = 0
    for index, char in enumerate(text[:limit]):
        used += _wire_cost(char)
        if used > limit:
            return text[:index]
    return text[:limit]
