#!/usr/bin/env bash
# Fixture test for hooks/enforce-reversibility.sh
#
# A block must be exit 2 exactly: Claude Code blocks a PreToolUse call only on
# exit 2, and treats any other non-zero code as a non-blocking error (the command
# runs). An allow must be exit 0.
#
# Native cases start from the Bash PreToolUse payload recorded from Claude Code
# (tests/fixtures/payloads/pretooluse-native.jsonl) and change only the command,
# so they use tool_input as Claude Code sends it. Legacy tool_args cases stay, to
# prove the fallback still works.
# Exit 0 = all tests passed.

set -uo pipefail

HOOK="hooks/enforce-reversibility.sh"
FIXTURE="tests/fixtures/payloads/pretooluse-native.jsonl"
ERRORS=0

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; ERRORS=$(( ERRORS + 1 )); }

TMPDIR_TEST=$(mktemp -d)
AUTONOMY_FILE="${TMPDIR_TEST}/effective-autonomy.json"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

write_autonomy() {
    cat > "$AUTONOMY_FILE" <<JSON
{"level": $1, "last_change": "2026-01-01T00:00:00Z", "reason": "test"}
JSON
}

# payload <recorded-tool> [dotted.key=value ...]: a recorded payload with fields replaced
payload() {
    python3 - "$FIXTURE" "$@" <<'PY'
import json, sys
fixture, tool, *pairs = sys.argv[1:]
records = [json.loads(line) for line in open(fixture, encoding="utf-8") if line.strip()]
d = next(r for r in records if r["tool_name"] == tool)
for pair in pairs:
    key, value = pair.split("=", 1)
    *parents, last = key.split(".")
    target = d
    for p in parents:
        target = target.setdefault(p, {})
    target[last] = value
print(json.dumps(d))
PY
}

# expect <exit-code> <level> <description> <payload-json>
expect() {
    local want="$1" level="$2" desc="$3" body="$4" got
    write_autonomy "$level"
    printf '%s' "$body" | EFFECTIVE_AUTONOMY_PATH="$AUTONOMY_FILE" bash "$HOOK" 2>/dev/null
    got=$?
    if [[ "$got" == "$want" ]]; then
        pass "$desc (exit $got)"
    else
        fail "$desc: expected exit $want, got $got"
    fi
}

# --- Native payloads: BLOCK (exit 2) ---
expect 2 3 "native git push at level 3 is blocked" "$(payload Bash 'tool_input.command=git push origin main')"
expect 2 3 "native git reset --hard at level 3 is blocked" "$(payload Bash 'tool_input.command=git reset --hard HEAD~1')"
expect 2 4 "native rm -rf at level 4 is blocked" "$(payload Bash 'tool_input.command=rm -rf build')"
expect 2 4 "native git push --force at level 4 is blocked" "$(payload Bash 'tool_input.command=git push --force origin main')"

# The block reason reaches stderr (Claude Code shows it to the model)
write_autonomy 4
reason=$(printf '%s' "$(payload Bash 'tool_input.command=rm -rf build')" | EFFECTIVE_AUTONOMY_PATH="$AUTONOMY_FILE" bash "$HOOK" 2>&1 >/dev/null)
if [[ "$reason" == *"BLOCKED"*"rm -rf"* ]]; then
    pass "block reason names the irreversible pattern on stderr"
else
    fail "block reason missing from stderr: '${reason}'"
fi

# --- Native payloads: ALLOW (exit 0) ---
expect 0 5 "native git push at level 5 is allowed" "$(payload Bash 'tool_input.command=git push origin main')"
expect 0 4 "recorded Bash call (ls) at level 4 is allowed" "$(payload Bash)"
expect 0 3 "native ls -la at level 3 is allowed" "$(payload Bash 'tool_input.command=ls -la')"
expect 0 1 "recorded Write (not Bash) at level 1 is allowed" "$(payload Write)"

# --- Legacy tool_args envelopes: still recognized ---
expect 2 3 "legacy git push at level 3 is blocked" \
    '{"tool_name":"Bash","tool_args":{"command":"git push origin main"},"cwd":"/tmp","session_id":"test"}'
expect 2 3 "legacy git reset --hard at level 3 is blocked" \
    '{"tool_name":"Bash","tool_args":{"command":"git reset --hard HEAD~1"},"cwd":"/tmp","session_id":"test"}'
expect 2 4 "legacy rm -rf at level 4 is blocked" \
    '{"tool_name":"Bash","tool_args":{"command":"rm -rf /tmp/foo"},"cwd":"/tmp","session_id":"test"}'
expect 0 5 "legacy git push at level 5 is allowed" \
    '{"tool_name":"Bash","tool_args":{"command":"git push origin main"},"cwd":"/tmp","session_id":"test"}'
expect 0 3 "legacy ls -la at level 3 is allowed" \
    '{"tool_name":"Bash","tool_args":{"command":"ls -la"},"cwd":"/tmp","session_id":"test"}'
expect 0 1 "legacy Write (not Bash) at level 1 is allowed" \
    '{"tool_name":"Write","tool_args":{"file_path":"foo.txt"},"cwd":"/tmp","session_id":"test"}'

# --- Fail open ---
got=0
printf '%s' "$(payload Bash 'tool_input.command=echo hello')" | EFFECTIVE_AUTONOMY_PATH="/nonexistent/effective-autonomy.json" bash "$HOOK" 2>/dev/null || got=$?
if [[ "$got" == 0 ]]; then pass "missing state file with a safe command fails open (exit 0)"; else fail "missing state file with a safe command should exit 0, got $got"; fi
expect 0 4 "empty envelope fails open" ""

# --- Results ---
echo ""
if (( ERRORS == 0 )); then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "${ERRORS} TEST(S) FAILED"
    exit 1
fi
