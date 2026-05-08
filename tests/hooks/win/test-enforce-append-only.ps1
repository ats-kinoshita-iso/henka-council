# Fixture test for hooks/win/enforce-append-only.ps1
# Tests ALLOW and BLOCK paths.
# Exit 0 = all tests passed.
# Requires PowerShell 7+ (pwsh).

$ErrorActionPreference = 'Continue'
$Errors = 0

function Pass([string]$msg) { Write-Host "PASS: $msg" }
function Fail([string]$msg) { Write-Host "FAIL: $msg"; $script:Errors++ }

function Invoke-Hook([string]$envelopeJson) {
    $result = $envelopeJson | pwsh -NoLogo -NoProfile -File 'hooks/win/enforce-append-only.ps1'
    return $LASTEXITCODE
}

# --- BLOCK cases ---

$envelope = '{"tool_name":"Write","tool_args":{"file_path":".council/henka-register.jsonl"},"cwd":"/tmp","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -ne 0) { Pass "Write on henka-register.jsonl is blocked" }
else { Fail "Write on henka-register.jsonl should be blocked (exit was 0)" }

$envelope = '{"tool_name":"Edit","tool_args":{"file_path":".council/decision-log.jsonl"},"cwd":"/tmp","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -ne 0) { Pass "Edit on decision-log.jsonl is blocked" }
else { Fail "Edit on decision-log.jsonl should be blocked" }

$envelope = '{"tool_name":"Write","tool_args":{"file_path":".council/audit-log.jsonl"},"cwd":"/tmp","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -ne 0) { Pass "Write on audit-log.jsonl is blocked" }
else { Fail "Write on audit-log.jsonl should be blocked" }

# --- ALLOW cases ---

$envelope = '{"tool_name":"Write","tool_args":{"file_path":"scripts/append-henka.py"},"cwd":"/tmp","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -eq 0) { Pass "Write on non-protected file is allowed" }
else { Fail "Write on non-protected file should be allowed (exit was $code)" }

$envelope = '{"tool_name":"Bash","tool_args":{"command":"cat .council/audit-log.jsonl"},"cwd":"/tmp","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -eq 0) { Pass "Bash tool is allowed" }
else { Fail "Bash tool should be allowed (exit was $code)" }

$envelope = '{"tool_name":"Read","tool_args":{"file_path":".council/audit-log.jsonl"},"cwd":"/tmp","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -eq 0) { Pass "Read tool is allowed" }
else { Fail "Read tool should be allowed (exit was $code)" }

# Empty envelope — fail open
$code = ('' | pwsh -NoLogo -NoProfile -File 'hooks/win/enforce-append-only.ps1'; $LASTEXITCODE)
if ($LASTEXITCODE -eq 0) { Pass "Empty envelope fails open (exit 0)" }
else { Fail "Empty envelope should fail open" }

# --- Results ---
Write-Host ""
if ($Errors -eq 0) {
    Write-Host "ALL TESTS PASSED"
    exit 0
} else {
    Write-Host "$Errors TEST(S) FAILED"
    exit 1
}
