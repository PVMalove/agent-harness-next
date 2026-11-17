#!/bin/bash
# Fail-closed activation check for the optional test-author agent.
#
# The script is invoked by the developer before spawning the in-session Claude Code subagent. It
# prints exactly one sanitized JSON line and always exits 0: a disabled result preserves the normal
# developer route and does not create orchestration or ledger state.
#
# Usage: test-author-preflight.sh [--worktree <path>] [--brief <approved brief> | --planned]
# --worktree must be this exact checkout; the project root comes from Git, and CLAUDE_PROJECT_DIR is
# optional but must name the same root when set. --brief selects the approved developer executor;
# --planned diagnoses the orchestration developer plan (Health only). With neither context flag,
# the explicit short-route project.test_author profile is required. No executor is implied.

set -u

disabled() {
  printf '{"status":"disabled","reason":"%s"}\n' "$1"
  exit 0
}

PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || disabled runner_unavailable

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd -P)"
[ -n "$REPO" ] || disabled project_untrusted

WORKTREE="$REPO"
SEEN_WORKTREE=0
CONTEXT_ARGS=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --worktree)
      [ "$SEEN_WORKTREE" -eq 0 ] && [ "$#" -ge 2 ] && [ -n "$2" ] || disabled checkout_mismatch
      WORKTREE="$(cd "$2" 2>/dev/null && pwd -P || true)"
      [ -n "$WORKTREE" ] && [ "$WORKTREE" = "$REPO" ] || disabled checkout_mismatch
      SEEN_WORKTREE=1
      shift 2
      ;;
    --brief)
      [ "${#CONTEXT_ARGS[@]}" -eq 0 ] && [ "$#" -ge 2 ] && [ -n "$2" ] || disabled checkout_mismatch
      CONTEXT_ARGS=(--brief "$2")
      shift 2
      ;;
    --planned)
      [ "${#CONTEXT_ARGS[@]}" -eq 0 ] || disabled checkout_mismatch
      CONTEXT_ARGS=(--planned)
      shift
      ;;
    *) disabled checkout_mismatch ;;
  esac
done

# Resolve before touching an adapter's identity or trust store. A configured unsupported runtime
# must never be turned into a Claude session. The installed module is portable stdlib code.
SELECTOR="$REPO/.harness/health/test_author.py"
[ -f "$SELECTOR" ] && [ ! -L "$SELECTOR" ] || disabled selector_unavailable
SELECTION="$("$PY" -I -B "$SELECTOR" check --repo "$REPO" "${CONTEXT_ARGS[@]}" 2>/dev/null || true)"
SELECTION_REASON="$(printf '%s' "$SELECTION" | "$PY" -c '
import json, sys
try:
    value = json.load(sys.stdin)
except (ValueError, TypeError, RecursionError):
    value = None
allowed = {"test_paths_missing", "test_runner_missing", "test_author_missing", "test_author_config_invalid", "runtime_unsupported", "orchestration_unavailable"}
if value == {"status": "ok"}:
    print("ok")
elif isinstance(value, dict) and value.get("status") == "disabled" and value.get("reason") in allowed:
    print(value["reason"])
else:
    print("selector_unavailable")
' 2>/dev/null || true)"
[ "$SELECTION_REASON" = "ok" ] || disabled "${SELECTION_REASON:-selector_unavailable}"

# Git is the single source of the project root: the checkout that holds this hook must be its own
# Git work tree (the main checkout or a linked worktree) in Claude Code and Codex alike.
GIT_ROOT="$(git -C "$REPO" rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$GIT_ROOT" ] || disabled project_untrusted
GIT_ROOT="$(cd "$GIT_ROOT" 2>/dev/null && pwd -P || true)"
[ "$GIT_ROOT" = "$REPO" ] || disabled project_untrusted
[ "$(git -C "$REPO" rev-parse --is-inside-work-tree 2>/dev/null || true)" = "true" ] || disabled project_untrusted

# Claude Code does not always pass CLAUDE_PROJECT_DIR to Bash, so its absence is not an error.
# When it is passed, the scoped guard of a native Agent resolves this same variable, so another
# path would bind the author to another checkout.
CLAUDE_REPO="${CLAUDE_PROJECT_DIR:-}"
if [ -n "$CLAUDE_REPO" ]; then
  CLAUDE_REPO="$(cd "$CLAUDE_REPO" 2>/dev/null && pwd -P || true)"
  [ "$CLAUDE_REPO" = "$REPO" ] || disabled project_dir_mismatch
fi
[ "${CLAUDE_CODE_SIMPLE:-0}" = "1" ] && disabled claude_code_unsupported
[ "${CLAUDE_CODE_SAFE_MODE:-0}" = "1" ] && disabled claude_code_unsupported

# Claude Code keeps workspace trust decisions in ~/.claude.json (or $CLAUDE_CONFIG_DIR/.claude.json).
# The native --print mode skips the trust dialog, so the preflight must verify the decision itself
# before enabling an agent whose safety depends on a frontmatter hook.  An entry for this exact
# checkout counts, and so does an entry for the repository's main checkout when that checkout
# lists this one among its linked worktrees: a worktree of a trusted repository is trusted.  Trust
# given only to a parent directory does not count (ADR 0033).
TRUSTED_PROJECT="$("$PY" -c '
import json
import os
import subprocess
import sys
from pathlib import Path


def git(checkout, *arguments):
    return subprocess.run(
        ["git", "-C", str(checkout), *arguments],
        capture_output=True, text=True, timeout=30, check=True,
    ).stdout


def accepted(projects, path):
    entry = projects.get(str(path))
    return isinstance(entry, dict) and entry.get("hasTrustDialogAccepted") is True


def listed_worktree(main, project):
    return any(
        Path(line[len("worktree "):]).resolve() == project
        for line in git(main, "worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    )


try:
    project = Path(sys.argv[1]).resolve()
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    state_path = (
        Path(config_dir).expanduser() / ".claude.json"
        if config_dir
        else Path.home() / ".claude.json"
    )
    projects = json.loads(state_path.read_text(encoding="utf-8")).get("projects", {})
    trusted = accepted(projects, project)
    if not trusted:
        common = (project / git(project, "rev-parse", "--git-common-dir").strip()).resolve()
        main = common.parent
        trusted = (
            common.name == ".git"
            and main != project
            and accepted(projects, main)
            and Path(git(main, "rev-parse", "--show-toplevel").strip()).resolve() == main
            and listed_worktree(main, project)
        )
except (AttributeError, OSError, TypeError, ValueError, RecursionError, subprocess.SubprocessError):
    trusted = False
print("ok" if trusted else "disabled")
' "$REPO" 2>/dev/null || true)"
[ "$TRUSTED_PROJECT" = "ok" ] || disabled project_untrusted

AGENT="$REPO/.claude/agents/test-author.md"
[ -f "$AGENT" ] && [ ! -L "$AGENT" ] || disabled agent_missing
GUARD="$REPO/.claude/hooks/test-author-guard.py"
RUNNER="$REPO/.claude/hooks/run-test.sh"
[ -f "$GUARD" ] && [ -x "$GUARD" ] || disabled guard_hook_unavailable
[ -f "$RUNNER" ] && [ -x "$RUNNER" ] || disabled runner_unavailable

# Print "ok" for {"status":"ok"}, the reason of a {"status":<$1>} answer when it is one of the
# remaining arguments, and "invalid" for anything else read from stdin.
answer_reason() {
  "$PY" -c '
import json
import sys

wanted, allowed = sys.argv[1], set(sys.argv[2:])
try:
    value = json.load(sys.stdin)
except (json.JSONDecodeError, TypeError, RecursionError):
    value = None
if value == {"status": "ok"}:
    print("ok")
elif (
    isinstance(value, dict)
    and value.get("status") == wanted
    and value.get("reason") in allowed
):
    print(value["reason"])
else:
    print("invalid")
' "$@" 2>/dev/null || echo invalid
}

CONFIG="$("$PY" "$GUARD" --validate-config 2>/dev/null || true)"
CONFIG_REASON="$(printf '%s' "$CONFIG" | answer_reason disabled \
  agent_missing scoped_hook_unsupported test_paths_missing test_runner_missing \
  config_invalid test_author_config_invalid write_zone_rejected)"
case "$CONFIG_REASON" in
  ok) ;;
  invalid) disabled guard_hook_unavailable ;;
  *) disabled "$CONFIG_REASON" ;;
esac

PROBE="$("$RUNNER" --probe 2>/dev/null || true)"
PROBE_REASON="$(printf '%s' "$PROBE" | answer_reason unavailable \
  isolation_unavailable runner_unavailable config_invalid write_zone_rejected \
  test_paths_missing test_runner_missing)"
case "$PROBE_REASON" in
  ok) ;;
  invalid) disabled isolation_unavailable ;;
  *) disabled "$PROBE_REASON" ;;
esac

printf '{"status":"ok"}\n'
