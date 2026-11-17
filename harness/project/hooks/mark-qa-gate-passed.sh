#!/bin/bash
# PostToolUse(Bash): fallback marker when the last configured QA command succeeds.
# Verdict envelope (hook-envelope.sh, then hook_response.py): reruns this script, answers with the
# JSON verdict and the exit code of the hook policy. Without Python or the helpers the script below
# decides alone.
[ -f "$(dirname "$0")/hook-envelope.sh" ] && . "$(dirname "$0")/hook-envelope.sh" mark-qa-gate-passed
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python "$SCRIPT_DIR/qa-gate-state.py" mark
