#!/usr/bin/env bash
# Live, opt-in SessionEnd budget canary (cloud-catcher ADR-0006 A1, Verification).
#
# Not run in CI: it starts real `claude -p` sessions and spends a little (each run is
# capped with --max-budget-usd 0.05). It checks that the installed Claude Code still
# gives a SessionEnd hook the budget the session diagnostics hook is built for: a
# hook that sleeps FITS_S (1.0 s) finishes, a hook that sleeps OVERRUNS_S (2.5 s) is
# cancelled. If either assertion fails the budget changed: revisit DEFAULT_BUDGET_S in
# scripts/_diaglib.py (about 1.0 s of deriver work) before relying on the hook. The
# deterministic half, the deriver's SessionEnd work on the heaviest recorded fixture,
# is checked by tests/scripts/test-session-diagnostics.py.
#
# Usage: CANARY_MODEL=<cheapest model id> bash tests/live/test-sessionend-budget-canary.sh
# Optional: CLAUDE_BIN (default claude), CANARY_DIR (default a fresh temp dir).
# The hook is registered in a scratch project's .claude/settings.json, so the run does
# not depend on how this plugin is installed.
set -uo pipefail
: "${CANARY_MODEL:?set CANARY_MODEL to the model id to run the probe sessions with}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
PINNED_VERSION="2.1.318"
FITS_S="1.0"
OVERRUNS_S="2.5"
WORK="${CANARY_DIR:-$(mktemp -d)}"
ERRORS=0
pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; ERRORS=$(( ERRORS + 1 )); }

version="$("$CLAUDE_BIN" --version 2>/dev/null | awk '{print $1}')"
if [[ "$version" != "$PINNED_VERSION" ]]; then
    echo "NOTE: Claude Code $version, canary pinned on $PINNED_VERSION; the result below is for $version"
fi

probe() {  # <seconds> -> prints the marker phases the hook reached
    local seconds="$1" dir="$WORK/sleep-$1" marker
    marker="$dir/marker.txt"
    mkdir -p "$dir/.claude"
    git -C "$dir" init -q 2>/dev/null || true
    cat > "$dir/.claude/settings.json" <<JSON
{"hooks": {"SessionEnd": [{"hooks": [{"type": "command",
  "command": "python3 -c \"import sys, time; open(sys.argv[1], 'a').write('start\\\\n'); time.sleep(float(sys.argv[2])); open(sys.argv[1], 'a').write('done\\\\n')\" '$marker' $seconds"}]}]}}
JSON
    ( cd "$dir" && "$CLAUDE_BIN" -p 'Reply with the single word OK.' --model "$CANARY_MODEL" \
        --max-turns 1 --max-budget-usd 0.05 >/dev/null 2>&1 )
    # A cancelled hook may still be sleeping; wait past its end before reading the marker.
    timeout "$(python3 -c "print(float('$seconds') + 1.0)")" tail -f /dev/null 2>/dev/null
    tr '\n' ' ' < "$marker" 2>/dev/null
}

fits="$(probe "$FITS_S")"
if [[ "$fits" == *start*done* ]]; then
    pass "a SessionEnd hook of ${FITS_S} s runs to the end"
else
    fail "a SessionEnd hook of ${FITS_S} s did not finish (marker: ${fits:-none}): the budget shrank"
fi
overruns="$(probe "$OVERRUNS_S")"
if [[ "$overruns" == *start* && "$overruns" != *done* ]]; then
    pass "a SessionEnd hook of ${OVERRUNS_S} s is cancelled"
else
    fail "a SessionEnd hook of ${OVERRUNS_S} s was not cancelled (marker: ${overruns:-none}): the budget grew or changed"
fi

echo ""
if (( ERRORS == 0 )); then echo "ALL TESTS PASSED"; exit 0; else echo "${ERRORS} TEST(S) FAILED"; exit 1; fi
