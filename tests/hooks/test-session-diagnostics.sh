#!/usr/bin/env bash
# Fixture test for hooks/session-diagnostics.sh (the bash wrapper). Parity twin:
# tests/hooks/win/test-session-diagnostics.ps1. The deriver itself is covered
# cross-platform by tests/scripts/test-session-diagnostics.py; this test proves the
# wrapper passes the payload through as raw bytes, writes one event per settled
# lifetime, appends nothing on a second firing, fails open, and that with
# AUTOMATE_RUN set none of the council's writing hooks writes anything.
set -uo pipefail
HOOK="hooks/session-diagnostics.sh"
REPO="$(pwd)"
FIXTURE_DIR="$REPO/tests/fixtures/transcripts/p05-fork-subagent/projects/-work-proj"
SESSION="00000000-0000-4000-8000-000000000001"
TRANSCRIPT="$FIXTURE_DIR/$SESSION.jsonl"
ERRORS=0
pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; ERRORS=$(( ERRORS + 1 )); }
TMPDIR_TEST=$(mktemp -d)
trap 'rm -rf "$TMPDIR_TEST"' EXIT

make_project() {
    mkdir -p "$1/.git" "$1/.harness"
    echo '{"current_sprint": 9, "current_phase": 2}' > "$1/.harness/sprint-state.json"
    if [[ "${2:-council}" == "council" ]]; then mkdir -p "$1/.council"; fi
}
payload_for() {  # <cwd> [reason]
    printf '{"session_id":"%s","transcript_path":"%s","cwd":"%s","hook_event_name":"SessionEnd","reason":"%s"}' \
        "$SESSION" "$TRANSCRIPT" "$1" "${2:-other}"
}
run_hook() {  # <payload> [VAR=value ...]
    local payload="$1"; shift
    ( unset CLAUDE_PROJECT_DIR DIAGNOSTICS_LOG_PATH AUTOMATE_RUN CLAUDE_PID; \
      printf '%s' "$payload" | env "$@" bash "$REPO/$HOOK" )
}

# --- Test 1: the closing lifetime becomes one schema 1.1 event ---
PROJ="$TMPDIR_TEST/proj"
make_project "$PROJ"
run_hook "$(payload_for "$PROJ/sub/dir")" CLAUDE_PID=4101
if (( $? == 0 )); then pass "Wrapper exits 0"; else fail "Wrapper exited non-zero"; fi
LOG="$PROJ/.council/diagnostics.jsonl"
if [[ -f "$LOG" && $(grep -c . "$LOG") -eq 1 ]]; then pass "Exactly one event written"; else fail "Expected one event in $LOG"; fi
if grep -q '"schema_version": "1.1"' "$LOG" 2>/dev/null && grep -q '"kind": "session"' "$LOG" 2>/dev/null \
   && grep -q '"start_source": "resume"' "$LOG" 2>/dev/null && grep -q '"phase": 2' "$LOG" 2>/dev/null; then
    pass "Event is the resumed lifetime's schema 1.1 session event, with the phase"
else
    fail "Event content unexpected: $(head -c 300 "$LOG" 2>/dev/null)"
fi
# A1 D1.5: ts is the lifetime's latest entry, never the hook's clock (the deriver's own
# numbers are compared event for event in tests/scripts/test-session-diagnostics.py).
if grep -q '"ts": "2026-11-04T20:55:04.349Z"' "$LOG" 2>/dev/null \
   && grep -q '"anchor": "cs:1793825684600:6908"' "$LOG" 2>/dev/null; then
    pass "ts is the resumed lifetime's latest entry and the anchor its closing cost-state"
else
    fail "ts or anchor unexpected: $(head -c 300 "$LOG" 2>/dev/null)"
fi
if grep -q "CANARY" "$LOG" 2>/dev/null; then fail "Transcript text leaked into the event"; else pass "No prompt, response or tool text in the event"; fi

# --- Test 2: a second firing on the same state appends nothing ---
before=$(cksum < "$LOG")
run_hook "$(payload_for "$PROJ")" CLAUDE_PID=4101
if [[ "$(cksum < "$LOG")" == "$before" ]]; then pass "Second firing appends nothing"; else fail "Second firing changed the ledger"; fi

# --- Test 3: raw UTF-8 bytes pass through (non-ASCII project path) ---
PROJ3="$TMPDIR_TEST/木下-proj"
make_project "$PROJ3"
run_hook "$(payload_for "$PROJ3")" CLAUDE_PID=4102 PYTHONIOENCODING=latin-1
if grep -q '"project": "木下-proj"' "$PROJ3/.council/diagnostics.jsonl" 2>/dev/null; then
    pass "Non-ASCII payload decoded as UTF-8"
else
    fail "Non-ASCII project path lost"
fi

# --- Test 4: no .council -> nothing written, nothing created ---
PROJ4="$TMPDIR_TEST/proj4"
make_project "$PROJ4" none
run_hook "$(payload_for "$PROJ4")" >/dev/null 2>&1
if [[ ! -e "$PROJ4/.council" ]]; then pass "No .council: nothing created"; else fail "Phantom .council created"; fi

# --- Test 5: empty stdin fails open ---
if printf '' | bash "$REPO/$HOOK"; then pass "Empty payload exits 0"; else fail "Empty payload should exit 0"; fi

# --- Test 6: crew guard — with AUTOMATE_RUN set no council hook writes anything ---
PROJ6="$TMPDIR_TEST/proj6"
make_project "$PROJ6"
: > "$PROJ6/.council/diagnostics.jsonl"
state_before=$(cd "$PROJ6" && find . -print0 | sort -z | xargs -0 cksum 2>/dev/null | cksum)
run_hook "$(payload_for "$PROJ6")" AUTOMATE_RUN=1 CLAUDE_PID=4106
run_hook "$(payload_for "$PROJ6" clear)" AUTOMATE_RUN=1 CLAUDE_PID=4106
tool_payload='{"tool_name":"Read","tool_input":{"file_path":"README.md"},"cwd":"'"$PROJ6"'","session_id":"s6","tool_use_id":"t6"}'
( unset CLAUDE_PROJECT_DIR AUDIT_LOG_PATH; printf '%s' "$tool_payload" | AUTOMATE_RUN=1 bash "$REPO/hooks/log-tool-call.sh" )
( unset SESSION_MARKER_PATH COUNCIL_PROGRESS_FILE; cd "$PROJ6" && printf '{}' | CLAUDE_PROJECT_DIR="$PROJ6" AUTOMATE_RUN=1 bash "$REPO/hooks/session-stopped-marker.sh" )
state_after=$(cd "$PROJ6" && find . -print0 | sort -z | xargs -0 cksum 2>/dev/null | cksum)
if [[ "$state_before" == "$state_after" ]]; then
    pass "Crew guard: SessionEnd, PostToolUse and Stop hooks leave .council/ and the worktree unchanged"
else
    fail "Crew guard: a hook wrote under $PROJ6 with AUTOMATE_RUN set"
fi

echo ""
if (( ERRORS == 0 )); then echo "ALL TESTS PASSED"; exit 0; else echo "${ERRORS} TEST(S) FAILED"; exit 1; fi
