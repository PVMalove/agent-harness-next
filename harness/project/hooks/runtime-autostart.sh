#!/bin/bash
# Advisory, Claude Code only (ADR 0031). PreToolUse(Bash): before a command of
# .harness/orchestration/coordinator.py, `harness-runtime ensure` attaches this session (or
# subagent) to the runtime of the main checkout and starts an owned `harness-runtime serve` when none
# answers. Stop and SubagentStop: `harness-runtime release` removes the owner; the runtime stops
# itself once no owner is left and its store is idle. The hook never blocks and never continues the
# turn; a failure is a warning `[runtime-autostart-failed] <reason>` with a systemMessage.
# runtime_autostart.py only parses the payload, paths and dep-info; this script runs git and the
# Rust binary. Windows (MINGW/MSYS/CYGWIN) and the agent sandbox keep the manual start.
# Verdict envelope (hook_response.py): applies the hook profile and answers with the JSON verdict.
if [ -z "${HARNESS_HOOK_ENVELOPE:-}" ]; then
  ENVELOPE_DIR="$(cd "$(dirname "$0")" && pwd)"
  ENVELOPE_PY="$(command -v python3 || command -v python)"
  if [ -n "$ENVELOPE_PY" ] && [ -f "$ENVELOPE_DIR/hook_response.py" ]; then
    exec "$ENVELOPE_PY" "$ENVELOPE_DIR/hook_response.py" run runtime-autostart "${BASH:-bash}" "$0"
  fi
fi
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python3 || command -v python)"
[ -n "$PY" ] || exit 0
HELPER="$HOOK_DIR/runtime_autostart.py"

case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) exit 0 ;;
esac

PARSED="$("$PY" "$HELPER" parse)" || exit 0
[ -n "$PARSED" ] || exit 0
{ IFS= read -r EVENT; IFS= read -r SESSION; IFS= read -r AGENT; IFS= read -r CHECKOUT; } <<EOF
$PARSED
EOF

if [ "$EVENT" = "PreToolUse" ] && [ "${SANDBOX_RUNTIME:-}" = "1" ]; then
  exec "$PY" "$HELPER" report sandbox
fi

COMMON="$(git -C "$CHECKOUT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
if [ -z "$COMMON" ]; then
  [ "$EVENT" = "PreToolUse" ] && exec "$PY" "$HELPER" report git "$CHECKOUT"
  exit 0
fi
MAIN="$(dirname "$COMMON")"

FOUND="$("$PY" "$HELPER" binary "$MAIN")" || exit 0
{ IFS= read -r KIND; IFS= read -r BIN; } <<EOF
$FOUND
EOF

AGENT_ARGS=()
[ -n "$AGENT" ] && AGENT_ARGS=(--agent "$AGENT")

# The variables Claude Code adds only for hooks: serve and its executions get the environment of
# the application itself. CLAUDE_PID becomes --owner-pid.
SCRUB=(-u CLAUDECODE -u CLAUDE_CODE_SESSION_ID -u CLAUDE_CODE_CHILD_SESSION
  -u CLAUDE_CODE_SESSION_ATTENDED -u CLAUDE_PID -u AI_AGENT -u CLAUDE_EFFORT -u TRACEPARENT
  -u CLAUDE_PROJECT_DIR -u CLAUDE_PLUGIN_ROOT -u CLAUDE_PLUGIN_DATA -u CLAUDE_ENV_FILE
  -u COLUMNS -u LINES -u HARNESS_HOOK_ENVELOPE)

if [ "$EVENT" != "PreToolUse" ]; then
  case "$KIND" in
    source|stale|path) env "${SCRUB[@]}" "$BIN" release --repo "$MAIN" --session "$SESSION" \
      "${AGENT_ARGS[@]}" >/dev/null 2>&1 ;;
  esac
  exit 0
fi

case "$KIND" in
  unbuilt) exec "$PY" "$HELPER" report unbuilt "$BIN" ;;
  missing) exec "$PY" "$HELPER" report missing ;;
esac

OWNER_ARGS=()
case "${CLAUDE_PID:-}" in
  ''|*[!0-9]*) ;;
  *) OWNER_ARGS=(--owner-pid "$CLAUDE_PID") ;;
esac
ATTACH_ONLY=()
[ "$KIND" = "stale" ] && ATTACH_ONLY=(--attach-only)

ANSWER="$(env "${SCRUB[@]}" "$BIN" ensure --repo "$MAIN" --session "$SESSION" "${AGENT_ARGS[@]}" \
  "${OWNER_ARGS[@]}" "${ATTACH_ONLY[@]}" 2>/dev/null)"
CODE=$?
if [ "$KIND" = "stale" ] && [ "$CODE" = "3" ]; then
  exec "$PY" "$HELPER" report stale "$BIN"
fi
exec "$PY" "$HELPER" report ensure "$CODE" "$ANSWER"
