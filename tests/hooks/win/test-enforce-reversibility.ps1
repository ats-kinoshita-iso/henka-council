# Fixture test for hooks/win/enforce-reversibility.ps1
# Tests ALLOW and BLOCK paths with temp state file.
# Exit 0 = all tests passed.
# Requires PowerShell 7+ (pwsh).

$ErrorActionPreference = 'Continue'
$Errors = 0

function Pass([string]$msg) { Write-Host "PASS: $msg" }
function Fail([string]$msg) { Write-Host "FAIL: $msg"; $script:Errors++ }

# Create temp dir for state files
$TempDir = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), [System.IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
$AutonomyFile = Join-Path $TempDir 'effective-autonomy.json'

function Write-Autonomy([int]$level) {
    $content = @{
        level       = $level
        last_change = '2026-01-01T00:00:00Z'
        reason      = 'test'
    } | ConvertTo-Json -Compress
    Set-Content -Path $AutonomyFile -Value $content -Encoding UTF8
}

function Invoke-HookWithLevel([string]$envelopeJson, [int]$level) {
    Write-Autonomy $level
    $env:EFFECTIVE_AUTONOMY_PATH = $AutonomyFile
    $code = ($envelopeJson | pwsh -NoLogo -NoProfile -File 'hooks/win/enforce-reversibility.ps1'; $LASTEXITCODE)
    $env:EFFECTIVE_AUTONOMY_PATH = $null
    return $LASTEXITCODE
}

# --- BLOCK cases ---

$envelope = '{"tool_name":"Bash","tool_args":{"command":"git push origin main"},"cwd":"/tmp","session_id":"test"}'
Write-Autonomy 3
$env:EFFECTIVE_AUTONOMY_PATH = $AutonomyFile
$envelope | pwsh -NoLogo -NoProfile -File 'hooks/win/enforce-reversibility.ps1' | Out-Null
if ($LASTEXITCODE -ne 0) { Pass "git push at level=3 is blocked" }
else { Fail "git push at level=3 should be blocked" }
$env:EFFECTIVE_AUTONOMY_PATH = $null

$envelope = '{"tool_name":"Bash","tool_args":{"command":"git reset --hard HEAD~1"},"cwd":"/tmp","session_id":"test"}'
Write-Autonomy 3
$env:EFFECTIVE_AUTONOMY_PATH = $AutonomyFile
$envelope | pwsh -NoLogo -NoProfile -File 'hooks/win/enforce-reversibility.ps1' | Out-Null
if ($LASTEXITCODE -ne 0) { Pass "git reset --hard at level=3 is blocked" }
else { Fail "git reset --hard at level=3 should be blocked" }
$env:EFFECTIVE_AUTONOMY_PATH = $null

$envelope = '{"tool_name":"Bash","tool_args":{"command":"rm -rf /tmp/foo"},"cwd":"/tmp","session_id":"test"}'
Write-Autonomy 4
$env:EFFECTIVE_AUTONOMY_PATH = $AutonomyFile
$envelope | pwsh -NoLogo -NoProfile -File 'hooks/win/enforce-reversibility.ps1' | Out-Null
if ($LASTEXITCODE -ne 0) { Pass "rm -rf at level=4 is blocked" }
else { Fail "rm -rf at level=4 should be blocked" }
$env:EFFECTIVE_AUTONOMY_PATH = $null

# --- ALLOW cases ---

$envelope = '{"tool_name":"Bash","tool_args":{"command":"git push origin main"},"cwd":"/tmp","session_id":"test"}'
Write-Autonomy 5
$env:EFFECTIVE_AUTONOMY_PATH = $AutonomyFile
$envelope | pwsh -NoLogo -NoProfile -File 'hooks/win/enforce-reversibility.ps1' | Out-Null
if ($LASTEXITCODE -eq 0) { Pass "git push at level=5 is allowed" }
else { Fail "git push at level=5 should be allowed" }
$env:EFFECTIVE_AUTONOMY_PATH = $null

$envelope = '{"tool_name":"Bash","tool_args":{"command":"ls -la"},"cwd":"/tmp","session_id":"test"}'
Write-Autonomy 3
$env:EFFECTIVE_AUTONOMY_PATH = $AutonomyFile
$envelope | pwsh -NoLogo -NoProfile -File 'hooks/win/enforce-reversibility.ps1' | Out-Null
if ($LASTEXITCODE -eq 0) { Pass "ls at level=3 is allowed" }
else { Fail "ls at level=3 should be allowed" }
$env:EFFECTIVE_AUTONOMY_PATH = $null

# Write tool (non-Bash) must always be allowed regardless of level
$envelope = '{"tool_name":"Write","tool_args":{"file_path":"foo.txt"},"cwd":"/tmp","session_id":"test"}'
Write-Autonomy 1
$env:EFFECTIVE_AUTONOMY_PATH = $AutonomyFile
$envelope | pwsh -NoLogo -NoProfile -File 'hooks/win/enforce-reversibility.ps1' | Out-Null
if ($LASTEXITCODE -eq 0) { Pass "Write tool at level=1 is allowed (non-Bash)" }
else { Fail "Write tool should always be allowed (non-Bash)" }
$env:EFFECTIVE_AUTONOMY_PATH = $null

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
