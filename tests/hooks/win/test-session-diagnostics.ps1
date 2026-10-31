# Fixture test for hooks/win/session-diagnostics.ps1 (the PowerShell wrapper).
# The measurement logic is covered cross-platform by tests/scripts/test-session-diagnostics.py;
# this test proves the wrapper passes the payload through and writes one event.
# Requires PowerShell 7+ (pwsh) and python on PATH.
$ErrorActionPreference = 'Continue'
$Errors = 0
function Pass([string]$msg) { Write-Host "PASS: $msg" }
function Fail([string]$msg) { Write-Host "FAIL: $msg"; $script:Errors++ }

$TempDir = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), [System.IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
$Fixture = (Resolve-Path 'tests/fixtures/transcripts/session-fixture.jsonl').Path -replace '\\', '/'
$Log = (Join-Path $TempDir 'diagnostics.jsonl')

$payload = '{"session_id":"fixture-session-0001","transcript_path":"' + $Fixture + '","cwd":"' + ($TempDir -replace '\\', '/') + '","hook_event_name":"SessionEnd","reason":"other"}'
$env:DIAGNOSTICS_LOG_PATH = $Log
$env:CLAUDE_PROJECT_DIR = $null
$payload | pwsh -NoLogo -NoProfile -File 'hooks/win/session-diagnostics.ps1' | Out-Null
$hookExit = $LASTEXITCODE
$env:DIAGNOSTICS_LOG_PATH = $null

if ($hookExit -eq 0) { Pass "Wrapper exited 0" } else { Fail "Wrapper exited $hookExit" }
if (Test-Path $Log) {
    $lines = @(Get-Content $Log | Where-Object { $_.Trim() -ne '' })
    if ($lines.Count -eq 1) { Pass "Exactly one event written" } else { Fail "Expected one event, got $($lines.Count)" }
    if ($lines[0] -match '"kind": "session"') { Pass "Event is a session event" } else { Fail "Event kind unexpected" }
    if ($lines[0] -match 'PROMPT-CANARY-7731') { Fail "Prompt text leaked into the event" } else { Pass "No prompt text in the event" }
} else {
    Fail "No diagnostics log written at $Log"
}

'' | pwsh -NoLogo -NoProfile -File 'hooks/win/session-diagnostics.ps1' | Out-Null
if ($LASTEXITCODE -eq 0) { Pass "Empty payload exits 0" } else { Fail "Empty payload should exit 0" }

Remove-Item -Recurse -Force $TempDir
Write-Host ""
if ($Errors -eq 0) { Write-Host "ALL TESTS PASSED"; exit 0 } else { Write-Host "$Errors TEST(S) FAILED"; exit 1 }
