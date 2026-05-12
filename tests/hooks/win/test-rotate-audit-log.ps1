# Fixture test for scripts/rotate-audit-log.py (PowerShell version)
# Verifies: archive produced, SHA-256 matches, source reset, DEC entry emitted, idempotent.
# Exit 0 = all tests passed.
# Requires PowerShell 7+ (pwsh) and Python 3.

$ErrorActionPreference = 'Continue'
$Errors = 0

function Pass([string]$msg) { Write-Host "PASS: $msg" }
function Fail([string]$msg) { Write-Host "FAIL: $msg"; $script:Errors++ }

# Create temp dir
$TempDir = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), [System.IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
$AuditLog = Join-Path $TempDir 'audit-log.jsonl'
$DecisionLog = Join-Path $TempDir 'decision-log.jsonl'
$Threshold = 100

# Create fake audit log above threshold.
# NOTE: must PIPE the here-string into `python -`, not pass it as a positional argument.
# `python - args @'script'@` would put the script in argv[4] and python would read empty
# stdin (silent no-op exit 0). The `@'...'@ | python - args` form pipes the script via stdin.
@'
import pathlib, sys, json
audit_log = pathlib.Path(sys.argv[1])
threshold = int(sys.argv[2])
content = ""
while len(content.encode("utf-8")) <= threshold + 10:
    content += json.dumps({"entry_id": "AUD-001", "timestamp": "2026-01-01T00:00:00Z",
                           "event_type": "tool-call", "agent_id": "test"}) + "\n"
audit_log.write_text(content, encoding="utf-8")
print(f"Created {audit_log} ({len(content)} bytes)")
'@ | python - $AuditLog $Threshold

if (-not (Test-Path $AuditLog)) {
    Fail "Failed to create test audit log"
    Remove-Item -Recurse -Force $TempDir
    exit 1
}

# Run rotation
python scripts/rotate-audit-log.py --file $AuditLog --threshold-bytes $Threshold --decision-output $DecisionLog
$rotateExit = $LASTEXITCODE

if ($rotateExit -eq 0) { Pass "rotate-audit-log.py exited 0" }
else { Fail "rotate-audit-log.py exited $rotateExit" }

# Check archive created
$archives = Get-ChildItem $TempDir -Filter 'audit-log.*.jsonl.gz' 2>$null
if ($archives.Count -ge 1) {
    Pass "Archive file created"
    $ArchiveFile = $archives[0].FullName
} else {
    Fail "No archive file found in $TempDir"
    $ArchiveFile = $null
}

# Check source file is empty
if (Test-Path $AuditLog) {
    $currentSize = (Get-Item $AuditLog).Length
    if ($currentSize -eq 0) { Pass "Source audit log is now empty" }
    else { Fail "Source audit log should be empty, but is $currentSize bytes" }
} else {
    Fail "Source audit log no longer exists (should be truncated, not deleted)"
}

# Check DEC entry was appended
if (Test-Path $DecisionLog) {
    $decContent = Get-Content $DecisionLog -Raw
    if ($decContent -match '"audit-log-rotation"') {
        Pass "DEC entry with decision_type=audit-log-rotation found"
    } else {
        Fail "DEC entry with decision_type=audit-log-rotation not found"
    }
} else {
    Fail "Decision log was not created at $DecisionLog"
}

# Check SHA-256 matches (pipe here-string into `python -` — see note above)
if ($null -ne $ArchiveFile -and (Test-Path $ArchiveFile) -and (Test-Path $DecisionLog)) {
    @'
import hashlib, json, pathlib, sys
archive_path = pathlib.Path(sys.argv[1])
decision_log_path = pathlib.Path(sys.argv[2])
h = hashlib.sha256()
with archive_path.open("rb") as f:
    for chunk in iter(lambda: f.read(65536), b""):
        h.update(chunk)
expected = h.hexdigest()
lines = [l.strip() for l in decision_log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
last = json.loads(lines[-1])
desc = last.get("description", "")
if isinstance(desc, str):
    try:
        desc = json.loads(desc)
    except Exception:
        desc = {}
recorded = desc.get("sha256_archive", "") if isinstance(desc, dict) else ""
if recorded == expected:
    print(f"SHA-256 MATCHES: {expected}")
    sys.exit(0)
else:
    print(f"SHA-256 MISMATCH: expected={expected}, recorded={recorded}")
    sys.exit(1)
'@ | python - $ArchiveFile $DecisionLog
    if ($LASTEXITCODE -eq 0) { Pass "SHA-256 in DEC entry matches archive file" }
    else { Fail "SHA-256 mismatch between DEC entry and archive file" }
}

# Idempotency: second run with empty file (below threshold) should exit 0 with no new archive
$archiveCountBefore = (Get-ChildItem $TempDir -Filter 'audit-log.*.jsonl.gz' 2>$null).Count
python scripts/rotate-audit-log.py --file $AuditLog --threshold-bytes $Threshold --decision-output $DecisionLog
$idempotentExit = $LASTEXITCODE
$archiveCountAfter = (Get-ChildItem $TempDir -Filter 'audit-log.*.jsonl.gz' 2>$null).Count

if ($idempotentExit -eq 0) { Pass "Second run (idempotent) exited 0" }
else { Fail "Second run (idempotent) exited $idempotentExit" }

if ($archiveCountAfter -eq $archiveCountBefore) { Pass "No new archive created on idempotent run" }
else { Fail "New archive created on idempotent run (expected $archiveCountBefore, got $archiveCountAfter)" }

# --- Cleanup ---
Remove-Item -Recurse -Force $TempDir

# --- Results ---
Write-Host ""
if ($Errors -eq 0) {
    Write-Host "ALL TESTS PASSED"
    exit 0
} else {
    Write-Host "$Errors TEST(S) FAILED"
    exit 1
}
