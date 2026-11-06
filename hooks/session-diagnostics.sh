#!/usr/bin/env bash
# SessionEnd hook — thin wrapper. The logic lives in scripts/session-diagnostics.py
# (over the deriver scripts/session_lifetimes.py) so the bash and PowerShell hooks
# share one implementation (parity, v2.1 A7). Appends one diagnostic event per
# settled process lifetime to <root>/.council/diagnostics.jsonl (ADR-0006 A1).
# The payload passes through on stdin as raw bytes; Python decodes it as UTF-8.
# Exit 0 always: diagnostics must never block or fail a session.
set -uo pipefail
# Crew guard (ADR-0006 A1 D1.9): auto-mate commits a crew's leftovers, so with
# AUTOMATE_RUN set the council writes nothing.
if [[ -n "${AUTOMATE_RUN:-}" ]]; then exit 0; fi
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
py=()
case "$(uname -s 2>/dev/null)" in
    # Git Bash on Windows: prefer the launcher; the Store "python" alias can hang.
    MINGW*|MSYS*|CYGWIN*) if command -v py >/dev/null 2>&1; then py=(py -3); fi ;;
esac
if (( ${#py[@]} == 0 )); then
    if command -v python3 >/dev/null 2>&1; then py=(python3)
    elif command -v python >/dev/null 2>&1; then py=(python)
    else exit 0; fi
fi
"${py[@]}" "$here/../scripts/session-diagnostics.py" 2>/dev/null || true
exit 0
