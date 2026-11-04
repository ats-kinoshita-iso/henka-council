# Fixture test for hooks/win/enforce-reversibility.ps1
# Tests ALLOW (exit 0) and BLOCK (exit 2) paths with temp state file. Claude Code
# blocks a PreToolUse call only on exit 2; any other non-zero code lets the command run.
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
    # Pipeline + $LASTEXITCODE must be two statements; PowerShell rejects
    # `(pipeline; $LASTEXITCODE)` as a single grouping expression.
    $envelopeJson | pwsh -NoLogo -NoProfile -File 'hooks/win/enforce-reversibility.ps1'
    $code = $LASTEXITCODE
    $env:EFFECTIVE_AUTONOMY_PATH = $null
    return $code
}

# --- BLOCK cases ---

$envelope = '{"tool_name":"Bash","tool_args":{"command":"git push origin main"},"cwd":"/tmp","session_id":"test"}'
Write-Autonomy 3
$env:EFFECTIVE_AUTONOMY_PATH = $AutonomyFile
$envelope | pwsh -NoLogo -NoProfile -File 'hooks/win/enforce-reversibility.ps1' | Out-Null
if ($LASTEXITCODE -eq 2) { Pass "git push at level=3 is blocked" }
else { Fail "git push at level=3 should be blocked" }
$env:EFFECTIVE_AUTONOMY_PATH = $null

$envelope = '{"tool_name":"Bash","tool_args":{"command":"git reset --hard HEAD~1"},"cwd":"/tmp","session_id":"test"}'
Write-Autonomy 3
$env:EFFECTIVE_AUTONOMY_PATH = $AutonomyFile
$envelope | pwsh -NoLogo -NoProfile -File 'hooks/win/enforce-reversibility.ps1' | Out-Null
if ($LASTEXITCODE -eq 2) { Pass "git reset --hard at level=3 is blocked" }
else { Fail "git reset --hard at level=3 should be blocked" }
$env:EFFECTIVE_AUTONOMY_PATH = $null

$envelope = '{"tool_name":"Bash","tool_args":{"command":"rm -rf /tmp/foo"},"cwd":"/tmp","session_id":"test"}'
Write-Autonomy 4
$env:EFFECTIVE_AUTONOMY_PATH = $AutonomyFile
$envelope | pwsh -NoLogo -NoProfile -File 'hooks/win/enforce-reversibility.ps1' | Out-Null
if ($LASTEXITCODE -eq 2) { Pass "rm -rf at level=4 is blocked" }
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


# Native payloads recorded from Claude Code (tests/fixtures/payloads/pretooluse-native.jsonl).
# Each case changes only the target path, the command, the cwd or the tool name, so the
# field names are the ones Claude Code really sends (tool_input, never tool_args).
$Fixture = 'tests/fixtures/payloads/pretooluse-native.jsonl'
function New-NativePayload([string]$tool, [hashtable]$set) {
    $record = Get-Content $Fixture | ForEach-Object { $_ | ConvertFrom-Json } | Where-Object { $_.tool_name -eq $tool } | Select-Object -First 1
    foreach ($key in $set.Keys) {
        switch ($key) {
            'file_path' { $record.tool_input | Add-Member -NotePropertyName file_path -NotePropertyValue $set[$key] -Force }
            'command'   { $record.tool_input | Add-Member -NotePropertyName command -NotePropertyValue $set[$key] -Force }
            'cwd'       { $record.cwd = $set[$key] }
            'tool_name' { $record.tool_name = $set[$key] }
        }
    }
    return ($record | ConvertTo-Json -Compress -Depth 10)
}

function Invoke-Native([string]$json, [int]$level) {
    Write-Autonomy $level
    $env:EFFECTIVE_AUTONOMY_PATH = $AutonomyFile
    $json | pwsh -NoLogo -NoProfile -File 'hooks/win/enforce-reversibility.ps1' | Out-Null
    $code = $LASTEXITCODE
    $env:EFFECTIVE_AUTONOMY_PATH = $null
    return $code
}

# --- Native payloads: BLOCK (exit 2) and ALLOW (exit 0) ---
$code = Invoke-Native (New-NativePayload 'Bash' @{ command = 'git push origin main' }) 3
if ($code -eq 2) { Pass "native git push at level=3 is blocked (exit 2)" }
else { Fail "native git push at level=3 should exit 2 (exit was $code)" }
$code = Invoke-Native (New-NativePayload 'Bash' @{ command = 'rm -rf build' }) 4
if ($code -eq 2) { Pass "native rm -rf at level=4 is blocked (exit 2)" }
else { Fail "native rm -rf at level=4 should exit 2 (exit was $code)" }
$code = Invoke-Native (New-NativePayload 'Bash' @{ command = 'git push origin main' }) 5
if ($code -eq 0) { Pass "native git push at level=5 is allowed" }
else { Fail "native git push at level=5 should be allowed (exit was $code)" }
$code = Invoke-Native (New-NativePayload 'Bash' @{}) 4
if ($code -eq 0) { Pass "recorded Bash call (ls) at level=4 is allowed" }
else { Fail "recorded Bash call at level=4 should be allowed (exit was $code)" }

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
