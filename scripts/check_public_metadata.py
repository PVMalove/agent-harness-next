#!/usr/bin/env python3
"""Запрет атрибуции автоматических AI-агентов в сообщениях коммитов и описаниях PR."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Runtime and model names are project vocabulary; only attribution is forbidden.
FORBIDDEN = re.compile(
    r"(?<![a-z0-9])co-authored[- ]by\s*:\s*"
    r"(?:claude(?:\s+code)?|openai|chatgpt|copilot|gemini|codex|gpt(?:[-_ ]?[0-9][a-z0-9._-]*)?)"
    r"(?=\s*(?:<|_?(?:\r?\n|$)))|"
    r"(?<![a-z0-9])(generated|written|created|authored|produced)\s+(with|by|using|via)\s+"
    r"\[?(claude|chatgpt|openai|copilot|gemini|codex|gpt[-_ ]?[0-9])|"
    r"(?<![a-z0-9])ai[-_ ]?generated(?![a-z0-9])|"
    r"(?<![a-z0-9.-])(claude\.ai|chatgpt\.com|chat\.openai\.com)/",
    re.IGNORECASE,
)
GIT_TIMEOUT_SECONDS = 60


def git_messages(
    commit_range: str, exclude_reachable_from: str | None = None
) -> list[tuple[str, str]]:
    """Получить список пар (хеш коммита, текст сообщения) для заданного диапазона коммитов git.

    `exclude_reachable_from` убирает из диапазона коммиты, уже достижимые из этой ссылки.
    """
    exclusion = ["--not", exclude_reachable_from] if exclude_reachable_from else []
    result = subprocess.run(
        [
            "git",
            "log",
            "--format=%H%x00%B%x00",
            "--no-merges",
            commit_range,
            *exclusion,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    fields = result.stdout.split("\x00")
    return list(zip(fields[0::2], fields[1::2]))


def main() -> int:
    """Точка входа CLI: проверка сообщений коммитов и тела PR на автоматическую атрибуцию."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit-range")
    # A PR into an integration branch carries default-branch commits its base lacks: they are
    # already published and cannot be rewritten, so they are not checked again.
    parser.add_argument("--exclude-reachable-from")
    parser.add_argument("--pr-body-file", type=Path)
    args = parser.parse_args()

    violations: list[str] = []
    if args.commit_range:
        for commit, message in git_messages(
            args.commit_range, args.exclude_reachable_from
        ):
            match = FORBIDDEN.search(message)
            if match:
                violations.append(
                    f"commit {commit}: forbidden metadata near {match.group(0)!r}"
                )
    if args.pr_body_file:
        # An explicit body file that is missing must fail, not pass the check unread.
        if not args.pr_body_file.is_file():
            parser.error(f"PR body file not found: {args.pr_body_file}")
        body = args.pr_body_file.read_text(encoding="utf-8")
        match = FORBIDDEN.search(body)
        if match:
            violations.append(f"PR body: forbidden metadata near {match.group(0)!r}")

    if violations:
        print("Public Git metadata check failed:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1
    print("Public Git metadata check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
