#!/usr/bin/env bash
# Fixture test for hooks/session-diagnostics.sh (the bash wrapper).
# The measurement logic is covered cross-platform by tests/scripts/test-session-diagnostics.py;
# this test proves the wrapper passes the payload through, writes one event, and fails open.
set -uo pipefail
HOOK="hooks/session-diagnostics.sh"
REPO="$(pwd)"
FIXTURE="$REPO/tests/fixtures/transcripts/session-fixture.jsonl"
ERRORS=0
pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; ERRORS=$(( ERRORS + 1 )); }
TMPDIR_TEST=$(mktemp -d)
trap 'rm -rf "$TMPDIR_TEST"' EXIT

# --- Test 1: one event per session into <root>/.council/diagnostics.jsonl ---
PROJ="$TMPDIR_TEST/proj"
mkdir -p "$PROJ/.council" "$PROJ/.git" "$PROJ/.harness"
echo '{"current_sprint": 9}' > "$PROJ/.harness/sprint-state.json"
payload='{"session_id":"fixture-session-0001","transcript_path":"'"$FIXTURE"'","cwd":"'"$PROJ"'","hook_event_name":"SessionEnd","reason":"other"}'
( unset CLAUDE_PROJECT_DIR DIAGNOSTICS_LOG_PATH; echo "$payload" | bash "$REPO/$HOOK" )
if (( $? == 0 )); then pass "Wrapper exits 0"; else fail "Wrapper exited non-zero"; fi
LOG="$PROJ/.council/diagnostics.jsonl"
if [[ -f "$LOG" && $(grep -c . "$LOG") -eq 1 ]]; then pass "Exactly one event written"; else fail "Expected one event in $LOG"; fi
if grep -q '"kind": "session"' "$LOG" 2>/dev/null && grep -q '"output_tokens": 170' "$LOG" 2>/dev/null; then
    pass "Event is a session event with deduplicated totals"
else
    fail "Event content unexpected: $(head -c 300 "$LOG" 2>/dev/null)"
fi
if grep -q "PROMPT-CANARY-7731" "$LOG" 2>/dev/null; then fail "Prompt text leaked into the event"; else pass "No prompt text in the event"; fi

# --- Test 2: no .council -> nothing written, nothing created ---
PROJ2="$TMPDIR_TEST/proj2"
mkdir -p "$PROJ2/.git"
payload='{"session_id":"s2","transcript_path":"'"$FIXTURE"'","cwd":"'"$PROJ2"'","hook_event_name":"SessionEnd"}'
( unset CLAUDE_PROJECT_DIR DIAGNOSTICS_LOG_PATH; echo "$payload" | bash "$REPO/$HOOK" ) >/dev/null 2>&1
if [[ ! -e "$PROJ2/.council" ]]; then pass "No .council: nothing created"; else fail "Phantom .council created"; fi

# --- Test 3: empty stdin fails open ---
if echo "" | bash "$REPO/$HOOK"; then pass "Empty payload exits 0"; else fail "Empty payload should exit 0"; fi

echo ""
if (( ERRORS == 0 )); then echo "ALL TESTS PASSED"; exit 0; else echo "${ERRORS} TEST(S) FAILED"; exit 1; fi
