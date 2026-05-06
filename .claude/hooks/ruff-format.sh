#!/usr/bin/env bash
# PostToolUse hook: format + lint-fix Python files after Edit/Write.
# Silent on success, prints ruff output on failure but does not block.

set -uo pipefail

input="$(cat)"

path="$(printf '%s' "$input" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ti = data.get("tool_input", {}) or {}
print(ti.get("file_path") or "")
')"

# Only operate on Python files inside the repo.
if [[ -z "$path" || "$path" != *.py ]]; then
    exit 0
fi
if [[ ! -f "$path" ]]; then
    exit 0
fi

if command -v ruff >/dev/null 2>&1; then
    ruff format "$path" >/dev/null 2>&1 || true
    ruff check --fix "$path" >/dev/null 2>&1 || true
fi

exit 0
