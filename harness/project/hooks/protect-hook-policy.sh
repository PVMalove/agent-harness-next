#!/bin/bash
# PreToolUse(Bash|Write|Edit|MultiEdit|NotebookEdit): critical guard of the hook policy. It blocks, in
# every profile, an agent change of hook_policy in .harness/project.json, of .claude/settings*.json,
# .codex/hooks.json and the hook directories, and asks a person before any shell write to
# .harness/project.json (exit code 3, turned into an "ask" verdict by hook_response.py).
# protect_hook_policy.py decides every call; only its exit 0 with the word `allow` lets the action
# run, so a missing interpreter, any other status or a partial copy of the helper blocks (fail closed).
# Verdict envelope (hook-envelope.sh, then hook_response.py): reruns this script, answers with the
# JSON verdict and the exit code of the hook policy. Without Python or the helpers the script below
# decides alone.
[ -f "$(dirname "$0")/hook-envelope.sh" ] && . "$(dirname "$0")/hook-envelope.sh" protect-hook-policy
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "[hook-policy-protected] protect-hook-policy: Python 3 не найден, действие нельзя проверить." >&2
  exit 2
fi

VERDICT="$("$PY" "$SCRIPT_DIR/protect_hook_policy.py")"
CODE=$?
if [ "$CODE" -eq 0 ] && [ "$VERDICT" = "allow" ]; then
  exit 0
fi
if [ "$CODE" -eq 3 ]; then
  # A refusal that a human may lift by hand: only the envelope turns code 3 into "ask".
  # Run alone (no hook_response.py), the script blocks.
  [ -n "${HARNESS_HOOK_ENVELOPE:-}" ] && exit 3
  exit 2
fi
if [ "$CODE" -ne 2 ]; then
  echo "[hook-policy-protected] protect-hook-policy: protect_hook_policy.py не дал решения (код $CODE) — действие заблокировано." >&2
fi
exit 2
