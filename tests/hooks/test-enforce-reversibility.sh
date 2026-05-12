#!/usr/bin/env bash
# Fixture test for hooks/enforce-reversibility.sh
# Tests ALLOW and BLOCK paths with temp state file.
# Exit 0 = all tests passed.

set -uo pipefail

HOOK="hooks/enforce-reversibility.sh"
ERRORS=0

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; ERRORS=$(( ERRORS + 1 )); }

# Create temp dir for state files
TMPDIR_TEST=$(mktemp -d)
AUTONOMY_FILE="${TMPDIR_TEST}/effective-autonomy.json"

cleanup() {
    rm -rf "$TMPDIR_TEST"
}
trap cleanup EXIT

# Helper: write autonomy file at given level
write_autonomy() {
    local lvl="$1"
    cat > "$AUTONOMY_FILE" <<EOF
{"level": ${lvl}, "last_change": "2026-01-01T00:00:00Z", "reason": "test"}
EOF
}

# Helper: run hook with envelope and autonomy level override
run_hook_with_level() {
    local envelope="$1"
    local lvl="$2"
    write_autonomy "$lvl"
    EFFECTIVE_AUTONOMY_PATH="$AUTONOMY_FILE" echo "$envelope" | bash "$HOOK"
    return $?
}

# --- BLOCK cases ---

# level=3, git push should be blocked
envelope='{"tool_name":"Bash","tool_args":{"command":"git push origin main"},"cwd":"/tmp","session_id":"test"}'
write_autonomy 3
if EFFECTIVE_AUTONOMY_PATH="$AUTONOMY_FILE" bash "$HOOK" <<< "$envelope"; then
    fail "git push at level=3 should be blocked"
else
    pass "git push at level=3 is blocked"
fi

# level=3, git reset --hard should be blocked
envelope='{"tool_name":"Bash","tool_args":{"command":"git reset --hard HEAD~1"},"cwd":"/tmp","session_id":"test"}'
write_autonomy 3
if EFFECTIVE_AUTONOMY_PATH="$AUTONOMY_FILE" bash "$HOOK" <<< "$envelope"; then
    fail "git reset --hard at level=3 should be blocked"
else
    pass "git reset --hard at level=3 is blocked"
fi

# level=4, rm -rf should be blocked
envelope='{"tool_name":"Bash","tool_args":{"command":"rm -rf /tmp/foo"},"cwd":"/tmp","session_id":"test"}'
write_autonomy 4
if EFFECTIVE_AUTONOMY_PATH="$AUTONOMY_FILE" bash "$HOOK" <<< "$envelope"; then
    fail "rm -rf at level=4 should be blocked"
else
    pass "rm -rf at level=4 is blocked"
fi

# --- ALLOW cases ---

# level=5, git push should be allowed
envelope='{"tool_name":"Bash","tool_args":{"command":"git push origin main"},"cwd":"/tmp","session_id":"test"}'
write_autonomy 5
if EFFECTIVE_AUTONOMY_PATH="$AUTONOMY_FILE" bash "$HOOK" <<< "$envelope"; then
    pass "git push at level=5 is allowed"
else
    fail "git push at level=5 should be allowed"
fi

# level=3, non-destructive Bash command should be allowed
envelope='{"tool_name":"Bash","tool_args":{"command":"ls -la"},"cwd":"/tmp","session_id":"test"}'
write_autonomy 3
if EFFECTIVE_AUTONOMY_PATH="$AUTONOMY_FILE" bash "$HOOK" <<< "$envelope"; then
    pass "ls at level=3 is allowed"
else
    fail "ls at level=3 should be allowed"
fi

# Write tool (non-Bash) must always be allowed regardless of level
envelope='{"tool_name":"Write","tool_args":{"file_path":"foo.txt"},"cwd":"/tmp","session_id":"test"}'
write_autonomy 1
if EFFECTIVE_AUTONOMY_PATH="$AUTONOMY_FILE" bash "$HOOK" <<< "$envelope"; then
    pass "Write tool at level=1 is allowed (non-Bash)"
else
    fail "Write tool should always be allowed (non-Bash)"
fi

# Missing state file — should fail open (allow, default level 4)
# level=4 blocks irreversible; but no file defaults to 4 still blocks irreversible
# Let's test with a safe command when no file exists
envelope='{"tool_name":"Bash","tool_args":{"command":"echo hello"},"cwd":"/tmp","session_id":"test"}'
if EFFECTIVE_AUTONOMY_PATH="/nonexistent/path/effective-autonomy.json" bash "$HOOK" <<< "$envelope"; then
    pass "Missing state file with safe command — fails open (allowed)"
else
    fail "Missing state file with safe command should fail open"
fi

# Empty envelope must allow (fail open)
if echo "" | EFFECTIVE_AUTONOMY_PATH="$AUTONOMY_FILE" bash "$HOOK"; then
    pass "Empty envelope fails open (exit 0)"
else
    fail "Empty envelope should fail open"
fi

# --- Results ---
echo ""
if (( ERRORS == 0 )); then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "${ERRORS} TEST(S) FAILED"
    exit 1
fi
