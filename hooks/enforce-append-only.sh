#!/usr/bin/env bash
# PreToolUse hook — block Write/Edit on append-only council logs.
# Reads Claude Code tool-call envelope JSON from stdin.
# Exit 0 = allow.  Non-zero exit = block (stderr message surfaced to user).

set -uo pipefail

PROTECTED_FILES=(
    ".council/henka-register.jsonl"
    ".council/decision-log.jsonl"
    ".council/audit-log.jsonl"
)

# Read envelope from stdin
envelope=$(cat 2>/dev/null || true)
if [[ -z "$envelope" ]]; then
    exit 0  # No envelope — fail open
fi

# JSON value extractor: prefer jq; fall back to python3; fail open if neither.
# Uses env var _JSON_INPUT to pass data safely to python3 (avoids pipe+heredoc conflict).
_json_get() {
    # $1 = json string, $2 = dotpath (e.g. ".tool_name" or ".tool_args.file_path")
    local json="$1" dotpath="$2"
    if command -v jq &>/dev/null; then
        printf '%s' "$json" | jq -r "${dotpath} // empty" 2>/dev/null || true
    elif command -v python3 &>/dev/null; then
        _JSON_INPUT="$json" _JSON_PATH="$dotpath" python3 -c "
import json, sys, os
try:
    d = json.loads(os.environ['_JSON_INPUT'])
    keys = os.environ['_JSON_PATH'].lstrip('.').split('.')
    v = d
    for k in keys:
        v = v.get(k, '') if isinstance(v, dict) else ''
    print('' if v is None else str(v))
except Exception:
    print('')
" 2>/dev/null || true
    else
        echo "enforce-append-only: neither jq nor python3 found — hook skipped (fail open)" >&2
        exit 0
    fi
}

tool_name=$(_json_get "$envelope" ".tool_name")
file_path=$(_json_get "$envelope" ".tool_args.file_path")

# Only inspect Write and Edit tool calls
if [[ "$tool_name" != "Write" && "$tool_name" != "Edit" ]]; then
    exit 0
fi

# Resolve the write target against the tool-call cwd before matching. A path expressed
# relative to a shifted cwd (e.g. cwd=<root>/.council, file_path=henka-register.jsonl)
# must still resolve to <root>/.council/henka-register.jsonl. Without this, a bare or
# ./-relative path slips past the protected-file check — the append-only bypass (issue #18).
cwd=$(_json_get "$envelope" ".cwd")
norm_path="${file_path//\\//}"   # backslashes -> forward slashes (Windows envelopes)
norm_path="${norm_path#./}"      # strip a single leading ./
cwd="${cwd//\\//}"

case "$norm_path" in
    /*|[A-Za-z]:/*) abs_path="$norm_path" ;;                       # already absolute (POSIX or Windows drive)
    *) if [[ -n "$cwd" ]]; then abs_path="${cwd%/}/${norm_path}"; else abs_path="$norm_path"; fi ;;
esac

for protected in "${PROTECTED_FILES[@]}"; do
    # Match the cwd-resolved absolute path (catches relative-to-.council evasions) and the
    # raw normalized path (catches the plain ".council/<log>" form when no cwd is present).
    if [[ "$abs_path" == "$protected" || "$abs_path" == *"/$protected" || "$norm_path" == "$protected" ]]; then
        echo "BLOCKED: Direct ${tool_name} on append-only log '${file_path}' is forbidden." >&2
        echo "  Approved write paths: scripts/append-henka.py, scripts/append-decision.py" >&2
        exit 1
    fi
done

exit 0
