#!/usr/bin/env bash
# Fixture test for hooks/enforce-append-only.sh
# Tests ALLOW and BLOCK paths.
# Exit 0 = all tests passed.

set -uo pipefail

HOOK="hooks/enforce-append-only.sh"
ERRORS=0

# All .council/ paths used below are JSON input strings only — no writes to .council/.
# Isolation: hook is stateless for this test (no state files needed).
# TMPDIR is still established for any future write-path expansions.
TMPDIR_TEST=$(mktemp -d)
trap 'rm -rf "$TMPDIR_TEST"' EXIT

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; ERRORS=$(( ERRORS + 1 )); }

# Helper: run hook with given envelope JSON; returns hook exit code
run_hook() {
    local envelope="$1"
    echo "$envelope" | bash "$HOOK"
    return $?
}

# --- BLOCK cases ---

# Write on henka-register.jsonl must block
envelope='{"tool_name":"Write","tool_args":{"file_path":".council/henka-register.jsonl"},"cwd":"/tmp","session_id":"test"}'
if run_hook "$envelope"; then
    fail "Write on henka-register.jsonl should have been blocked (exit 0 is wrong)"
else
    pass "Write on henka-register.jsonl is blocked"
fi

# Write on decision-log.jsonl must block
envelope='{"tool_name":"Write","tool_args":{"file_path":".council/decision-log.jsonl"},"cwd":"/tmp","session_id":"test"}'
if run_hook "$envelope"; then
    fail "Write on decision-log.jsonl should have been blocked"
else
    pass "Write on decision-log.jsonl is blocked"
fi

# Write on audit-log.jsonl must block
envelope='{"tool_name":"Write","tool_args":{"file_path":".council/audit-log.jsonl"},"cwd":"/tmp","session_id":"test"}'
if run_hook "$envelope"; then
    fail "Write on audit-log.jsonl should have been blocked"
else
    pass "Write on audit-log.jsonl is blocked"
fi

# Edit on decision-log.jsonl must block
envelope='{"tool_name":"Edit","tool_args":{"file_path":".council/decision-log.jsonl"},"cwd":"/tmp","session_id":"test"}'
if run_hook "$envelope"; then
    fail "Edit on decision-log.jsonl should have been blocked"
else
    pass "Edit on decision-log.jsonl is blocked"
fi

# --- BLOCK cases: cwd-relative path resolution (issue #18 append-only bypass regression) ---
# A protected log can be written via a path expressed relative to a shifted cwd. The hook
# must resolve file_path against cwd before matching, or these evade the guard (exit 0).

# Bare filename written from cwd inside .council/ must block (the confirmed bypass)
envelope='{"tool_name":"Write","tool_args":{"file_path":"henka-register.jsonl"},"cwd":"/proj/.council","session_id":"test"}'
if run_hook "$envelope"; then
    fail "Bare henka-register.jsonl from cwd=/proj/.council should be blocked (append-only bypass)"
else
    pass "Bare henka-register.jsonl from cwd=.council is blocked"
fi

# ./-relative filename from cwd inside .council/ must block
envelope='{"tool_name":"Write","tool_args":{"file_path":"./decision-log.jsonl"},"cwd":"/proj/.council","session_id":"test"}'
if run_hook "$envelope"; then
    fail "./decision-log.jsonl from cwd=/proj/.council should be blocked"
else
    pass "./decision-log.jsonl from cwd=.council is blocked"
fi

# Absolute path to a protected log (cwd elsewhere) must block
envelope='{"tool_name":"Write","tool_args":{"file_path":"/proj/.council/audit-log.jsonl"},"cwd":"/somewhere/else","session_id":"test"}'
if run_hook "$envelope"; then
    fail "Absolute /proj/.council/audit-log.jsonl should be blocked"
else
    pass "Absolute path to audit-log.jsonl is blocked"
fi

# --- BLOCK cases: Windows backslash paths (Git Bash / Windows envelopes) ---
# Windows hosts emit backslash separators in file_path and cwd. The hook must
# normalize them before matching; without that, backslash paths silently
# under-block on Git Bash.

# Relative backslash path to a protected log must block
envelope='{"tool_name":"Write","tool_args":{"file_path":".council\\henka-register.jsonl"},"cwd":"C:\\proj","session_id":"test"}'
if run_hook "$envelope"; then
    fail 'Backslash .council\henka-register.jsonl should be blocked'
else
    pass "Backslash-relative .council path is blocked"
fi

# Absolute Windows path to a protected log must block
envelope='{"tool_name":"Write","tool_args":{"file_path":"C:\\proj\\.council\\decision-log.jsonl"},"cwd":"C:\\somewhere\\else","session_id":"test"}'
if run_hook "$envelope"; then
    fail 'Absolute C:\proj\.council\decision-log.jsonl should be blocked'
else
    pass "Absolute Windows backslash path to decision-log.jsonl is blocked"
fi

# Bare filename resolved against a backslash Windows cwd inside .council must block
envelope='{"tool_name":"Write","tool_args":{"file_path":"audit-log.jsonl"},"cwd":"C:\\proj\\.council","session_id":"test"}'
if run_hook "$envelope"; then
    fail 'Bare audit-log.jsonl from backslash cwd C:\proj\.council should be blocked'
else
    pass "Bare audit-log.jsonl from backslash Windows cwd is blocked"
fi

# --- ALLOW cases ---

# Backslash path with the protected basename but NOT under .council must NOT over-block
envelope='{"tool_name":"Write","tool_args":{"file_path":"C:\\proj\\henka-register.jsonl"},"cwd":"C:\\proj","session_id":"test"}'
if run_hook "$envelope"; then
    pass "Backslash path to non-.council henka-register.jsonl is allowed"
else
    fail 'C:\proj\henka-register.jsonl (not under .council) should be allowed'
fi

# Same basename but NOT under .council/ is a different file — must NOT over-block
envelope='{"tool_name":"Write","tool_args":{"file_path":"henka-register.jsonl"},"cwd":"/proj","session_id":"test"}'
if run_hook "$envelope"; then
    pass "Bare henka-register.jsonl from project root (not .council) is allowed"
else
    fail "henka-register.jsonl at project root should be allowed (it is not the protected file)"
fi

# Write on a non-protected file must allow
envelope='{"tool_name":"Write","tool_args":{"file_path":"scripts/append-henka.py"},"cwd":"/tmp","session_id":"test"}'
if run_hook "$envelope"; then
    pass "Write on non-protected file is allowed"
else
    fail "Write on non-protected file should be allowed (was blocked)"
fi

# Bash tool must always allow
envelope='{"tool_name":"Bash","tool_args":{"command":"cat .council/audit-log.jsonl"},"cwd":"/tmp","session_id":"test"}'
if run_hook "$envelope"; then
    pass "Bash tool is allowed"
else
    fail "Bash tool should be allowed (was blocked)"
fi

# Read tool must always allow
envelope='{"tool_name":"Read","tool_args":{"file_path":".council/audit-log.jsonl"},"cwd":"/tmp","session_id":"test"}'
if run_hook "$envelope"; then
    pass "Read tool is allowed"
else
    fail "Read tool should be allowed (was blocked)"
fi

# Empty envelope must allow (fail open)
if echo "" | bash "$HOOK"; then
    pass "Empty envelope fails open (exit 0)"
else
    fail "Empty envelope should fail open (was blocked)"
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
