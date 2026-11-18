#!/usr/bin/env bash
# PostToolUse hook — thin wrapper. The logic lives in scripts/log-tool-call.py so
# the bash and PowerShell hooks share one implementation (parity, v2.1 A7).
# Reads the native hook payload on stdin and passes it through unchanged.
# Exit 0 always: an audit logger must never block or fail a session.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then py=python3
elif command -v python >/dev/null 2>&1; then py=python
else echo "log-tool-call: python not found — audit logging skipped" >&2; exit 0; fi
"$py" "$here/../scripts/log-tool-call.py" 2>/dev/null || true
exit 0
