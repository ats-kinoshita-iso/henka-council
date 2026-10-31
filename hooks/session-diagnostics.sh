#!/usr/bin/env bash
# SessionEnd hook — thin wrapper. The logic lives in scripts/session-diagnostics.py
# so the bash and PowerShell hooks share one implementation (parity, v2.1 A7).
# Appends one diagnostic event per session to <root>/.council/diagnostics.jsonl.
# Exit 0 always: diagnostics must never block or fail a session.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then py=python3
elif command -v python >/dev/null 2>&1; then py=python
else exit 0; fi
"$py" "$here/../scripts/session-diagnostics.py" 2>/dev/null || true
exit 0
