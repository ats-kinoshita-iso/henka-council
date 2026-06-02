#!/usr/bin/env bash
# PostToolUse hook — append a schema-valid audit entry to audit-log.jsonl.
# Reads Claude Code tool-call envelope JSON from stdin.
# Exit 0 = continue.  (PostToolUse hooks do not block — tool already ran.)

set -uo pipefail

# Env-var override for testability; the default path is anchored to the project root
# below (once the envelope cwd is known) to avoid a nested .council/.council/ audit log
# when the tool-call cwd is a subdirectory of the project root (issue #18).
AUDIT_LOG="${AUDIT_LOG_PATH:-}"

# Read envelope from stdin
envelope=$(cat 2>/dev/null || true)
if [[ -z "$envelope" ]]; then
    exit 0  # No envelope — no-op
fi

# JSON value extractor: prefer jq; fall back to python3.
# Uses env vars _JSON_INPUT/_JSON_PATH to pass data safely to python3.
_json_get() {
    local json="$1" dotpath="$2" default="${3:-unknown}"
    local result=""
    if command -v jq &>/dev/null; then
        result=$(printf '%s' "$json" | jq -r "${dotpath} // empty" 2>/dev/null || true)
    elif command -v python3 &>/dev/null; then
        result=$(_JSON_INPUT="$json" _JSON_PATH="$dotpath" python3 -c "
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
" 2>/dev/null || true)
    fi
    if [[ -z "$result" ]]; then
        echo "$default"
    else
        echo "$result"
    fi
}

# Resolve the project root for anchoring the audit-log path.
# Priority: CLAUDE_PROJECT_DIR (set by Claude Code at hook-fire time) ->
# nearest ancestor of the start dir containing a .git marker -> start dir.
# Prevents a nested .council/.council/ audit log when the tool-call cwd is a
# subdirectory of the project root (issue #18). The .git marker is used (not
# .council/.harness) because those can themselves be misrouted ghost dirs.
_council_project_root() {
    local start="${1:-$PWD}" dir parent
    if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
        printf '%s' "${CLAUDE_PROJECT_DIR%/}"
        return 0
    fi
    dir="${start%/}"
    while [[ -n "$dir" && "$dir" != "/" ]]; do
        if [[ -e "$dir/.git" ]]; then
            printf '%s' "$dir"
            return 0
        fi
        parent=$(dirname "$dir")
        [[ "$parent" == "$dir" ]] && break
        dir="$parent"
    done
    printf '%s' "${start%/}"
}

# Check if jq or python3 is available for JSON output building
if ! command -v jq &>/dev/null && ! command -v python3 &>/dev/null; then
    echo "log-tool-call: neither jq nor python3 found — audit logging skipped" >&2
    exit 0
fi

# Extract fields from envelope
tool_name=$(_json_get "$envelope" ".tool_name" "unknown")
session_id=$(_json_get "$envelope" ".session_id" "unknown")
agent_id=$(_json_get "$envelope" ".agent_id" "hook/log-tool-call")
cwd=$(_json_get "$envelope" ".cwd" "")

# Anchor the audit-log path to the project root unless an explicit override was given.
if [[ -z "$AUDIT_LOG" ]]; then
    AUDIT_LOG="$(_council_project_root "$cwd")/.council/audit-log.jsonl"
fi

# Build a privacy-safe input summary
if [[ "$tool_name" == "Bash" ]]; then
    raw_cmd=$(_json_get "$envelope" ".tool_args.command" "")
    # Truncate to 200 chars for privacy
    input_summary="${raw_cmd:0:200}"
elif [[ "$tool_name" == "Write" || "$tool_name" == "Edit" || "$tool_name" == "Read" ]]; then
    raw_path=$(_json_get "$envelope" ".tool_args.file_path" "")
    input_summary="file_path=${raw_path}"
else
    input_summary="${tool_name} call"
fi

# Determine event_type
event_type="tool-call"
# Check for andon signals
lower_env=$(echo "$envelope" | tr '[:upper:]' '[:lower:]')
if echo "$lower_env" | grep -qE '"andon|andon_signal|stop.*signal|alert.*signal' 2>/dev/null; then
    event_type="andon-signal"
fi

# Generate entry_id using session + timestamp nanos (best effort)
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "1970-01-01T00:00:00Z")
nonce=$(date +%s%N 2>/dev/null || date +%s || echo "0")
entry_id="AUD-${nonce}"

# Track andon_pull_count per agent
# Use a temp dir for the state file (safe when .council/ absent)
andon_state_dir="${TMPDIR:-/tmp}/council-andon-counts"
mkdir -p "$andon_state_dir" 2>/dev/null || true
safe_agent_id=$(echo "$agent_id" | tr '/' '_' | tr ':' '_')
andon_count_file="${andon_state_dir}/${safe_agent_id}.count"

andon_count=0
if [[ -f "$andon_count_file" ]]; then
    stored=$(cat "$andon_count_file" 2>/dev/null || echo "0")
    if [[ "$stored" =~ ^[0-9]+$ ]]; then
        andon_count="$stored"
    fi
fi

# Increment if this is an andon event
if [[ "$event_type" == "andon-signal" ]]; then
    andon_count=$(( andon_count + 1 ))
    echo "$andon_count" > "$andon_count_file" 2>/dev/null || true
fi

# Build JSON entry (all required fields: entry_id, timestamp, event_type, agent_id)
if command -v jq &>/dev/null; then
    # -c emits compact (single-line) JSON so the appended audit-log line is a single jsonl record.
    # Multi-line pretty-printed output would break consumers that read the file as one JSON object per line.
    json_entry=$(jq -nc \
        --arg entry_id "$entry_id" \
        --arg timestamp "$timestamp" \
        --arg event_type "$event_type" \
        --arg agent_id "$agent_id" \
        --arg tool_name "$tool_name" \
        --arg tool_input_summary "$input_summary" \
        --argjson andon_pull_count "$andon_count" \
        '{
            entry_id: $entry_id,
            timestamp: $timestamp,
            event_type: $event_type,
            agent_id: $agent_id,
            tool_name: $tool_name,
            tool_input_summary: $tool_input_summary,
            tool_outcome: "success",
            andon_pull_count: $andon_pull_count
        }' 2>/dev/null || true)
else
    # Python3 fallback for JSON output
    json_entry=$(_E_ID="$entry_id" _TS="$timestamp" _ET="$event_type" _AID="$agent_id" \
                 _TN="$tool_name" _TIS="$input_summary" _APC="$andon_count" \
        python3 -c "
import json, os
print(json.dumps({
    'entry_id': os.environ['_E_ID'],
    'timestamp': os.environ['_TS'],
    'event_type': os.environ['_ET'],
    'agent_id': os.environ['_AID'],
    'tool_name': os.environ['_TN'],
    'tool_input_summary': os.environ['_TIS'],
    'tool_outcome': 'success',
    'andon_pull_count': int(os.environ['_APC']),
}))
" 2>/dev/null || true)
fi

if [[ -z "$json_entry" ]]; then
    echo "log-tool-call: failed to build JSON entry — skipping" >&2
    exit 0
fi

# Ensure parent directory exists
audit_dir=$(dirname "$AUDIT_LOG")
mkdir -p "$audit_dir" 2>/dev/null || true

# Append entry
echo "$json_entry" >> "$AUDIT_LOG" 2>/dev/null || {
    echo "log-tool-call: failed to append to ${AUDIT_LOG} — skipping" >&2
    exit 0
}

exit 0
