#!/usr/bin/env bash
# Fixture test for hooks/enforce-branch-charter.sh
# Tests the headline catch (divergent branch, no charter -> BLOCK) plus the
# allow/warn paths and fail-open behavior.
# Exit 0 = all tests passed.

set -uo pipefail

HOOK="hooks/enforce-branch-charter.sh"
SCRIPT="$PWD/scripts/direction-check.py"
ERRORS=0
pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; ERRORS=$(( ERRORS + 1 )); }

TMP=$(mktemp -d)
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

mkdir -p "$TMP/.council/charters"
cat > "$TMP/.council/config.json" <<'EOF'
{"direction_check":{"enabled":true,"anchor_path":"docs/divorce-spec.md","killed_workstreams":["cmpx writer"],"mainline_branch":"main"}}
EOF
CONFIG="$TMP/.council/config.json"

# Envelope helper: a git commit Bash tool call.
ENV_COMMIT='{"tool_name":"Bash","tool_args":{"command":"git commit -m wip"},"cwd":"'"$TMP"'","session_id":"t"}'

run() {  # args: branch  [extra env assignments handled by caller]
    CLAUDE_PROJECT_DIR="$TMP" DIRECTION_CHECK_CONFIG="$CONFIG" \
    DIRECTION_CHECK_SCRIPT="$SCRIPT" DIRECTION_CHECK_BRANCH="$1" \
    bash "$HOOK" <<< "$ENV_COMMIT"
}

# 1. Divergent branch, NO charter -> BLOCK (the wizardly-johnson case).
if run "claude/wizardly-johnson"; then
    fail "divergent branch with no charter should BLOCK"
else
    pass "divergent branch with no charter is BLOCKED"
fi

# 2. On mainline -> allowed (nothing to enforce).
if run "main"; then
    pass "commit on mainline is allowed"
else
    fail "commit on mainline should be allowed"
fi

# 3. Divergent branch WITH a declared competitive+justified charter -> WARN (allowed).
cat > "$TMP/.council/charters/branch-claude-compete-x.json" <<'EOF'
{"charter_id":"WC-0050","branch":"claude/compete-x","created_at":"2026-06-20T00:00:00Z",
 "strategic_anchor":{"path":"docs/divorce-spec.md"},"workstream_scope":["cmpx-writer"],
 "exploration_mode":"competitive",
 "divergence_justification":"Benchmark a competing cmpx writer against the YAML path before committing."}
EOF
if run "claude/compete-x"; then
    pass "declared competitive branch is allowed (WARN)"
else
    fail "declared competitive branch should be allowed"
fi

# 4. Gate disabled in config -> fail open (allowed) even on divergent branch.
cat > "$TMP/.council/config-off.json" <<'EOF'
{"direction_check":{"enabled":false,"mainline_branch":"main"}}
EOF
if CLAUDE_PROJECT_DIR="$TMP" DIRECTION_CHECK_CONFIG="$TMP/.council/config-off.json" \
   DIRECTION_CHECK_SCRIPT="$SCRIPT" DIRECTION_CHECK_BRANCH="claude/whatever" \
   bash "$HOOK" <<< "$ENV_COMMIT"; then
    pass "disabled gate fails open (allowed)"
else
    fail "disabled gate should fail open"
fi

# 5. Non-git Bash command -> ignored (allowed).
NON_GIT='{"tool_name":"Bash","tool_args":{"command":"ls -la"},"cwd":"'"$TMP"'","session_id":"t"}'
if CLAUDE_PROJECT_DIR="$TMP" DIRECTION_CHECK_CONFIG="$CONFIG" DIRECTION_CHECK_SCRIPT="$SCRIPT" \
   DIRECTION_CHECK_BRANCH="claude/wizardly-johnson" bash "$HOOK" <<< "$NON_GIT"; then
    pass "non-git command is ignored (allowed)"
else
    fail "non-git command should be ignored"
fi

# 6. Empty envelope -> fail open.
if echo "" | bash "$HOOK"; then
    pass "empty envelope fails open"
else
    fail "empty envelope should fail open"
fi

echo ""
if (( ERRORS == 0 )); then echo "ALL TESTS PASSED"; exit 0; else echo "${ERRORS} TEST(S) FAILED"; exit 1; fi
