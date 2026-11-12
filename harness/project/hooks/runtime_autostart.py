#!/usr/bin/env python3
"""Помощник hook-а ``runtime-autostart`` (ADR 0031, раздел 5).

Помощник только читает: payload события, пути и dep-info сборки. Процессы запускает
``runtime-autostart.sh`` (git и ``harness-runtime ensure``/``release``), а serve запускает сам
Rust-бинарник; Python процессов не запускает (ADR 0021).

- ``parse`` читает payload из stdin и печатает четыре строки: событие, сессию, агента (или пустую
  строку) и checkout. Для ``PreToolUse`` checkout — третий родитель пути
  ``.harness/orchestration/coordinator.py`` из команды (относительный путь берётся от ``cwd``
  payload); команда без coordinator даёт пустой вывод. Для ``Stop`` и ``SubagentStop`` checkout —
  ``cwd`` payload.
- ``binary <основной checkout>`` печатает вид и путь бинарника: ``source``/``stale``/``unbuilt``
  для сборки из исходников рабочего пространства, ``path`` для ``harness-runtime`` из ``PATH`` и
  ``missing``, когда бинарника нет.
- ``report <вид> [код ensure] [JSON ensure]`` печатает ответ hook-а: stdout — JSON протокола
  Claude Code, первая строка stderr — ``[runtime-autostart-failed] <причина>`` для предупреждения.

Только стандартная библиотека, Python 3.9+.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Dict, Iterator, List, Optional

sys.dont_write_bytecode = True

REASON = "runtime-autostart-failed"
COORDINATOR = re.compile(r"""(?:^|[\s"'=(;&|])([^\s"';&|()]*\.harness/orchestration/coordinator\.py)(?=$|[\s"';&|)])""")
OWNER_PART = re.compile(r"[A-Za-z0-9._:-]{1,120}")
WORKSPACE = PurePosixPath("native/harness-runtime")
BINARY = "harness-runtime"
BUILD = "cargo build --release --manifest-path native/harness-runtime/Cargo.toml"


def _payload(text: str) -> Dict[str, object]:
    try:
        payload = json.loads(text)
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _text(payload: Dict[str, object], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def coordinator_checkout(command: str, cwd: str) -> Optional[Path]:
    """Checkout, чей coordinator вызывает команда: третий родитель ``coordinator.py``."""
    found = COORDINATOR.search(command)
    if found is None:
        return None
    path = Path(found.group(1))
    if not path.is_absolute():
        if not cwd:
            return None
        path = Path(cwd) / path
    return path.parents[2]


def parse(text: str) -> List[str]:
    """Событие, сессия, агент и checkout; пустой список — hook молчит."""
    payload = _payload(text)
    event = _text(payload, "hook_event_name")
    session = _text(payload, "session_id")
    agent = _text(payload, "agent_id")
    cwd = _text(payload, "cwd")
    if not OWNER_PART.fullmatch(session) or (agent and not OWNER_PART.fullmatch(agent)):
        return []
    if event == "PreToolUse":
        tool_input = payload.get("tool_input")
        command = tool_input.get("command") if isinstance(tool_input, dict) else None
        if not isinstance(command, str):
            return []
        checkout = coordinator_checkout(command, cwd)
        if checkout is None:
            return []
    elif event in ("Stop", "SubagentStop"):
        if not cwd:
            return []
        checkout = Path(cwd)
        if event == "Stop":
            agent = ""
    else:
        return []
    if "\n" in str(checkout):
        return []
    return [event, session, agent, str(checkout)]


def dep_info_paths(text: str) -> Iterator[str]:
    """Пути зависимостей из dep-info cargo: после ``<цель>:``, пробел внутри пути экранирован."""
    joined = text.replace("\\\n", " ")
    for line in joined.splitlines():
        head, sep, rest = line.partition(": ")
        if not sep or not head:
            continue
        for token in re.split(r"(?<!\\) +", rest.strip()):
            if token:
                yield token.replace("\\ ", " ")
        return


def stale(workspace: Path, binary: Path) -> bool:
    """Устарела ли сборка: файл dep-info, ``Cargo.lock`` или ``Cargo.toml`` новее бинарника,
    либо dep-info нет или он не читается."""
    try:
        built = binary.stat().st_mtime
        text = (binary.parent / f"{BINARY}.d").read_text("utf-8")
    except (OSError, ValueError):
        return True
    sources = list(dep_info_paths(text))
    if not sources:
        return True
    sources.append(str(workspace / "Cargo.lock"))
    sources.append(str(workspace / "Cargo.toml"))
    sources.extend(str(path) for path in sorted(workspace.glob("crates/*/Cargo.toml")))
    for source in sources:
        try:
            if Path(source).stat().st_mtime > built:
                return True
        except OSError:
            return True
    return False


def binary(main: Path) -> List[str]:
    """Вид и путь бинарника основного checkout."""
    workspace = main / WORKSPACE
    if (workspace / "Cargo.toml").is_file():
        built = workspace / "target" / "release" / BINARY
        if not built.is_file():
            return ["unbuilt", str(built)]
        return ["stale" if stale(workspace, built) else "source", str(built)]
    found = shutil.which(BINARY)
    return ["path", found] if found else ["missing", ""]


def _warn(reason: str) -> int:
    """Предупреждение: stderr с префиксом причины, stdout — сообщение человеку и контекст агенту."""
    message = f"runtime-autostart: {reason}"
    print(f"[{REASON}] {reason}", file=sys.stderr)
    print(
        json.dumps(
            {
                "systemMessage": message,
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": message,
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


MANUAL = (
    "запустите `harness-runtime serve --repo <repo>` вручную вне песочницы агента; "
    "агент serve не запускает"
)


def report(kind: str, args: List[str]) -> int:
    """Ответ hook-а по виду исхода."""
    if kind == "sandbox":
        return _warn(f"hook исполняется в песочнице агента (SANDBOX_RUNTIME=1); {MANUAL}")
    if kind == "unbuilt":
        return _warn(f"бинарник {args[0] if args else BINARY} не собран: выполните `{BUILD}`")
    if kind == "missing":
        return _warn(f"бинарник {BINARY} не найден ни в рабочем пространстве, ни в PATH; {MANUAL}")
    if kind == "stale":
        return _warn(
            f"сборка {args[0] if args else BINARY} устарела и не запускается: выполните `{BUILD}`"
        )
    if kind == "git":
        return _warn(f"не найден основной checkout репозитория {args[0] if args else ''}")
    if kind != "ensure" or len(args) < 2:
        return _warn(f"неизвестный исход {kind}")
    code, text = args[0], args[1]
    answer = _payload(text.strip().splitlines()[0] if text.strip() else "")
    status = answer.get("status")
    if code == "0" and status == "started":
        message = (
            f"runtime-autostart: harness-runtime serve запущен автоматически "
            f"(pid {answer.get('pid')}, журнал {answer.get('log')})"
        )
        print(json.dumps({"systemMessage": message}, ensure_ascii=False))
        return 0
    if code == "0" and status == "reused":
        return 0
    if status == "refused":
        return _warn(
            f"harness-runtime serve отказал при старте (код {answer.get('exit_code')}): "
            f"{answer.get('error')}; REMEDY: {answer.get('remedy')}; журнал {answer.get('log')}"
        )
    if status == "timeout":
        return _warn(
            f"harness-runtime serve не ответил за {answer.get('seconds')} с; "
            f"журнал {answer.get('log')}"
        )
    detail = answer.get("error") or text.strip() or "нет вывода"
    remedy = answer.get("remedy")
    return _warn(
        f"harness-runtime ensure завершился кодом {code}: {detail}"
        + (f"; REMEDY: {remedy}" if remedy else "")
    )


def main(argv: List[str]) -> int:
    if argv[:1] == ["parse"]:
        for line in parse(sys.stdin.read()):
            print(line)
        return 0
    if argv[:1] == ["binary"] and len(argv) == 2:
        for line in binary(Path(argv[1])):
            print(line)
        return 0
    if argv[:1] == ["report"] and len(argv) >= 2:
        return report(argv[1], argv[2:])
    print("[internal-error] runtime_autostart.py: parse | binary <main> | report <kind>", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
