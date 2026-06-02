#!/usr/bin/env bash
# Stop hook — append a SESSION_STOPPED marker to progress.md.
# Reads (or ignores) any envelope from stdin.
# Exit 0 always (stop hooks cannot block).

set -uo pipefail

# Env-var override for testability; also accept legacy COUNCIL_PROGRESS_FILE.
# The default path is anchored to the project root below to avoid a nested
# .council/.harness/progress.md when the session cwd is a subdirectory (issue #18).
TARGET_FILE="${SESSION_MARKER_PATH:-${COUNCIL_PROGRESS_FILE:-}}"

# Resolve the project root for anchoring the progress-marker path.
# Priority: CLAUDE_PROJECT_DIR (set by Claude Code at hook-fire time) ->
# nearest ancestor of $PWD containing a .git marker -> $PWD.
_council_project_root() {
    local start="${1:-$PWD}" dir parent
    if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
        printf '%s' "${CLAUDE_PROJECT_DIR%/}"
        return 0
    fi
    dir="${start%/}"
    while [[ -n "$dir" && "$dir" != "/" ]]; do
        if [[ -e "$dir/.git" ]]; then
            printf '%s' "$dir"
            return 0
        fi
        parent=$(dirname "$dir")
        [[ "$parent" == "$dir" ]] && break
        dir="$parent"
    done
    printf '%s' "${start%/}"
}

# Read and discard stdin (Claude Code may send a minimal envelope)
cat > /dev/null 2>&1 || true

# Anchor the progress-marker path to the project root unless an explicit override was given.
if [[ -z "$TARGET_FILE" ]]; then
    TARGET_FILE="$(_council_project_root)/.harness/progress.md"
fi

# Generate UTC timestamp
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "1970-01-01T00:00:00Z")

# Ensure target parent directory exists
target_dir=$(dirname "$TARGET_FILE")
if [[ "$target_dir" != "." ]] && [[ "$target_dir" != "" ]]; then
    mkdir -p "$target_dir" 2>/dev/null || true
fi

# Append marker. Format matches the legacy mixed-case "Stopped." prose used
# throughout .harness/progress.md. The trailing HTML comment carries the
# SESSION_STOPPED tag so machine readers (e.g. the sprint-05 contract SC-11
# verification) can still locate session boundaries by substring match.
{
    echo ""
    echo "## Session ${timestamp}"
    echo "Stopped. Current sprint state should be committed.  <!-- SESSION_STOPPED -->"
} >> "$TARGET_FILE" 2>/dev/null || {
    echo "session-stopped-marker: failed to write to ${TARGET_FILE}" >&2
    exit 0
}

exit 0
