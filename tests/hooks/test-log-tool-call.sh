#!/usr/bin/env bash
# Fixture test for hooks/log-tool-call.sh
# Tests that a valid audit entry is appended and validates against the schema.
# Exit 0 = all tests passed.

set -uo pipefail

HOOK="hooks/log-tool-call.sh"
REPO="$(pwd)"
ERRORS=0

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; ERRORS=$(( ERRORS + 1 )); }

# Create temp dir for output
TMPDIR_TEST=$(mktemp -d)
AUDIT_LOG_TEMP="${TMPDIR_TEST}/audit-log.jsonl"

cleanup() {
    rm -rf "$TMPDIR_TEST"
}
trap cleanup EXIT

# --- Test 1: Basic tool-call envelope appends a valid entry ---
envelope='{"tool_name":"Read","tool_args":{"file_path":"README.md"},"cwd":"/tmp","session_id":"sess-001","agent_id":"orchestrator"}'

AUDIT_LOG_PATH="$AUDIT_LOG_TEMP" bash "$HOOK" <<< "$envelope"
hook_exit=$?

if (( hook_exit != 0 )); then
    fail "Hook exited with code ${hook_exit} (expected 0)"
else
    pass "Hook exited 0"
fi

if [[ ! -f "$AUDIT_LOG_TEMP" ]]; then
    fail "Audit log file was not created at ${AUDIT_LOG_TEMP}"
else
    pass "Audit log file exists"
fi

# Validate with Python
validation_result=$(python3 - <<'PYEOF'
import json, pathlib, sys

audit_log = pathlib.Path("${AUDIT_LOG_TEMP_PY}")
if not audit_log.exists():
    print("FAIL: audit log does not exist")
    sys.exit(1)

lines = [l.strip() for l in audit_log.read_text(encoding="utf-8").splitlines() if l.strip()]
if not lines:
    print("FAIL: audit log is empty")
    sys.exit(1)

try:
    entry = json.loads(lines[-1])
except json.JSONDecodeError as e:
    print(f"FAIL: last line is not valid JSON: {e}")
    sys.exit(1)

required = ["entry_id", "timestamp", "event_type", "agent_id"]
for field in required:
    if field not in entry:
        print(f"FAIL: missing required field '{field}'")
        sys.exit(1)

print("SCHEMA CHECK PASS")
PYEOF
) 2>&1 || true

# Run the actual validation using temp path substitution
python3 - "$AUDIT_LOG_TEMP" <<'PYEOF'
import json, pathlib, sys

audit_log = pathlib.Path(sys.argv[1])
if not audit_log.exists():
    print("FAIL: audit log does not exist")
    sys.exit(1)

lines = [l.strip() for l in audit_log.read_text(encoding="utf-8").splitlines() if l.strip()]
if not lines:
    print("FAIL: audit log is empty")
    sys.exit(1)

try:
    entry = json.loads(lines[-1])
except json.JSONDecodeError as e:
    print(f"FAIL: last line is not valid JSON: {e}")
    sys.exit(1)

required = ["entry_id", "timestamp", "event_type", "agent_id"]
missing = [f for f in required if f not in entry]
if missing:
    print(f"FAIL: missing required fields: {missing}")
    sys.exit(1)

# Validate against schema using jsonschema if available
try:
    import jsonschema
    schema_path = pathlib.Path("schemas/audit-log-entry.schema.json")
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft7Validator(schema).validate(entry)
        print("Schema-valid: jsonschema validation passed")
    else:
        print("Schema file not found — skipping jsonschema validation (field check passed)")
except ImportError:
    print("jsonschema not installed — skipping schema validation (field check passed)")
except jsonschema.ValidationError as e:
    print(f"FAIL: schema validation error: {e.message}")
    sys.exit(1)

print("AUDIT ENTRY VALID")
PYEOF
py_exit=$?

if (( py_exit == 0 )); then
    pass "Audit log entry is valid"
else
    fail "Audit log entry validation failed"
fi

# --- Test 2: Empty envelope should not crash (fail open) ---
AUDIT_LOG_TEMP2="${TMPDIR_TEST}/audit-log2.jsonl"
if echo "" | AUDIT_LOG_PATH="$AUDIT_LOG_TEMP2" bash "$HOOK"; then
    pass "Empty envelope exits 0 (fail open)"
else
    fail "Empty envelope should exit 0 (was non-zero)"
fi

# --- Test 3: Missing audit log directory created automatically ---
AUDIT_LOG_TEMP3="${TMPDIR_TEST}/subdir/audit-log.jsonl"
envelope='{"tool_name":"Bash","tool_args":{"command":"echo test"},"cwd":"/tmp","session_id":"sess-002","agent_id":"test-agent"}'
if AUDIT_LOG_PATH="$AUDIT_LOG_TEMP3" bash "$HOOK" <<< "$envelope"; then
    if [[ -f "$AUDIT_LOG_TEMP3" ]]; then
        pass "Audit log created in new subdirectory"
    else
        fail "Audit log not created in new subdirectory"
    fi
else
    fail "Hook failed when creating subdirectory"
fi

# --- Test 4: Path anchoring via CLAUDE_PROJECT_DIR (issue #18 misroute regression) ---
# With no AUDIT_LOG_PATH override and the tool-call cwd shifted into <root>/.council,
# the audit log must land at <root>/.council/audit-log.jsonl, NOT a nested
# <root>/.council/.council/audit-log.jsonl.
PROJ4="${TMPDIR_TEST}/proj4"
mkdir -p "$PROJ4/.council"
envelope='{"tool_name":"Bash","tool_args":{"command":"git status"},"cwd":"'"$PROJ4"'/.council","session_id":"s4","agent_id":"orchestrator"}'
echo "$envelope" | CLAUDE_PROJECT_DIR="$PROJ4" AUDIT_LOG_PATH="" bash "$REPO/$HOOK" >/dev/null 2>&1
if [[ -f "$PROJ4/.council/audit-log.jsonl" && ! -d "$PROJ4/.council/.council" ]]; then
    pass "Audit log anchored to <root>/.council via CLAUDE_PROJECT_DIR (no nested .council/.council)"
else
    fail "Audit log misrouted under CLAUDE_PROJECT_DIR (nested .council/.council or canonical path missing)"
fi

# --- Test 5: Path anchoring via .git walk-up when CLAUDE_PROJECT_DIR is unset ---
# Fallback path: walk up from the tool-call cwd to the nearest .git marker.
PROJ5="${TMPDIR_TEST}/proj5"
mkdir -p "$PROJ5/.council"
: > "$PROJ5/.git"   # worktree-style .git file marker at the project root
envelope='{"tool_name":"Bash","tool_args":{"command":"ls"},"cwd":"'"$PROJ5"'/.council","session_id":"s5","agent_id":"orchestrator"}'
( unset CLAUDE_PROJECT_DIR; echo "$envelope" | AUDIT_LOG_PATH="" bash "$REPO/$HOOK" ) >/dev/null 2>&1
if [[ -f "$PROJ5/.council/audit-log.jsonl" && ! -d "$PROJ5/.council/.council" ]]; then
    pass "Audit log anchored via .git walk-up when CLAUDE_PROJECT_DIR unset"
else
    fail "Audit log walk-up anchoring failed (nested .council/.council or canonical path missing)"
fi

# --- Test 6: Native payload (tool_input, session_id, tool_use_id) into an initialized council ---
PROJ6="${TMPDIR_TEST}/proj6"
mkdir -p "$PROJ6/.council" "$PROJ6/.git" "$PROJ6/src"
envelope='{"hook_event_name":"PostToolUse","tool_name":"Edit","tool_input":{"file_path":"src/app.py","old_string":"a","new_string":"b"},"tool_response":{"filePath":"src/app.py","success":true},"cwd":"'"$PROJ6"'/src","session_id":"sess-native-6","tool_use_id":"toolu_006"}'
( unset CLAUDE_PROJECT_DIR; echo "$envelope" | AUDIT_LOG_PATH="" bash "$REPO/$HOOK" ) >/dev/null 2>&1
python3 - "$PROJ6/.council/audit-log.jsonl" <<'PYEOF'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
assert p.exists(), "audit log not written for native payload"
e = json.loads(p.read_text(encoding="utf-8").splitlines()[-1])
assert e["tool_input_summary"] == "file_path=src/app.py", e["tool_input_summary"]
assert e["session_id"] == "sess-native-6" and e["tool_use_id"] == "toolu_006", e
assert e["andon_pull_count"] is None, e["andon_pull_count"]
assert e["tool_outcome"] == "success" and e["event_type"] == "tool-call", e
import jsonschema
schema = json.loads(pathlib.Path("schemas/audit-log-entry.schema.json").read_text(encoding="utf-8"))
jsonschema.Draft7Validator(schema).validate(e)
print("NATIVE ENTRY VALID")
PYEOF
if (( $? == 0 )); then pass "Native payload: real file_path, session_id, tool_use_id, null andon count, schema-valid"; else fail "Native payload entry wrong or invalid"; fi

# --- Test 7: No .council at the root -> nothing written, nothing created ---
PROJ7="${TMPDIR_TEST}/proj7"
mkdir -p "$PROJ7/.git" "$PROJ7/sub"
envelope='{"tool_name":"Read","tool_input":{"file_path":"README.md"},"cwd":"'"$PROJ7"'/sub","session_id":"s7"}'
( unset CLAUDE_PROJECT_DIR; echo "$envelope" | AUDIT_LOG_PATH="" bash "$REPO/$HOOK" ) >/dev/null 2>&1
if [[ ! -e "$PROJ7/.council" ]]; then pass "No .council: no phantom directory, nothing written"; else fail "Phantom .council created in an uninitialized project"; fi

# --- Test 8: andon_signal in a tool response is logged as an andon-signal event ---
PROJ8="${TMPDIR_TEST}/proj8"
mkdir -p "$PROJ8/.council" "$PROJ8/.git"
envelope='{"tool_name":"Task","tool_input":{"prompt":"review"},"tool_response":{"content":"{\"andon_signal\":{\"type\":\"stop\"}}"},"cwd":"'"$PROJ8"'","session_id":"s8","tool_use_id":"toolu_008"}'
( unset CLAUDE_PROJECT_DIR; echo "$envelope" | AUDIT_LOG_PATH="" bash "$REPO/$HOOK" ) >/dev/null 2>&1
if grep -q '"event_type": "andon-signal"' "$PROJ8/.council/audit-log.jsonl" 2>/dev/null; then pass "andon_signal in tool response -> event_type andon-signal"; else fail "andon signal not detected"; fi

# --- Results ---
echo ""
if (( ERRORS == 0 )); then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "${ERRORS} TEST(S) FAILED"
    exit 1
fi
