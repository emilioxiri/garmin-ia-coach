#!/usr/bin/env bash
# PreToolUse hook: block edits/writes to secret files.
# Reads the tool input JSON from stdin, extracts file_path, blocks if it
# matches one of the protected paths.

set -euo pipefail

input="$(cat)"

# Extract file_path from Edit/Write/MultiEdit/NotebookEdit tool inputs.
path="$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ti = data.get("tool_input", {}) or {}
print(ti.get("file_path") or ti.get("notebook_path") or "")
')"

if [[ -z "$path" ]]; then
    exit 0
fi

case "$path" in
    *"/.env"|*"/.env."*|*".env")
        printf '{"decision":"block","reason":"Edits to .env are blocked. Update it manually."}\n'
        exit 0
        ;;
    *"data/garmin_session.json"|*"/data/garmin_session.json")
        printf '{"decision":"block","reason":"Garmin session token file is protected. Do not edit."}\n'
        exit 0
        ;;
esac

exit 0
