#!/bin/bash
# PreToolUse(Bash|Write|Edit|MultiEdit|NotebookEdit): critical guard of the hook policy. It blocks, in
# every profile, an agent change of hook_policy in .harness/project.json, of .claude/settings*.json,
# .codex/hooks.json and the hook directories, and asks a person before any shell write to
# .harness/project.json (exit code 3, turned into an "ask" verdict by hook_response.py).
# protect_hook_policy.py decides every call; only its exit 0 with the word `allow` lets the action
# run, so a missing interpreter, any other status or a partial copy of the helper blocks (fail closed).
# Verdict envelope (hook_response.py): reruns this script, answers with the JSON verdict and the
# exit code of the hook policy. Without Python or the helper the script below decides alone.
if [ -z "${HARNESS_HOOK_ENVELOPE:-}" ]; then
  ENVELOPE_DIR="$(cd "$(dirname "$0")" && pwd)"
  ENVELOPE_PY="$(command -v python3 || command -v python)"
  if [ -n "$ENVELOPE_PY" ] && [ -f "$ENVELOPE_DIR/hook_response.py" ]; then
    exec "$ENVELOPE_PY" "$ENVELOPE_DIR/hook_response.py" run protect-hook-policy "${BASH:-bash}" "$0"
  fi
fi
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
