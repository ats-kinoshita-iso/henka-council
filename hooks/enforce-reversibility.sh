#!/usr/bin/env bash
# PreToolUse hook — block irreversible Bash commands when effective autonomy level < 5.
# Reads Claude Code tool-call envelope JSON from stdin.
# Exit 0 = allow.  Non-zero exit = block.

set -uo pipefail

# Env-var override for testability
AUTONOMY_FILE="${EFFECTIVE_AUTONOMY_PATH:-.council/state/effective-autonomy.json}"

# Patterns that indicate irreversible operations
IRREVERSIBLE_PATTERNS=(
    "git push"
    "git push --force"
    "git reset --hard"
    "git rebase"
    "git merge"
    "rm -rf"
    "git filter-branch"
)

# Read envelope from stdin
envelope=$(cat 2>/dev/null || true)
if [[ -z "$envelope" ]]; then
    exit 0  # No envelope — fail open
fi

# JSON value extractor: prefer jq; fall back to python3; fail open if neither.
# Uses env var _JSON_INPUT/_JSON_PATH to pass data safely to python3.
_json_get() {
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
        echo "enforce-reversibility: neither jq nor python3 found — hook skipped (fail open)" >&2
        exit 0
    fi
}

tool_name=$(_json_get "$envelope" ".tool_name")

# Only inspect Bash tool calls
if [[ "$tool_name" != "Bash" ]]; then
    exit 0
fi

# Read effective autonomy level; default to 4 if file absent
level=4
if [[ -f "$AUTONOMY_FILE" ]]; then
    if command -v jq &>/dev/null; then
        parsed=$(jq -r '.level // empty' "$AUTONOMY_FILE" 2>/dev/null || true)
    elif command -v python3 &>/dev/null; then
        parsed=$(_JSON_FILE="$AUTONOMY_FILE" python3 -c "
import json, os
try:
    d = json.load(open(os.environ['_JSON_FILE'], encoding='utf-8'))
    print(d.get('level', ''))
except Exception:
    print('')
" 2>/dev/null || true)
    else
        parsed=""
    fi
    if [[ -n "$parsed" ]] && [[ "$parsed" =~ ^[0-9]+$ ]]; then
        level="$parsed"
    else
        echo "enforce-reversibility: could not parse level from ${AUTONOMY_FILE} — defaulting to 4 (fail open)" >&2
    fi
else
    echo "enforce-reversibility: ${AUTONOMY_FILE} not found — defaulting to level 4 (fail open)" >&2
fi

# If level >= 5, all commands allowed
if (( level >= 5 )); then
    exit 0
fi

# Extract the command
command_str=$(_json_get "$envelope" ".tool_args.command")

if [[ -z "$command_str" ]]; then
    exit 0
fi

# Check for irreversible patterns
for pattern in "${IRREVERSIBLE_PATTERNS[@]}"; do
    if echo "$command_str" | grep -qF "$pattern" 2>/dev/null; then
        echo "BLOCKED: Irreversible command '${pattern}' detected in Bash tool call." >&2
        echo "  Effective autonomy level is ${level} (< 5). Irreversible operations require level 5." >&2
        echo "  Command: ${command_str}" >&2
        exit 1
    fi
done

exit 0
