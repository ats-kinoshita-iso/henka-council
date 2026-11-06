# Fixture test for hooks/win/session-diagnostics.ps1 (the PowerShell wrapper). Parity twin:
# tests/hooks/test-session-diagnostics.sh. The deriver itself is covered cross-platform by
# tests/scripts/test-session-diagnostics.py; this test proves the wrapper passes the payload
# through as raw bytes, writes one event per settled lifetime, appends nothing on a second
# firing, fails open, and that with AUTOMATE_RUN set no council writing hook writes anything.
# Requires PowerShell 7+ (pwsh) and Python on PATH.
$ErrorActionPreference = 'Continue'
$Errors = 0
function Pass([string]$msg) { Write-Host "PASS: $msg" }
function Fail([string]$msg) { Write-Host "FAIL: $msg"; $script:Errors++ }

$Repo = (Get-Location).Path
$Hook = Join-Path $Repo 'hooks/win/session-diagnostics.ps1'
$Session = '00000000-0000-4000-8000-000000000001'
$Transcript = (Join-Path $Repo "tests/fixtures/transcripts/p05-fork-subagent/projects/-work-proj/$Session.jsonl") -replace '\\', '/'
$TempDir = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), [System.IO.Path]::GetRandomFileName())
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

function New-Project([string]$Path, [bool]$Council = $true) {
    New-Item -ItemType Directory -Path (Join-Path $Path '.git') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $Path '.harness') -Force | Out-Null
    Set-Content -Path (Join-Path $Path '.harness/sprint-state.json') -Value '{"current_sprint": 9, "current_phase": 2}' -Encoding utf8NoBOM
    if ($Council) { New-Item -ItemType Directory -Path (Join-Path $Path '.council') -Force | Out-Null }
}

function Get-Payload([string]$Cwd, [string]$Reason = 'other') {
    $obj = [ordered]@{
        session_id      = $Session
        transcript_path = $Transcript
        cwd             = ($Cwd -replace '\\', '/')
        hook_event_name = 'SessionEnd'
        reason          = $Reason
    }
    return ($obj | ConvertTo-Json -Compress)
}

# Runs one hook script with a clean set of the variables the hooks read, then restores them.
function Invoke-Hook([string]$Script, [string]$Payload, [hashtable]$Vars = @{}) {
    $names = @('CLAUDE_PROJECT_DIR', 'DIAGNOSTICS_LOG_PATH', 'AUTOMATE_RUN', 'CLAUDE_PID', 'AUDIT_LOG_PATH',
               'SESSION_MARKER_PATH', 'COUNCIL_PROGRESS_FILE') + @($Vars.Keys)
    $saved = @{}
    foreach ($n in ($names | Select-Object -Unique)) {
        $saved[$n] = [Environment]::GetEnvironmentVariable($n)
        [Environment]::SetEnvironmentVariable($n, $null)
    }
    foreach ($k in $Vars.Keys) { [Environment]::SetEnvironmentVariable($k, [string]$Vars[$k]) }
    $Payload | pwsh -NoLogo -NoProfile -File $Script | Out-Null
    $code = $LASTEXITCODE
    foreach ($n in $saved.Keys) { [Environment]::SetEnvironmentVariable($n, $saved[$n]) }
    return $code
}

function Get-TreeState([string]$Path) {
    $items = Get-ChildItem -Path $Path -Recurse -Force | Sort-Object FullName
    return ($items | ForEach-Object {
        if ($_.PSIsContainer) { "$($_.FullName)|dir" } else { "$($_.FullName)|$((Get-FileHash -Path $_.FullName -Algorithm SHA256).Hash)" }
    }) -join "`n"
}

# --- Test 1: the closing lifetime becomes one schema 1.1 event ---
$Proj = Join-Path $TempDir 'proj'
New-Project $Proj
$code = Invoke-Hook $Hook (Get-Payload (Join-Path $Proj 'sub/dir')) @{ CLAUDE_PID = '4101' }
if ($code -eq 0) { Pass 'Wrapper exits 0' } else { Fail "Wrapper exited $code" }
$Log = Join-Path $Proj '.council/diagnostics.jsonl'
$lines = @()
if (Test-Path $Log) { $lines = @(Get-Content $Log -Encoding utf8 | Where-Object { $_.Trim() -ne '' }) }
if ($lines.Count -eq 1) { Pass 'Exactly one event written' } else { Fail "Expected one event, got $($lines.Count)" }
if ($lines.Count -ge 1 -and $lines[0] -match '"schema_version": "1.1"' -and $lines[0] -match '"kind": "session"' `
    -and $lines[0] -match '"start_source": "resume"' -and $lines[0] -match '"phase": 2') {
    Pass "Event is the resumed lifetime's schema 1.1 session event, with the phase"
} else {
    Fail 'Event content unexpected'
}
if ($lines.Count -ge 1 -and $lines[0] -match 'CANARY') { Fail 'Transcript text leaked into the event' } else { Pass 'No prompt, response or tool text in the event' }

# --- Test 2: a second firing on the same state appends nothing ---
$before = (Get-FileHash -Path $Log -Algorithm SHA256).Hash
Invoke-Hook $Hook (Get-Payload $Proj) @{ CLAUDE_PID = '4101' } | Out-Null
if ((Get-FileHash -Path $Log -Algorithm SHA256).Hash -eq $before) { Pass 'Second firing appends nothing' } else { Fail 'Second firing changed the ledger' }

# --- Test 3: raw UTF-8 bytes pass through (non-ASCII project path) ---
$Proj3 = Join-Path $TempDir ([string]::Concat([char]0x6728, [char]0x4E0B, '-proj'))
New-Project $Proj3
Invoke-Hook $Hook (Get-Payload $Proj3) @{ CLAUDE_PID = '4102' } | Out-Null
$Log3 = Join-Path $Proj3 '.council/diagnostics.jsonl'
$expectedProject = '"project": "' + (Split-Path $Proj3 -Leaf) + '"'
if ((Test-Path $Log3) -and ((Get-Content $Log3 -Raw -Encoding utf8).Contains($expectedProject))) {
    Pass 'Non-ASCII payload decoded as UTF-8'
} else {
    Fail 'Non-ASCII project path lost'
}

# --- Test 4: no .council -> nothing written, nothing created ---
$Proj4 = Join-Path $TempDir 'proj4'
New-Project $Proj4 $false
Invoke-Hook $Hook (Get-Payload $Proj4) | Out-Null
if (-not (Test-Path (Join-Path $Proj4 '.council'))) { Pass 'No .council: nothing created' } else { Fail 'Phantom .council created' }

# --- Test 5: empty stdin fails open ---
$code = Invoke-Hook $Hook ''
if ($code -eq 0) { Pass 'Empty payload exits 0' } else { Fail 'Empty payload should exit 0' }

# --- Test 6: crew guard — with AUTOMATE_RUN set no council hook writes anything ---
$Proj6 = Join-Path $TempDir 'proj6'
New-Project $Proj6
New-Item -ItemType File -Path (Join-Path $Proj6 '.council/diagnostics.jsonl') -Force | Out-Null
$stateBefore = Get-TreeState $Proj6
Invoke-Hook $Hook (Get-Payload $Proj6) @{ AUTOMATE_RUN = '1'; CLAUDE_PID = '4106' } | Out-Null
Invoke-Hook $Hook (Get-Payload $Proj6 'clear') @{ AUTOMATE_RUN = '1'; CLAUDE_PID = '4106' } | Out-Null
$toolPayload = ([ordered]@{ tool_name = 'Read'; tool_input = @{ file_path = 'README.md' }; cwd = ($Proj6 -replace '\\', '/'); session_id = 's6'; tool_use_id = 't6' } | ConvertTo-Json -Compress)
Invoke-Hook (Join-Path $Repo 'hooks/win/log-tool-call.ps1') $toolPayload @{ AUTOMATE_RUN = '1' } | Out-Null
Invoke-Hook (Join-Path $Repo 'hooks/win/session-stopped-marker.ps1') '{}' @{ AUTOMATE_RUN = '1'; CLAUDE_PROJECT_DIR = $Proj6 } | Out-Null
if ((Get-TreeState $Proj6) -eq $stateBefore) {
    Pass 'Crew guard: SessionEnd, PostToolUse and Stop hooks leave .council/ and the worktree unchanged'
} else {
    Fail "Crew guard: a hook wrote under $Proj6 with AUTOMATE_RUN set"
}

Remove-Item -Recurse -Force $TempDir
Write-Host ""
if ($Errors -eq 0) { Write-Host "ALL TESTS PASSED"; exit 0 } else { Write-Host "$Errors TEST(S) FAILED"; exit 1 }
