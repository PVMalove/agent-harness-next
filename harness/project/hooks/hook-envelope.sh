#!/bin/bash
# Verdict envelope of the managed event hooks. Not an event hook: no runtime file wires it. A hook
# script sources it as its first command, with its own hook_id as the only argument:
#   [ -f "$(dirname "$0")/hook-envelope.sh" ] && . "$(dirname "$0")/hook-envelope.sh" <hook_id>
# hook_response.py reruns the calling script ($0) with the same stdin and answers with the JSON
# verdict and the exit code of the hook policy; exec replaces the calling shell, so the script
# below the source line never runs here. Inside that rerun (HARNESS_HOOK_ENVELOPE is set), without
# Python, without hook_response.py or without this file the calling script decides alone.
if [ -z "${HARNESS_HOOK_ENVELOPE:-}" ]; then
  ENVELOPE_DIR="$(cd "$(dirname "$0")" && pwd)"
  ENVELOPE_PY="$(command -v python3 || command -v python)"
  if [ -n "$ENVELOPE_PY" ] && [ -f "$ENVELOPE_DIR/hook_response.py" ]; then
    exec "$ENVELOPE_PY" "$ENVELOPE_DIR/hook_response.py" run "$1" "${BASH:-bash}" "$0"
  fi
fi
