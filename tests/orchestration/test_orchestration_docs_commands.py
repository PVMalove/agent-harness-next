"""The orchestration documents name only coordinator commands and options that exist (#685).

Every inline code span and every code-block line of the documents below that starts with a
coordinator command group (after an optional ``python <path>/coordinator.py`` and its ``--repo`` or
``--state-dir``) must name a subcommand of that group in ``coordinator.parser()``, and each of its
``--options`` must be accepted by that subcommand or the root parser. ``a|b`` lists alternatives.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness.orchestration import coordinator

ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS = (
    "harness/orchestration/playbook.md",
    "harness/orchestration/README.md",
    "site/docs/backend-orchestration.md",
    "site/docs/skills/implement.md",
    "skills/first-party/engineering/implement/SKILL.md",
    "README.md",
)
_SPAN = re.compile(r"`([^`\n]+)`")
_FENCE = re.compile(r"^\s*```")
_WORDS = re.compile(r"[a-z][a-z-]*(?:\|[a-z][a-z-]*)*")
_PREFIX = re.compile(
    r"^(?:python3?\s+)?\S*coordinator\.py\s+|^(?:--repo|--state-dir)\s+\S+\s+"
)


def _subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action._name_parser_map)
    return {}


def _options(parser: argparse.ArgumentParser) -> set[str]:
    return {option for action in parser._actions for option in action.option_strings}


ROOT_PARSER = coordinator.parser()
GROUPS = _subcommands(ROOT_PARSER)


def _fragments(text: str) -> Iterator[str]:
    """Inline code spans outside code blocks, and the lines of the code blocks."""
    in_block = False
    for line in text.splitlines():
        if _FENCE.match(line):
            in_block = not in_block
            continue
        if in_block:
            yield line.strip().rstrip("\\").strip()
        else:
            yield from _SPAN.findall(line)


def _strip_prefix(fragment: str) -> str:
    previous = None
    while previous != fragment:
        previous = fragment
        fragment = _PREFIX.sub("", fragment, count=1)
    return fragment


def _is_command(tokens: list[str], depth: int) -> bool:
    """Prose such as an error message (`ledger is locked …`) is not a command: after the command
    words a command has only options, placeholders and their values."""
    rest = tokens[depth:]
    return not rest or rest[0].startswith(("-", "<", "["))


def command_problems(text: str) -> list[str]:
    """Why a fragment of ``text`` names a coordinator command or option that does not exist."""
    problems: list[str] = []
    for fragment in _fragments(text):
        tokens = _strip_prefix(fragment).split()
        if len(tokens) >= 2 and tokens[0] in GROUPS:
            problems.extend(_walk(fragment, tokens, [tokens[0]], GROUPS[tokens[0]]))
    return problems


def _walk(
    fragment: str, tokens: list[str], path: list[str], parser: argparse.ArgumentParser
) -> list[str]:
    depth = len(path)
    subcommands = _subcommands(parser)
    if not subcommands or depth == len(tokens) or not _WORDS.fullmatch(tokens[depth]):
        if depth > 1 and _is_command(tokens, depth):
            return _option_problems(fragment, path, parser)
        return []
    problems: list[str] = []
    for name in tokens[depth].split("|"):
        if name in subcommands:
            problems.extend(_walk(fragment, tokens, [*path, name], subcommands[name]))
        elif _is_command(tokens, depth + 1):
            problems.append(f"{fragment!r}: no command {' '.join(path)} {name}")
    return problems


def _option_problems(
    fragment: str, path: list[str], parser: argparse.ArgumentParser
) -> list[str]:
    accepted = _options(parser) | _options(ROOT_PARSER)
    return [
        f"{fragment!r}: {' '.join(path)} has no option {option}"
        for option in re.findall(r"(?<![\w-])--[a-z][a-z-]*", fragment)
        if option not in accepted
    ]


@pytest.mark.parametrize("relative", DOCUMENTS)
def test_every_documented_coordinator_command_exists(relative: str) -> None:
    text = (ROOT / relative).read_text(encoding="utf-8")

    assert command_problems(text) == []


def test_an_invented_subcommand_or_option_is_a_problem() -> None:
    text = (
        "Run `recovery rollback --batch <id>`.\n"
        "```bash\n"
        "python .harness/orchestration/coordinator.py --repo . config validate --strict\n"
        "```\n"
    )

    assert command_problems(text) == [
        "'recovery rollback --batch <id>': no command recovery rollback",
        "'python .harness/orchestration/coordinator.py --repo . config validate --strict': "
        "config validate has no option --strict",
    ]


def test_existing_commands_alternatives_and_options_pass() -> None:
    text = (
        "`recovery status|reload|resume|fix|abort --batch <id>` and "
        "`config validate --repo . --canonical --json`.\n"
    )

    assert command_problems(text) == []
