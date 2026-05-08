#!/usr/bin/env bash
# Stop hook — append a SESSION_STOPPED marker to progress.md.
# Reads (or ignores) any envelope from stdin.
# Exit 0 always (stop hooks cannot block).

set -uo pipefail

# Env-var override for testability; also accept legacy COUNCIL_PROGRESS_FILE
TARGET_FILE="${SESSION_MARKER_PATH:-${COUNCIL_PROGRESS_FILE:-.harness/progress.md}}"

# Read and discard stdin (Claude Code may send a minimal envelope)
cat > /dev/null 2>&1 || true

# Generate UTC timestamp
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "1970-01-01T00:00:00Z")

# Ensure target parent directory exists
target_dir=$(dirname "$TARGET_FILE")
if [[ "$target_dir" != "." ]] && [[ "$target_dir" != "" ]]; then
    mkdir -p "$target_dir" 2>/dev/null || true
fi

# Append marker
{
    echo ""
    echo "## Session ${timestamp}"
    echo "SESSION_STOPPED. Current sprint state should be committed."
} >> "$TARGET_FILE" 2>/dev/null || {
    echo "session-stopped-marker: failed to write to ${TARGET_FILE}" >&2
    exit 0
}

exit 0
