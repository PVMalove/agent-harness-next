#!/usr/bin/env python3
"""Адаптер payload `apply_patch` второго runtime для критичных guards Write/Edit (issue #830).

Второй runtime присылает правку файлов как `tool_name: "apply_patch"` с телом патча в
`tool_input.command` и без `file_path`; shell-вызов `apply_patch <<'EOF'` приходит как `Bash`.
Модуль повторяет разбор патча runtime (режим Lenient: heredoc-обёртка, пробелы вокруг маркеров,
`*** Environment ID:`, `*** End of File`, `*** Move to:`) и отдаёт операции с абсолютными путями.
`PatchError` возникает ровно там, где runtime сам отвергает патч, плюс NUL в пути.

`python apply_patch_payload.py fanout -- <cmd...>` читает payload из stdin и для каждого пути патча
запускает `cmd` с синтетическим payload `Write{file_path}` на stdin; первый ненулевой код и его stderr
пробрасываются. Только стандартная библиотека, Python 3.9+.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

# .claude/hooks must stay prunable by uninstall: never leave __pycache__ next to it.
sys.dont_write_bytecode = True

# Rust `char::is_whitespace` (White_Space): `str.strip()` without arguments also strips \x1c-\x1f.
WS = (
    "\t\n\x0b\x0c\r \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007"
    "\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"
)
BEGIN = "*** Begin Patch"
END = "*** End Patch"
ADD = "*** Add File: "
DELETE = "*** Delete File: "
UPDATE = "*** Update File: "
MOVE = "*** Move to: "
EOF_MARKER = "*** End of File"
CONTEXT = "@@ "
EMPTY_CONTEXT = "@@"
ENVIRONMENT = "*** Environment ID:"
HEREDOC_OPENINGS = ("<<EOF", "<<'EOF'", '<<"EOF"')
HEADERS = (ADD, UPDATE, DELETE, MOVE)
SHELL_LINE = re.compile(
    r"^\s*(?:cd[ \t]+(?:(?P<w>[^\s'\"\\$`&|;<>()]+)|'(?P<r>[^']*)'|\"(?P<d>[^\"\\$`]*)\")"
    r"[ \t]*&&[ \t]*)?(?:apply_patch|applypatch)[ \t]*<<[ \t]*(?P<q>['\"]?)"
    r"(?P<delim>[A-Za-z_][A-Za-z0-9_]*)(?P=q)[ \t]*$"
)
REASON = "apply-patch-unparseable"
PATCH_WORD = re.compile(r"(?<![\w./-])(?:apply_patch|applypatch)(?![\w./-])")


class PatchError(ValueError):
    """Патч нельзя разобрать так, как его разобрал бы runtime; текст — причина без патча."""


class Chunk(NamedTuple):
    """Чанк Update: строки до и после, индексы строк контекста, якорь `@@`, конец файла."""

    change_context: Optional[str]
    old_lines: Tuple[str, ...]
    new_lines: Tuple[str, ...]
    context_indices: Tuple[Tuple[int, int], ...]
    end_of_file: bool


class FileOp(NamedTuple):
    """Операция патча над одним файлом."""

    kind: str  # "add" | "update" | "delete"
    path: str
    move_to: Optional[str]
    content: Optional[str]
    chunks: Tuple[Chunk, ...]


class _Op:
    def __init__(self, kind: str, path: str) -> None:
        self.kind = kind
        self.path = path
        self.move_to: Optional[str] = None
        self.content = ""
        self.chunks: List[Dict[str, object]] = []


def _chunk() -> Dict[str, object]:
    return {"context": None, "old": [], "new": [], "indices": [], "eof": False}


def _empty(chunk: Dict[str, object]) -> bool:
    return not chunk["old"] and not chunk["new"]


def _lines(text: str) -> List[str]:
    """Rust `str::lines`: деление по `\\n`, снятие одного `\\r`, без пустого хвоста."""
    if not text:
        return []
    parts = text.split("\n")
    if parts[-1] == "":
        parts.pop()
    return [part[:-1] if part.endswith("\r") else part for part in parts]


def _boundaries(lines: List[str]) -> List[str]:
    def strict(candidate: List[str]) -> None:
        first = candidate[0].strip(WS) if candidate else None
        last = candidate[-1].strip(WS) if candidate else None
        if first == BEGIN and last == END:
            return
        if first != BEGIN:
            raise PatchError("The first line of the patch must be '*** Begin Patch'")
        raise PatchError("The last line of the patch must be '*** End Patch'")

    try:
        strict(lines)
        return lines
    except PatchError:
        if (
            len(lines) >= 4
            and lines[0] in HEREDOC_OPENINGS
            and lines[-1].endswith("EOF")
        ):
            inner = lines[1:-1]
            strict(inner)
            return inner
        raise


class _Parser:
    """Порт потокового разбора runtime: одна строка за шаг, режимы как у runtime."""

    def __init__(self) -> None:
        self.mode = "not-started"
        self.ops: List[_Op] = []
        self.environment: Optional[str] = None

    def _ensure_update_not_empty(self) -> None:
        if not self.ops or self.ops[-1].kind != "update":
            return
        last = self.ops[-1]
        if not last.chunks and self.mode == "update":
            raise PatchError("an Update File hunk is empty")
        if last.chunks and _empty(last.chunks[-1]):
            raise PatchError("Update hunk does not contain any lines")

    def _headers(self, trimmed: str) -> bool:
        if self.mode == "started" and trimmed.startswith(ENVIRONMENT):
            if self.environment is not None:
                raise PatchError(
                    "apply_patch environment_id cannot be specified more than once"
                )
            value = trimmed[len(ENVIRONMENT) :].strip(WS)
            if not value:
                raise PatchError("apply_patch environment_id cannot be empty")
            self.environment = value
            return True
        if trimmed == END:
            self._ensure_update_not_empty()
            self.mode = "ended"
            return True
        for marker, kind in ((ADD, "add"), (DELETE, "delete"), (UPDATE, "update")):
            if trimmed.startswith(marker):
                self._ensure_update_not_empty()
                self.ops.append(_Op(kind, trimmed[len(marker) :]))
                self.mode = kind
                return True
        return False

    def line(self, line: str) -> None:
        trimmed = line.strip(WS)
        if self.mode == "not-started":
            if trimmed != BEGIN:
                raise PatchError(
                    "The first line of the patch must be '*** Begin Patch'"
                )
            self.mode = "started"
        elif self.mode in ("started", "add", "delete"):
            if self._headers(trimmed):
                return
            if self.mode == "add" and line.startswith("+"):
                self.ops[-1].content += line[1:] + "\n"
                return
            raise PatchError("a line is not a valid hunk header")
        elif self.mode == "update":
            self._update(line)
        elif trimmed:
            raise PatchError("The last line of the patch must be '*** End Patch'")

    def _update(self, line: str) -> None:
        update_line = line.rstrip(WS)
        if self._headers(update_line):
            return
        op = self.ops[-1]
        chunks = op.chunks
        is_context = update_line == EMPTY_CONTEXT or update_line.startswith(CONTEXT)
        if chunks and chunks[-1]["eof"]:
            if not update_line:
                return
            if not is_context:
                raise PatchError("expected an @@ context marker after *** End of File")
        if not chunks and op.move_to is None and update_line.startswith(MOVE):
            op.move_to = update_line[len(MOVE) :]
            return
        if is_context and chunks and _empty(chunks[-1]):
            raise PatchError("Update hunk does not contain any lines")
        if is_context:
            chunk = _chunk()
            if update_line != EMPTY_CONTEXT:
                chunk["context"] = update_line[len(CONTEXT) :]
            chunks.append(chunk)
            return
        if update_line == EOF_MARKER:
            if chunks and _empty(chunks[-1]):
                raise PatchError("Update hunk does not contain any lines")
            if chunks:
                chunks[-1]["eof"] = True
            return
        prefix = line[:1]
        if line == "" or prefix in (" ", "+", "-"):
            if not chunks:
                chunks.append(_chunk())
            chunk = chunks[-1]
            old, new = chunk["old"], chunk["new"]
            assert isinstance(old, list) and isinstance(new, list)
            if prefix in ("", " "):
                indices = chunk["indices"]
                assert isinstance(indices, list)
                indices.append((len(old), len(new)))
                old.append(line[1:])
                new.append(line[1:])
            elif prefix == "+":
                new.append(line[1:])
            else:
                old.append(line[1:])
            return
        raise PatchError("unexpected line in an update hunk")

    def finish(self, last: str) -> Tuple[FileOp, ...]:
        if last.strip(WS) == END:
            self._ensure_update_not_empty()
            self.mode = "ended"
        else:
            self.line(last)
        if self.mode != "ended":
            raise PatchError("The last line of the patch must be '*** End Patch'")
        result = []
        for op in self.ops:
            for path in (op.path, op.move_to):
                if path is not None and "\x00" in path:
                    raise PatchError("a patch path contains NUL")
            result.append(
                FileOp(
                    op.kind,
                    op.path,
                    op.move_to,
                    op.content if op.kind == "add" else None,
                    tuple(
                        Chunk(
                            chunk["context"],  # type: ignore[arg-type]
                            tuple(chunk["old"]),  # type: ignore[arg-type]
                            tuple(chunk["new"]),  # type: ignore[arg-type]
                            tuple(chunk["indices"]),  # type: ignore[arg-type]
                            bool(chunk["eof"]),
                        )
                        for chunk in op.chunks
                    ),
                )
            )
        return tuple(result)


def parse_patch(text: str) -> Tuple[FileOp, ...]:
    """Разобрать патч как runtime; пути — как в патче. Ошибка runtime — `PatchError`."""
    if not isinstance(text, str):
        raise PatchError("the patch is not a string")
    lines = _boundaries(_lines(text.strip(WS)))
    parser = _Parser()
    for line in lines[:-1]:
        parser.line(line)
    return parser.finish(lines[-1])


def parse_shell(script: str) -> Optional[Tuple[str, Optional[str]]]:
    """(тело heredoc, каталог cd) для `[cd <dir> &&] apply_patch <<DELIM`; иначе None."""
    first, newline, rest = script.partition("\n")
    match = SHELL_LINE.match(first)
    if match is None or not newline:
        return None
    delim = match.group("delim")
    body: List[str] = []
    lines = rest.split("\n")
    for index, line in enumerate(lines):
        if line == delim:
            if any(other.strip(WS) for other in lines[index + 1 :]):
                return None
            cd_dir = next(
                (
                    match.group(name)
                    for name in ("w", "r", "d")
                    if match.group(name) is not None
                ),
                None,
            )
            return "\n".join(body).rstrip("\n"), cd_dir
        body.append(line)
    return None


def _cwd(payload: Dict[str, object]) -> str:
    cwd = payload.get("cwd")
    return cwd if isinstance(cwd, str) and cwd else os.getcwd()


def _absolute(ops: Sequence[FileOp], base: str) -> Tuple[FileOp, ...]:
    return tuple(
        op._replace(
            path=os.path.join(base, op.path),
            move_to=None if op.move_to is None else os.path.join(base, op.move_to),
        )
        for op in ops
    )


def operations(payload: object) -> Tuple[FileOp, ...]:
    """Операции payload `apply_patch` с абсолютными путями (от `cwd` payload)."""
    if not isinstance(payload, dict):
        raise PatchError("the payload is not a JSON object")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        raise PatchError("the payload has no tool_input object")
    command = tool_input.get("command")
    if not isinstance(command, str):
        raise PatchError("tool_input.command is not a string")
    return _absolute(parse_patch(command), _cwd(payload))


def bash_operations(payload: object) -> Optional[Tuple[FileOp, ...]]:
    """Операции shell-вызова `apply_patch` в Bash; None — команда не shell-форма apply_patch."""
    if not isinstance(payload, dict):
        return None
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    shell = parse_shell(command) if isinstance(command, str) else None
    if shell is None:
        return None
    body, cd_dir = shell
    base = _cwd(payload)
    return _absolute(
        parse_patch(body), base if cd_dir is None else os.path.join(base, cd_dir)
    )


def mentions_patch(command: str) -> bool:
    """Есть ли в команде слово apply_patch и строка `*** Begin Patch`."""
    return bool(PATCH_WORD.search(command)) and any(
        line.strip(WS) == BEGIN for line in command.split("\n")
    )


def header_paths(command: str) -> Tuple[str, ...]:
    """Пути заголовков патча в произвольном тексте: запасной разбор для Bash."""
    paths = []
    for line in command.split("\n"):
        trimmed = line.strip(WS)
        for marker in HEADERS:
            if trimmed.startswith(marker):
                paths.append(trimmed[len(marker) :])
    return tuple(paths)


def targets(ops: Sequence[FileOp]) -> List[str]:
    """Пути, которые трогает патч: путь операции, затем назначение Move."""
    return [path for op in ops for path in (op.path, op.move_to) if path is not None]


def _normalise(text: str) -> str:
    table = {
        **dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"), "-"),
        **dict.fromkeys(map(ord, "\u2018\u2019\u201a\u201b"), "'"),
        **dict.fromkeys(map(ord, "\u201c\u201d\u201e\u201f"), '"'),
        **dict.fromkeys(
            map(
                ord,
                "\xa0\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000",
            ),
            " ",
        ),
    }
    return text.strip(WS).translate(table)


def _seek(
    lines: Sequence[str], pattern: Sequence[str], start: int, eof: bool
) -> Optional[int]:
    """Порт seek_sequence runtime: точно, затем trim_end, trim и нормализация пунктуации."""
    if not pattern:
        return start
    if len(pattern) > len(lines):
        return None
    begin = max(len(lines) - len(pattern), start) if eof else start
    for key in (
        lambda s: s,
        lambda s: s.rstrip(WS),
        lambda s: s.strip(WS),
        _normalise,
    ):
        wanted = [key(item) for item in pattern]
        for index in range(begin, len(lines) - len(pattern) + 1):
            if [key(item) for item in lines[index : index + len(pattern)]] == wanted:
                return index
    return None


def apply_update(text: str, chunks: Sequence[Chunk]) -> Optional[str]:
    """Текст после чанков Update; None — runtime тоже не применил бы патч."""
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    replacements: List[Tuple[int, int, List[str]]] = []
    cursor = 0
    for chunk in chunks:
        if chunk.change_context is not None:
            found = _seek(lines, [chunk.change_context], cursor, False)
            if found is None:
                return None
            cursor = found + 1
        if not chunk.old_lines:
            replacements.append((len(lines), 0, list(chunk.new_lines)))
            continue
        pattern, new = list(chunk.old_lines), list(chunk.new_lines)
        found = _seek(lines, pattern, cursor, chunk.end_of_file)
        if found is None and pattern[-1] == "":
            pattern = pattern[:-1]
            if new and new[-1] == "":
                new = new[:-1]
            found = _seek(lines, pattern, cursor, chunk.end_of_file)
        if found is None:
            return None
        old_start = new_start = 0
        for old_context, new_context in chunk.context_indices:
            if old_context >= len(pattern) or new_context >= len(new):
                break
            if old_start != old_context or new_start != new_context:
                replacements.append(
                    (
                        found + old_start,
                        old_context - old_start,
                        new[new_start:new_context],
                    )
                )
            old_start, new_start = old_context + 1, new_context + 1
        if old_start != len(pattern) or new_start != len(new):
            replacements.append(
                (found + old_start, len(pattern) - old_start, new[new_start:])
            )
        cursor = found + len(pattern)
    for start, length, new_lines in sorted(replacements, key=lambda item: item[0])[
        ::-1
    ]:
        lines[start : start + length] = new_lines
    return "".join(line + "\n" for line in lines)


def detail(error: PatchError) -> str:
    """Причина отказа и remedy без префикса: что не так и какой патч прислать."""
    return (
        f"патч apply_patch не разбирается ({error}), правку нельзя проверить. Пришли патч "
        "в формате *** Begin Patch … *** End Patch с заголовками *** Add File:/"
        "*** Update File:/*** Delete File: и непустыми путями."
    )


def remedy(hook: str, error: PatchError) -> str:
    """Строка stderr guard-а: префикс `[apply-patch-unparseable]`, id hook-а и remedy."""
    return f"[{REASON}] {hook}: {detail(error)}"


def _fanout(command: Sequence[str]) -> int:
    try:
        try:
            payload = json.loads(sys.stdin.read())
        except (ValueError, RecursionError):
            raise PatchError("the payload is not JSON") from None
        paths = targets(operations(payload))
    except PatchError as error:
        hook = os.path.basename(command[-1])
        sys.stderr.write(
            remedy(hook[:-3] if hook.endswith(".sh") else hook, error) + "\n"
        )
        return 2
    env = dict(os.environ)
    env.setdefault("CLAUDE_PROJECT_DIR", os.getcwd())
    for path in paths:
        synthetic = {**payload, "tool_name": "Write", "tool_input": {"file_path": path}}
        done = subprocess.run(
            list(command),
            input=json.dumps(synthetic).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )
        if done.returncode != 0:
            sys.stdout.buffer.write(done.stdout)
            sys.stdout.flush()
            sys.stderr.buffer.write(done.stderr)
            sys.stderr.flush()
            return done.returncode
    return 0


def main(argv: Sequence[str]) -> int:
    """`fanout -- <cmd...>`: проверить каждый путь патча командой guard-а Write/Edit."""
    if len(argv) < 3 or argv[0] != "fanout" or argv[1] != "--":
        sys.stderr.write("usage: apply_patch_payload.py fanout -- <command...>\n")
        return 2
    return _fanout(argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
