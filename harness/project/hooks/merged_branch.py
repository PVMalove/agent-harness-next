#!/usr/bin/env python3
"""Доказательство слияния для удаления issue-ветки: `git branch -D` и `git push --delete`.

Удаление разрешено, только если ветка подходит под `branch_pattern` из `.harness/project.json`,
не защищена (`master`, `main`, `base_branch`, `integration/*`) и в трекере есть слитый PR/MR этой
ветки, голова которого равна SHA удаляемой ветки. Squash- и rebase-слияние оставляют коммиты
ветки вне истории цели, поэтому слияние доказывает состояние PR, а не Git. Трекер, CLI или
резолвер недоступны, ответ не разобран — удаление блокируется (fail closed), в отличие от
`tracker-issue.py`, который в таких случаях пропускает команду.

CLI для `block-dangerous-git.sh`: `merged_branch.py < payload.json` печатает `allow` и завершается
с кодом 0, если команда — ровно `git branch -D <ветка>...` и каждая ветка доказана. Иначе код 2 и
причина в stdout; команда другой формы — код 2 без вывода (хук оставляет свою блокировку).
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict

if TYPE_CHECKING:
    from harness.health.project_tracker import TrackerResolution

    Run = Callable[[list[str]], subprocess.CompletedProcess[str] | None]
    Resolve = Callable[[Path], TrackerResolution]

Settings = Dict[str, object]

GIT_TIMEOUT_SECONDS = 10
# Only one plain command: no operators, expansions, quotes or git global options.
LOCAL_DELETE = re.compile(r"git branch -D((?: [A-Za-z0-9._/-]+)+)")
RULE = "Удаление ветки"


def _settings(project: Path) -> Settings:
    try:
        data = json.loads(
            (project / ".harness" / "project.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _setting(settings: Settings, key: str) -> str:
    value = settings.get(key, "")
    return value if isinstance(value, str) else ""


def _tracker_tools(project: Path) -> tuple[Resolve, Run] | None:
    """Резолвер трекера и run_tool через загрузчик `tracker-issue.py`; None — его нет."""
    path = Path(__file__).resolve().with_name("tracker-issue.py")
    # The loader rebinds the `harness` package to the project's `.harness`; undo it afterwards so
    # an importing process keeps its own `harness` modules.
    saved = {
        key: value
        for key, value in sys.modules.items()
        if key == "harness" or key.startswith("harness.")
    }
    try:
        spec = importlib.util.spec_from_file_location("tracker_issue_hook", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tools: tuple[Resolve, Run] | None = module.load_tracker_tools(project)
        return tools
    except Exception:
        return None
    finally:
        for key in [
            k for k in sys.modules if k == "harness" or k.startswith("harness.")
        ]:
            del sys.modules[key]
        sys.modules.update(saved)


def _merged_heads(kind: str | None, stdout: str) -> list[str] | None:
    """SHA голов слитых PR/MR из JSON-ответа CLI; None — ответ не разобрать."""
    try:
        items = json.loads(stdout)
    except ValueError:
        return None
    if not isinstance(items, list):
        return None
    state, head = ("MERGED", "headRefOid") if kind == "github" else ("merged", "sha")
    return [
        str(item.get(head))
        for item in items
        if isinstance(item, dict) and item.get("state") == state
    ]


def merge_block_reason(
    project: Path,
    branch: str,
    sha: str,
    run: Run | None = None,
    resolve: Resolve | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> str:
    """Причина запретить удаление `branch` с головой `sha`; "" — слияние доказано."""
    settings = _settings(project)
    base_branch = _setting(settings, "base_branch")
    if branch in {"master", "main", base_branch} - {""} or branch.startswith(
        "integration/"
    ):
        return f"{RULE}: '{branch}' — защищённая ветка, агент её не удаляет."
    pattern = _setting(settings, "branch_pattern")
    try:
        matches = bool(pattern) and re.match(pattern, branch) is not None
    except re.error:
        matches = False
    if not matches:
        return (
            f"{RULE}: '{branch}' не подходит под branch_pattern из .harness/project.json — "
            "агент удаляет только issue-ветки."
        )
    if run is None or resolve is None:
        tools = _tracker_tools(project)
        if tools is None:
            return (
                f"{RULE}: резолвер трекера (.harness/health) не загрузился, слияние "
                f"'{branch}' не проверить — удали ветку вручную."
            )
        resolve, run = tools
    kind: str | None = None
    host: str | None = None
    name: str | None = None
    try:
        tracker = resolve(project).effective
        kind, host, name = tracker.type, tracker.host, tracker.project
    except Exception:
        pass  # an unusable resolver leaves the tracker unknown: blocked below
    if kind == "github":
        tool, address = "gh", f"{host}/{name}"
    elif kind == "gitlab":
        tool, address = "glab", f"https://{host}/{name}"
    else:
        tool = address = ""
    if not tool or host is None or name is None:
        return (
            f"{RULE}: трекер проекта не GitHub/GitLab или не определён, слияние '{branch}' "
            "не проверить — удали ветку вручную."
        )
    executable = which(tool)
    if executable is None:
        return f"{RULE}: {tool} не установлен, слияние '{branch}' не проверить."
    if kind == "github":
        argv = [executable, "pr", "list", "-R", address, "--head", branch]
        argv += ["--state", "merged", "--json", "number,state,headRefOid"]
    else:
        argv = [executable, "mr", "list", "-R", address, "--source-branch", branch]
        argv += ["--merged", "-F", "json"]
    result = run(argv)
    if result is None or result.returncode != 0:
        return (
            f"{RULE}: трекер не ответил на '{tool} {' '.join(argv[1:3])}' для '{branch}' — "
            "слияние не доказано, ветка не удалена. Проверь доступ к трекеру и повтори."
        )
    heads = _merged_heads(kind, result.stdout)
    if heads is None:
        return f"{RULE}: ответ {tool} о PR ветки '{branch}' не разобран — удаление заблокировано."
    if sha in heads:
        return ""
    if heads:
        return (
            f"{RULE}: голова слитого PR ветки '{branch}' ({', '.join(heads)}) не равна SHA "
            f"ветки {sha} — в ветке есть неслитые коммиты, удаление заблокировано."
        )
    return f"{RULE}: у '{branch}' нет слитого PR — удали ветку после слияния."


def _local_sha(cwd: Path, branch: str) -> str | None:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(cwd),
                "rev-parse",
                "--verify",
                "--quiet",
                f"refs/heads/{branch}",
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def local_delete_reason(command: str, cwd: Path, project: Path) -> str:
    """Причина запретить `git branch -D <ветки>`; "" — каждая ветка доказана."""
    found = LOCAL_DELETE.fullmatch(command.strip())
    if found is None:
        return ""  # not the exempt form: the caller keeps its own block
    for branch in found.group(1).split():
        sha = _local_sha(cwd, branch)
        if sha is None:
            return f"{RULE}: локальной ветки '{branch}' нет или git не ответил."
        reason = merge_block_reason(project, branch, sha)
        if reason:
            return reason
    return ""


def main() -> int:
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except ValueError:
        data = None
    payload = data if isinstance(data, dict) else {}
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    cwd = payload.get("cwd")
    start = Path(cwd) if isinstance(cwd, str) and cwd else project
    if not isinstance(command, str) or LOCAL_DELETE.fullmatch(command.strip()) is None:
        return 2
    reason = local_delete_reason(command, start, project)
    if reason:
        print(reason)
        return 2
    print("allow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
