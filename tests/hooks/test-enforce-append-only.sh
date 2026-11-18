#!/usr/bin/env bash
# Fixture test for hooks/enforce-append-only.sh
#
# A block must be exit 2 exactly: Claude Code blocks a PreToolUse call only on
# exit 2, and treats any other non-zero code as a non-blocking error (the write
# goes ahead). An allow must be exit 0.
#
# Native cases start from PreToolUse payloads recorded from Claude Code
# (tests/fixtures/payloads/pretooluse-native.jsonl) and change only the target
# path, the cwd or the tool name, so they use the field names Claude Code really
# sends (tool_input, never tool_args). Legacy tool_args cases stay, to prove the
# fallback still works.
# Exit 0 = all tests passed.

set -uo pipefail

HOOK="hooks/enforce-append-only.sh"
FIXTURE="tests/fixtures/payloads/pretooluse-native.jsonl"
ERRORS=0

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; ERRORS=$(( ERRORS + 1 )); }

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

# expect <exit-code> <description> <payload-json>
expect() {
    local want="$1" desc="$2" body="$3" got
    printf '%s' "$body" | bash "$HOOK" 2>/dev/null
    got=$?
    if [[ "$got" == "$want" ]]; then
        pass "$desc (exit $got)"
    else
        fail "$desc: expected exit $want, got $got"
    fi
}

# --- Native payloads: BLOCK (exit 2) ---
for log in henka-register decision-log audit-log; do
    expect 2 "native Write on .council/${log}.jsonl is blocked" \
        "$(payload Write "tool_input.file_path=/work/proj/.council/${log}.jsonl")"
done
expect 2 "native Edit on .council/decision-log.jsonl is blocked" \
    "$(payload Edit tool_input.file_path=/work/proj/.council/decision-log.jsonl)"
expect 2 "native Edit on .council/henka-register.jsonl is blocked" \
    "$(payload Edit tool_input.file_path=/work/proj/.council/henka-register.jsonl)"
expect 2 "native bare henka-register.jsonl from cwd=.council is blocked" \
    "$(payload Write tool_input.file_path=henka-register.jsonl cwd=/work/proj/.council)"
expect 2 "native ./decision-log.jsonl from cwd=.council is blocked" \
    "$(payload Write tool_input.file_path=./decision-log.jsonl cwd=/work/proj/.council)"

# The block reason reaches stderr (Claude Code shows it to the model)
reason=$(printf '%s' "$(payload Write tool_input.file_path=/work/proj/.council/audit-log.jsonl)" | bash "$HOOK" 2>&1 >/dev/null)
if [[ "$reason" == *"BLOCKED"*"audit-log.jsonl"* ]]; then
    pass "block reason names the protected log on stderr"
else
    fail "block reason missing from stderr: '${reason}'"
fi

# --- Native payloads: ALLOW (exit 0) ---
expect 0 "recorded Write to an ordinary file is allowed" "$(payload Write)"
expect 0 "recorded Edit of an ordinary file is allowed" "$(payload Edit)"
expect 0 "native henka-register.jsonl at the project root (not .council) is allowed" \
    "$(payload Write tool_input.file_path=henka-register.jsonl cwd=/work/proj)"
expect 0 "recorded Bash call is allowed (not a Write or Edit)" "$(payload Bash)"
expect 0 "native Bash reading a ledger is allowed" \
    "$(payload Bash 'tool_input.command=cat .council/audit-log.jsonl')"
expect 0 "native Read of a ledger is allowed" \
    "$(payload Write tool_name=Read tool_input.file_path=/work/proj/.council/audit-log.jsonl)"

# --- Legacy tool_args envelopes: still recognized ---
expect 2 "legacy Write on henka-register.jsonl is blocked" \
    '{"tool_name":"Write","tool_args":{"file_path":".council/henka-register.jsonl"},"cwd":"/tmp","session_id":"test"}'
expect 2 "legacy Write on decision-log.jsonl is blocked" \
    '{"tool_name":"Write","tool_args":{"file_path":".council/decision-log.jsonl"},"cwd":"/tmp","session_id":"test"}'
expect 2 "legacy Write on audit-log.jsonl is blocked" \
    '{"tool_name":"Write","tool_args":{"file_path":".council/audit-log.jsonl"},"cwd":"/tmp","session_id":"test"}'
expect 2 "legacy Edit on decision-log.jsonl is blocked" \
    '{"tool_name":"Edit","tool_args":{"file_path":".council/decision-log.jsonl"},"cwd":"/tmp","session_id":"test"}'
expect 2 "legacy bare henka-register.jsonl from cwd=.council is blocked (issue #18)" \
    '{"tool_name":"Write","tool_args":{"file_path":"henka-register.jsonl"},"cwd":"/proj/.council","session_id":"test"}'
expect 2 "legacy ./decision-log.jsonl from cwd=.council is blocked" \
    '{"tool_name":"Write","tool_args":{"file_path":"./decision-log.jsonl"},"cwd":"/proj/.council","session_id":"test"}'
expect 2 "legacy absolute path to audit-log.jsonl is blocked" \
    '{"tool_name":"Write","tool_args":{"file_path":"/proj/.council/audit-log.jsonl"},"cwd":"/somewhere/else","session_id":"test"}'
expect 0 "legacy henka-register.jsonl at the project root is allowed" \
    '{"tool_name":"Write","tool_args":{"file_path":"henka-register.jsonl"},"cwd":"/proj","session_id":"test"}'
expect 0 "legacy Write on a non-protected file is allowed" \
    '{"tool_name":"Write","tool_args":{"file_path":"scripts/append-henka.py"},"cwd":"/tmp","session_id":"test"}'
expect 0 "legacy Bash is allowed" \
    '{"tool_name":"Bash","tool_args":{"command":"cat .council/audit-log.jsonl"},"cwd":"/tmp","session_id":"test"}'
expect 0 "legacy Read is allowed" \
    '{"tool_name":"Read","tool_args":{"file_path":".council/audit-log.jsonl"},"cwd":"/tmp","session_id":"test"}'

# --- Fail open ---
expect 0 "empty envelope fails open" ""

# --- Results ---
echo ""
if (( ERRORS == 0 )); then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "${ERRORS} TEST(S) FAILED"
    exit 1
fi
