#!/usr/bin/env bash
# Bash fixture test for scripts/rotate-audit-log.py
# Verifies: archive produced, SHA-256 matches, source reset, DEC entry emitted, idempotent.
# Exit 0 = all tests passed.

set -uo pipefail

ERRORS=0

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; ERRORS=$(( ERRORS + 1 )); }

# Create isolated temp dir
TMPDIR_TEST=$(mktemp -d)
AUDIT_LOG="${TMPDIR_TEST}/audit-log.jsonl"
DECISION_LOG="${TMPDIR_TEST}/decision-log.jsonl"
THRESHOLD=100  # small threshold for testing

cleanup() {
    rm -rf "$TMPDIR_TEST"
}
trap cleanup EXIT

# Create a fake audit log above the threshold (200 bytes of data)
python3 - "$AUDIT_LOG" "$THRESHOLD" <<'PYEOF'
import pathlib, sys, json
audit_log = pathlib.Path(sys.argv[1])
threshold = int(sys.argv[2])
# Write enough lines to exceed threshold
content = ""
while len(content.encode("utf-8")) <= threshold + 10:
    content += json.dumps({"entry_id": "AUD-001", "timestamp": "2026-01-01T00:00:00Z",
                           "event_type": "tool-call", "agent_id": "test"}) + "\n"
audit_log.write_text(content, encoding="utf-8")
print(f"Created {audit_log} ({len(content)} bytes)")
PYEOF

if [[ ! -f "$AUDIT_LOG" ]]; then
    fail "Failed to create test audit log"
    exit 1
fi

original_size=$(wc -c < "$AUDIT_LOG")
echo "Original audit log size: ${original_size} bytes (threshold: ${THRESHOLD})"

# Run rotation
python3 scripts/rotate-audit-log.py \
    --file "$AUDIT_LOG" \
    --threshold-bytes "$THRESHOLD" \
    --decision-output "$DECISION_LOG"
rotate_exit=$?

if (( rotate_exit == 0 )); then
    pass "rotate-audit-log.py exited 0"
else
    fail "rotate-audit-log.py exited ${rotate_exit}"
fi

# Check: archive was created
archive_count=$(ls "${TMPDIR_TEST}"/audit-log.*.jsonl.gz 2>/dev/null | wc -l)
if (( archive_count >= 1 )); then
    pass "Archive file created"
    ARCHIVE_FILE=$(ls "${TMPDIR_TEST}"/audit-log.*.jsonl.gz | head -1)
else
    fail "No archive file found in ${TMPDIR_TEST}"
    ARCHIVE_FILE=""
fi

# Check: source file is now empty
if [[ -f "$AUDIT_LOG" ]]; then
    current_size=$(wc -c < "$AUDIT_LOG")
    if (( current_size == 0 )); then
        pass "Source audit log is now empty"
    else
        fail "Source audit log should be empty, but is ${current_size} bytes"
    fi
else
    fail "Source audit log no longer exists (should be truncated, not deleted)"
fi

# Check: DEC entry was appended to decision log
if [[ -f "$DECISION_LOG" ]]; then
    dec_lines=$(grep -c '"decision_type".*"audit-log-rotation"' "$DECISION_LOG" 2>/dev/null || echo "0")
    if (( dec_lines >= 1 )); then
        pass "DEC entry with decision_type=audit-log-rotation found"
    else
        fail "DEC entry with decision_type=audit-log-rotation not found in ${DECISION_LOG}"
    fi
else
    fail "Decision log was not created at ${DECISION_LOG}"
fi

# Check: SHA-256 in DEC entry matches archive file
if [[ -n "$ARCHIVE_FILE" ]] && [[ -f "$DECISION_LOG" ]]; then
    python3 - "$ARCHIVE_FILE" "$DECISION_LOG" <<'PYEOF'
import hashlib, json, pathlib, sys

archive_path = pathlib.Path(sys.argv[1])
decision_log_path = pathlib.Path(sys.argv[2])

# Compute SHA-256 of the archive file
h = hashlib.sha256()
with archive_path.open("rb") as f:
    for chunk in iter(lambda: f.read(65536), b""):
        h.update(chunk)
expected_sha256 = h.hexdigest()

# Read last DEC entry from decision log
lines = [l.strip() for l in decision_log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
last_entry = json.loads(lines[-1])

# DEC description contains the sha256_archive
desc = last_entry.get("description", "")
if isinstance(desc, str):
    try:
        desc_obj = json.loads(desc)
        recorded_sha256 = desc_obj.get("sha256_archive", "")
    except json.JSONDecodeError:
        recorded_sha256 = ""
else:
    recorded_sha256 = desc.get("sha256_archive", "")

if recorded_sha256 == expected_sha256:
    print(f"SHA-256 MATCHES: {expected_sha256}")
    sys.exit(0)
else:
    print(f"SHA-256 MISMATCH: expected={expected_sha256}, recorded={recorded_sha256}")
    sys.exit(1)
PYEOF
    sha_exit=$?
    if (( sha_exit == 0 )); then
        pass "SHA-256 in DEC entry matches archive file"
    else
        fail "SHA-256 mismatch between DEC entry and archive file"
    fi
fi

# Check: Idempotency — run again with same threshold (file is now empty = below threshold)
python3 scripts/rotate-audit-log.py \
    --file "$AUDIT_LOG" \
    --threshold-bytes "$THRESHOLD" \
    --decision-output "$DECISION_LOG"
idempotent_exit=$?

if (( idempotent_exit == 0 )); then
    pass "Second run (idempotent) exited 0"
else
    fail "Second run (idempotent) exited ${idempotent_exit}"
fi

# Verify no new archive was created
new_archive_count=$(ls "${TMPDIR_TEST}"/audit-log.*.jsonl.gz 2>/dev/null | wc -l)
if (( new_archive_count == archive_count )); then
    pass "No new archive created on idempotent run"
else
    fail "New archive created on idempotent run (expected ${archive_count}, got ${new_archive_count})"
fi

# --- Results ---
echo ""
if (( ERRORS == 0 )); then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "${ERRORS} TEST(S) FAILED"
    exit 1
fi
