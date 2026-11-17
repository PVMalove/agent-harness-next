#!/bin/bash
# PreToolUse(Bash): blocks unconditionally destructive git commands, adapted from the upstream
# mattpocock/skills "git-guardrails-claude-code" skill (skills/misc/, not part of the vendored
# mattpocock-suite capability). Deliberately does NOT block `git push` outright, unlike upstream —
# docs/agents/git-workflow.md requires pushing issue branches; push-to-base/integration is already
# covered by block-direct-master.sh.
# Verdict envelope (hook-envelope.sh, then hook_response.py): reruns this script, answers with the
# JSON verdict and the exit code of the hook policy. Without Python or the helpers the script below
# decides alone.
[ -f "$(dirname "$0")/hook-envelope.sh" ] && . "$(dirname "$0")/hook-envelope.sh" block-dangerous-git
INPUT=$(cat)
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "Невозможно проверить опасные Git-команды: Python 3.9+ не найден." >&2
  exit 2
fi

# The command is parsed as shell, not grepped as raw text: a destructive command is blocked only
# where the shell would run `git` (a command word, also inside $(...), backticks, `sh -c`, `eval`
# and heredoc bodies fed to a shell). The same text inside a quoted string, an argument of another
# interpreter (`python -c ...`) or a heredoc body fed to a non-shell is data and passes. Text the
# parser cannot read falls back to the raw match, so an unreadable command still fails closed.
read -r -d '' CHECK <<'PY_EOF'
import json
import re
import sys

# Raw-text fallback for a command the parser cannot read: any words may stand between `git`
# and the subcommand (global options) and between the subcommand and its option.
RAW_PATTERNS = {
    "git reset --hard": r"\bgit\b.*\breset\b.*\s--hard\b",
    "git clean -f": r"\bgit\b.*\bclean\b.*\s(-[a-zA-Z]*f|--force\b)",
    "git branch -D": r"\bgit\b.*\bbranch\b.*\s(-[a-zA-Z]*D|--delete\b.*\s(--force\b|-[a-zA-Z]*f))",
    "git checkout .": r"\bgit\b.*\bcheckout\b.*\s\.(\s|$)",
    "git restore .": r"\bgit\b.*\brestore\b.*\s\.(\s|$)",
}
# Global options of `git` that take the next word as their value (`git --help`).
VALUE_OPTIONS = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env",
    "--super-prefix", "--attr-source", "--list-cmds",
}
SHELLS = ("sh", "bash", "zsh", "dash", "ksh")
METACHARACTERS = " \t\n|&;()<>"


class Blocked(Exception):
    pass


class Unparsed(Exception):
    pass


def basename(word):
    return word.rsplit("/", 1)[-1]


def short_flags(arguments):
    """Letters of the short option clusters (`-fd` gives f and d) before a `--` separator."""
    letters = set()
    for argument in arguments:
        if argument == "--":
            break
        if re.fullmatch(r"-[a-zA-Z]+", argument):
            letters.update(argument[1:])
    return letters


def destructive(subcommand, arguments):
    """The pattern a git subcommand with these arguments matches, or None."""
    flags = short_flags(arguments)
    options = set(arguments)
    if subcommand == "reset" and "--hard" in options:
        return "git reset --hard"
    if subcommand == "clean" and ("f" in flags or "--force" in options):
        return "git clean -f"
    if subcommand == "branch" and (
        "D" in flags
        or ("d" in flags or "--delete" in options) and ("f" in flags or "--force" in options)
    ):
        return "git branch -D"
    if subcommand == "checkout" and "." in options:
        return "git checkout ."
    if subcommand == "restore" and "." in options and not (
        options & {"--staged", "-S"} and not options & {"--worktree", "-W"}
    ):
        return "git restore ."
    return None


def check_git(arguments):
    """Skip the global options of `git` (`-C dir`, `-c k=v`, `--no-pager` ...), check the rest."""
    index = 0
    while index < len(arguments) and arguments[index].startswith("-"):
        index += 2 if arguments[index] in VALUE_OPTIONS else 1
    if index < len(arguments):
        pattern = destructive(arguments[index], arguments[index + 1 :])
        if pattern:
            raise Blocked(pattern)


def check_words(words):
    for index, word in enumerate(words):
        name = basename(word)
        if name == "git":
            check_git(words[index + 1 :])
        elif name in SHELLS:
            for option, script in zip(words[index + 1 :], words[index + 2 :]):
                if re.fullmatch(r"-[a-z]*c[a-z]*", option):
                    scan(script, 0, None)
        elif name == "eval":
            scan(" ".join(words[index + 1 :]), 0, None)


def scan_expansions(text):
    """Run only the $(...) and `...` parts of text that the shell would expand."""
    index = 0
    while index < len(text):
        if text[index] == "\\":
            index += 2
        elif text.startswith("$(", index):
            index = scan(text, index + 2, ")")
        elif text[index] == "`":
            index = scan(text, index + 1, "`")
        else:
            index += 1


def read_double_quoted(text, index):
    """Return the index after the closing quote; expansions inside are scanned."""
    while index < len(text):
        char = text[index]
        if char == '"':
            return index + 1
        if char == "\\":
            index += 2
        elif text.startswith("$(", index):
            index = scan(text, index + 2, ")")
        elif char == "`":
            index = scan(text, index + 1, "`")
        else:
            index += 1
    raise Unparsed


def read_delimiter(text, index):
    word, quoted = [], False
    while index < len(text) and text[index] not in METACHARACTERS:
        char = text[index]
        if char in ("'", '"'):
            end = text.find(char, index + 1)
            if end < 0:
                raise Unparsed
            word.append(text[index + 1 : end])
            index, quoted = end + 1, True
        elif char == "\\":
            word.append(text[index + 1 : index + 2])
            index, quoted = index + 2, True
        else:
            word.append(char)
            index += 1
    return "".join(word), quoted, index


def read_heredoc_body(text, index, delimiter, strip_tabs):
    lines = []
    while index < len(text):
        end = text.find("\n", index)
        end = len(text) if end < 0 else end
        line = text[index:end]
        index = end + 1
        if (line.lstrip("\t") if strip_tabs else line) == delimiter:
            break
        lines.append(line)
    return "\n".join(lines), index


def feeds_shell(line):
    return any(basename(word) in SHELLS + ("eval",) for word in line)


def scan(text, index, closer):
    """Check the shell text from index; stop after `closer` and return the next index."""
    words, line, pending = [], [], []
    current = None
    depth = 0
    piped = False

    def scan_piped():
        # Words piped, here-stringed or process-substituted into a shell may be its script.
        if piped and feeds_shell(line):
            for word in line:
                scan(word, 0, None)

    def end_word():
        nonlocal current
        if current is not None:
            words.append("".join(current))
            line.append(words[-1])
            current = None

    def end_command():
        end_word()
        check_words(words)
        words.clear()

    while index < len(text):
        char = text[index]
        if char == "\\":
            if text[index + 1 : index + 2] != "\n":
                current = (current or []) + [text[index + 1 : index + 2]]
            index += 2
        elif char == "'":
            end = text.find("'", index + 1)
            if end < 0:
                raise Unparsed
            current = (current or []) + [text[index + 1 : end]]
            index = end + 1
        elif char == '"':
            end = read_double_quoted(text, index + 1)
            current = (current or []) + [text[index + 1 : end - 1]]
            index = end
        elif text.startswith("$(", index):
            current = current or []
            index = scan(text, index + 2, ")")
        elif text.startswith("$'", index):
            end = index + 2
            while end < len(text) and text[end] != "'":
                end += 2 if text[end] == "\\" else 1
            if end >= len(text):
                raise Unparsed
            current = (current or []) + [text[index + 2 : end]]
            index = end + 1
        elif char == "`":
            if closer == "`":
                end_command()
                scan_piped()
                return index + 1
            current = current or []
            index = scan(text, index + 1, "`")
        elif char == "#" and current is None:
            end = text.find("\n", index)
            index = len(text) if end < 0 else end
        elif char in " \t":
            end_word()
            index += 1
        elif char == "\n":
            end_command()
            scan_piped()
            index += 1
            for delimiter, strip_tabs, quoted in pending:
                body, index = read_heredoc_body(text, index, delimiter, strip_tabs)
                if feeds_shell(line):
                    scan(body, 0, None)
                elif not quoted:
                    scan_expansions(body)
            pending, line, piped = [], [], False
        elif text.startswith("<<<", index):
            end_word()
            piped = True
            index += 3
        elif text.startswith("<<", index):
            end_word()
            start = index + 2
            strip_tabs = text.startswith("-", start)
            start += strip_tabs
            while text[start : start + 1] in (" ", "\t"):
                start += 1
            delimiter, quoted, index = read_delimiter(text, start)
            if delimiter:
                pending.append((delimiter, strip_tabs, quoted))
        elif char in "<>":
            end_word()
            piped = piped or text.startswith("<(", index)
            index += 1
        elif char in "|&;":
            end_command()
            if text.startswith(("||", "&&"), index):
                index += 2
            else:
                piped = piped or char == "|"
                index += 1
        elif char == "(":
            end_command()
            depth += 1
            index += 1
        elif char == ")":
            end_command()
            index += 1
            if depth:
                depth -= 1
            elif closer == ")":
                scan_piped()
                return index
        else:
            current = (current or []) + [char]
            index += 1
    if closer:
        raise Unparsed
    end_command()
    scan_piped()
    return index


try:
    command = json.load(open(0, encoding="utf-8", errors="ignore")).get("tool_input", {}).get("command", "")
except Exception:
    command = ""
if isinstance(command, str) and command:
    try:
        scan(command, 0, None)
    except Blocked as blocked:
        print(blocked.args[0])
    except Exception:
        for pattern, raw in RAW_PATTERNS.items():
            if re.search(raw, command):
                print(pattern)
                break
PY_EOF

PATTERN="$(printf '%s' "$INPUT" | "$PY" -c "$CHECK")"
if [ -n "$PATTERN" ]; then
  REMEDY="такие операции требуют явного запроса пользователя."
  if [ "$PATTERN" = "git branch -D" ]; then
    REMEDY="локальную ветку слитого тикета удаляет 'harness branch-delete <repo> <branch>': команда сама проверяет, что ветка соответствует branch_pattern, не извлечена и сохранена на origin или в слитом PR/MR."
  fi
  echo "Заблокировано: команда матчит деструктивный паттерн '$PATTERN' — $REMEDY" >&2
  exit 2
fi

exit 0
