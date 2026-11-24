#!/usr/bin/env bash
# Fixture test for hooks/enforce-branch-charter.sh
# Tests the headline catch (divergent branch, no charter -> BLOCK), the
# contract-content catch (a killed workstream in the sprint contract -> BLOCK),
# the allow/warn paths and fail-open behavior.
#
# A block must be exit 2 exactly: Claude Code blocks a PreToolUse call only on
# exit 2. An allow must be exit 0. Native cases start from the Bash PreToolUse
# payload recorded from Claude Code (tests/fixtures/payloads/pretooluse-native.jsonl)
# and change only the command and cwd; one legacy tool_args case proves the
# fallback still works.
# Exit 0 = all tests passed.

set -uo pipefail

HOOK="hooks/enforce-branch-charter.sh"
SCRIPT="$PWD/scripts/direction-check.py"
FIXTURE="tests/fixtures/payloads/pretooluse-native.jsonl"
ERRORS=0
pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; ERRORS=$(( ERRORS + 1 )); }

TMP=$(mktemp -d)
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

mkdir -p "$TMP/.council/charters" "$TMP/.harness/contracts"
cat > "$TMP/.council/config.json" <<'EOF'
{"direction_check":{"enabled":true,"anchor_path":"docs/divorce-spec.md","killed_workstreams":["cmpx writer"],"mainline_branch":"main"}}
EOF
CONFIG="$TMP/.council/config.json"

# payload <command>: the recorded Bash payload with command and cwd replaced
payload() {
    python3 - "$FIXTURE" "$1" "$TMP" <<'PY'
import json, sys
fixture, command, cwd = sys.argv[1:]
records = [json.loads(line) for line in open(fixture, encoding="utf-8") if line.strip()]
d = next(r for r in records if r["tool_name"] == "Bash")
d["tool_input"]["command"] = command
d["cwd"] = cwd
print(json.dumps(d))
PY
}

ENV_COMMIT=$(payload "git commit -m wip")

# run <branch> [config] [envelope]: prints the hook's exit code
run() {
    CLAUDE_PROJECT_DIR="$TMP" DIRECTION_CHECK_CONFIG="${2:-$CONFIG}" \
    DIRECTION_CHECK_SCRIPT="$SCRIPT" DIRECTION_CHECK_BRANCH="$1" \
    bash "$HOOK" <<< "${3:-$ENV_COMMIT}" >/dev/null 2>&1
    echo $?
}

expect() {  # expect <name> <want> <got>
    if [[ "$3" == "$2" ]]; then pass "$1 (exit $3)"; else fail "$1: expected exit $2, got $3"; fi
}

# 1. Divergent branch, NO charter -> BLOCK (the wizardly-johnson case).
expect "divergent branch with no charter is BLOCKED" 2 "$(run "claude/wizardly-johnson")"

# 1b. Same, legacy tool_args envelope -> still BLOCK.
LEGACY='{"tool_name":"Bash","tool_args":{"command":"git commit -m wip"},"cwd":"'"$TMP"'","session_id":"t"}'
expect "legacy tool_args envelope is still BLOCKED" 2 "$(run "claude/wizardly-johnson" "$CONFIG" "$LEGACY")"

# 2. On mainline -> allowed (nothing to enforce).
expect "commit on mainline is allowed" 0 "$(run "main")"

# 3. Divergent branch WITH a declared competitive+justified charter -> WARN (allowed).
cat > "$TMP/.council/charters/branch-claude-compete-x.json" <<'EOF'
{"charter_id":"WC-0050","branch":"claude/compete-x","created_at":"2026-06-20T00:00:00Z",
 "strategic_anchor":{"path":"docs/divorce-spec.md"},"workstream_scope":["cmpx-writer"],
 "exploration_mode":"competitive",
 "divergence_justification":"Benchmark a competing cmpx writer against the YAML path before committing."}
EOF
expect "declared competitive branch is allowed (WARN)" 0 "$(run "claude/compete-x")"

# 4. Divergent branch with a MAINLINE charter whose sprint contract reintroduces
#    a killed workstream -> BLOCK (the hook resolves the contract from
#    sprint_context; before the fix it never read the contract).
cat > "$TMP/.council/charters/branch-claude-feature-y.json" <<'EOF'
{"charter_id":"WC-0051","branch":"claude/feature-y","sprint_context":3,"created_at":"2026-06-20T00:00:00Z",
 "strategic_anchor":{"path":"docs/divorce-spec.md"},"workstream_scope":["export"],
 "exploration_mode":"mainline"}
EOF
printf '# Sprint 03\nCites docs/divorce-spec.md.\nBuild the .cmpx writer for export.\n' > "$TMP/.harness/contracts/sprint-03.md"
expect "mainline charter + contract reintroducing a killed workstream is BLOCKED" 2 "$(run "claude/feature-y")"

# 4b. Same charter, clean contract -> allowed.
printf '# Sprint 03\nCites docs/divorce-spec.md.\nBuild the YAML writer for export.\n' > "$TMP/.harness/contracts/sprint-03.md"
expect "mainline charter + clean contract is allowed" 0 "$(run "claude/feature-y")"

# 5. Gate disabled in config -> fail open (allowed) even on divergent branch.
cat > "$TMP/.council/config-off.json" <<'EOF'
{"direction_check":{"enabled":false,"mainline_branch":"main"}}
EOF
expect "disabled gate fails open (allowed)" 0 "$(run "claude/whatever" "$TMP/.council/config-off.json")"

# 6. Non-git Bash command -> ignored (allowed).
expect "non-git command is ignored (allowed)" 0 "$(run "claude/wizardly-johnson" "$CONFIG" "$(payload "ls -la")")"

# 7. Empty envelope -> fail open.
echo "" | bash "$HOOK" >/dev/null 2>&1
expect "empty envelope fails open" 0 "$?"

echo ""
if (( ERRORS == 0 )); then echo "ALL TESTS PASSED"; exit 0; else echo "${ERRORS} TEST(S) FAILED"; exit 1; fi
