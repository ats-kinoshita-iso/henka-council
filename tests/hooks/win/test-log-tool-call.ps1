# Fixture test for hooks/win/log-tool-call.ps1
# Tests that a valid audit entry is appended.
# Exit 0 = all tests passed.
# Requires PowerShell 7+ (pwsh).

$ErrorActionPreference = 'Continue'
$Errors = 0

function Pass([string]$msg) { Write-Host "PASS: $msg" }
function Fail([string]$msg) { Write-Host "FAIL: $msg"; $script:Errors++ }

# Create temp dir for output
$TempDir = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), [System.IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
$AuditLog = Join-Path $TempDir 'audit-log.jsonl'

# --- Test 1: Basic tool-call envelope appends a valid entry ---
$envelope = '{"tool_name":"Read","tool_args":{"file_path":"README.md"},"cwd":"/tmp","session_id":"sess-001","agent_id":"orchestrator"}'

$env:AUDIT_LOG_PATH = $AuditLog
$envelope | pwsh -NoLogo -NoProfile -File 'hooks/win/log-tool-call.ps1' | Out-Null
$hookExit = $LASTEXITCODE
$env:AUDIT_LOG_PATH = $null

if ($hookExit -eq 0) { Pass "Hook exited 0" }
else { Fail "Hook exited $hookExit (expected 0)" }

if (Test-Path $AuditLog) { Pass "Audit log file exists" }
else { Fail "Audit log file was not created at $AuditLog" }

# Validate with Python — must PIPE the here-string into `python -`, not pass it as
# a positional argument. `python - args @'script'@` would put the script in argv[4]
# and python would read empty stdin and exit 0 silently. Pipe form binds stdin correctly.
$pyResult = @'
import json, pathlib, sys

audit_log = pathlib.Path(sys.argv[1])
schema_path = pathlib.Path(sys.argv[2])

if not audit_log.exists():
    print("FAIL: audit log does not exist")
    sys.exit(1)

lines = [l.strip() for l in audit_log.read_text(encoding="utf-8").splitlines() if l.strip()]
if not lines:
    print("FAIL: audit log is empty")
    sys.exit(1)

try:
    entry = json.loads(lines[-1])
except json.JSONDecodeError as e:
    print(f"FAIL: last line is not valid JSON: {e}")
    sys.exit(1)

required = ["entry_id", "timestamp", "event_type", "agent_id"]
missing = [f for f in required if f not in entry]
if missing:
    print(f"FAIL: missing required fields: {missing}")
    sys.exit(1)

try:
    import jsonschema
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft7Validator(schema).validate(entry)
        print("Schema-valid: jsonschema validation passed")
except ImportError:
    print("jsonschema not installed - field check passed")
except Exception as e:
    print(f"FAIL: schema error: {e}")
    sys.exit(1)

print("AUDIT ENTRY VALID")
'@ | python - $AuditLog 'schemas/audit-log-entry.schema.json'

if ($LASTEXITCODE -eq 0) { Pass "Audit log entry is valid" }
else { Fail "Audit log entry validation failed" }

# --- Test 2: Empty envelope should not crash ---
$AuditLog2 = Join-Path $TempDir 'audit-log2.jsonl'
$env:AUDIT_LOG_PATH = $AuditLog2
'' | pwsh -NoLogo -NoProfile -File 'hooks/win/log-tool-call.ps1' | Out-Null
$env:AUDIT_LOG_PATH = $null
if ($LASTEXITCODE -eq 0) { Pass "Empty envelope exits 0 (fail open)" }
else { Fail "Empty envelope should exit 0" }

# --- Test 3: Path anchoring via CLAUDE_PROJECT_DIR (issue #18 misroute regression) ---
# No AUDIT_LOG_PATH override, tool-call cwd shifted into <root>/.council: the audit log
# must land at <root>/.council/audit-log.jsonl, not a nested <root>/.council/.council/.
$Proj3 = Join-Path $TempDir 'proj3'
New-Item -ItemType Directory -Path (Join-Path $Proj3 '.council') -Force | Out-Null
$envelope = '{"tool_name":"Bash","tool_args":{"command":"git status"},"cwd":"' + ($Proj3 -replace '\\','/') + '/.council","session_id":"s3","agent_id":"orchestrator"}'
$env:AUDIT_LOG_PATH = $null
$env:CLAUDE_PROJECT_DIR = $Proj3
$envelope | pwsh -NoLogo -NoProfile -File 'hooks/win/log-tool-call.ps1' | Out-Null
$env:CLAUDE_PROJECT_DIR = $null
$canonical3 = Join-Path (Join-Path $Proj3 '.council') 'audit-log.jsonl'
$nested3 = Join-Path (Join-Path $Proj3 '.council') '.council'
if ((Test-Path $canonical3) -and -not (Test-Path $nested3)) {
    Pass "Audit log anchored via CLAUDE_PROJECT_DIR (no nested .council/.council)"
} else {
    Fail "Audit log misrouted under CLAUDE_PROJECT_DIR (nested .council/.council or canonical path missing)"
}

# --- Test 4: Path anchoring via .git walk-up when CLAUDE_PROJECT_DIR is unset ---
$Proj4 = Join-Path $TempDir 'proj4'
New-Item -ItemType Directory -Path (Join-Path $Proj4 '.council') -Force | Out-Null
New-Item -ItemType File -Path (Join-Path $Proj4 '.git') -Force | Out-Null
$envelope = '{"tool_name":"Bash","tool_args":{"command":"ls"},"cwd":"' + ($Proj4 -replace '\\','/') + '/.council","session_id":"s4","agent_id":"orchestrator"}'
$env:AUDIT_LOG_PATH = $null
$env:CLAUDE_PROJECT_DIR = $null
$envelope | pwsh -NoLogo -NoProfile -File 'hooks/win/log-tool-call.ps1' | Out-Null
$canonical4 = Join-Path (Join-Path $Proj4 '.council') 'audit-log.jsonl'
$nested4 = Join-Path (Join-Path $Proj4 '.council') '.council'
if ((Test-Path $canonical4) -and -not (Test-Path $nested4)) {
    Pass "Audit log anchored via .git walk-up when CLAUDE_PROJECT_DIR unset"
} else {
    Fail "Audit log walk-up anchoring failed (nested .council/.council or canonical path missing)"
}

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
