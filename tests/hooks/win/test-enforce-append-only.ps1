# Fixture test for hooks/win/enforce-append-only.ps1
# Tests ALLOW (exit 0) and BLOCK (exit 2) paths. Claude Code blocks a PreToolUse
# call only on exit 2; any other non-zero code lets the write go ahead.
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

# --- Native payloads: BLOCK (exit 2) ---
foreach ($log in 'henka-register', 'decision-log', 'audit-log') {
    $code = Invoke-Hook (New-NativePayload 'Write' @{ file_path = "/work/proj/.council/$log.jsonl" })
    if ($code -eq 2) { Pass "native Write on .council/$log.jsonl is blocked (exit 2)" }
    else { Fail "native Write on .council/$log.jsonl should exit 2 (exit was $code)" }
}
$code = Invoke-Hook (New-NativePayload 'Edit' @{ file_path = '/work/proj/.council/decision-log.jsonl' })
if ($code -eq 2) { Pass "native Edit on .council/decision-log.jsonl is blocked (exit 2)" }
else { Fail "native Edit on .council/decision-log.jsonl should exit 2 (exit was $code)" }
$code = Invoke-Hook (New-NativePayload 'Write' @{ file_path = 'henka-register.jsonl'; cwd = '/work/proj/.council' })
if ($code -eq 2) { Pass "native bare henka-register.jsonl from cwd=.council is blocked (exit 2)" }
else { Fail "native bare henka-register.jsonl from cwd=.council should exit 2 (exit was $code)" }

# --- Native payloads: ALLOW (exit 0) ---
$code = Invoke-Hook (New-NativePayload 'Write' @{})
if ($code -eq 0) { Pass "recorded Write to an ordinary file is allowed" }
else { Fail "recorded Write to an ordinary file should be allowed (exit was $code)" }
$code = Invoke-Hook (New-NativePayload 'Write' @{ tool_name = 'Read'; file_path = '/work/proj/.council/audit-log.jsonl' })
if ($code -eq 0) { Pass "native Read of a ledger is allowed" }
else { Fail "native Read of a ledger should be allowed (exit was $code)" }

# --- Legacy tool_args envelopes (still recognized): BLOCK (exit 2) ---

$envelope = '{"tool_name":"Write","tool_args":{"file_path":".council/henka-register.jsonl"},"cwd":"/tmp","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -eq 2) { Pass "Write on henka-register.jsonl is blocked" }
else { Fail "Write on henka-register.jsonl should be blocked (exit was 0)" }

$envelope = '{"tool_name":"Edit","tool_args":{"file_path":".council/decision-log.jsonl"},"cwd":"/tmp","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -eq 2) { Pass "Edit on decision-log.jsonl is blocked" }
else { Fail "Edit on decision-log.jsonl should be blocked" }

$envelope = '{"tool_name":"Write","tool_args":{"file_path":".council/audit-log.jsonl"},"cwd":"/tmp","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -eq 2) { Pass "Write on audit-log.jsonl is blocked" }
else { Fail "Write on audit-log.jsonl should be blocked" }

# --- BLOCK cases: cwd-relative path resolution (issue #18 append-only bypass regression) ---
# A protected log written via a path relative to a shifted cwd must still be matched.

$envelope = '{"tool_name":"Write","tool_args":{"file_path":"henka-register.jsonl"},"cwd":"/proj/.council","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -eq 2) { Pass "Bare henka-register.jsonl from cwd=.council is blocked" }
else { Fail "Bare henka-register.jsonl from cwd=/proj/.council should be blocked (append-only bypass)" }

$envelope = '{"tool_name":"Write","tool_args":{"file_path":"./decision-log.jsonl"},"cwd":"/proj/.council","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -eq 2) { Pass "./decision-log.jsonl from cwd=.council is blocked" }
else { Fail "./decision-log.jsonl from cwd=/proj/.council should be blocked" }

$envelope = '{"tool_name":"Write","tool_args":{"file_path":"/proj/.council/audit-log.jsonl"},"cwd":"/somewhere/else","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -eq 2) { Pass "Absolute path to audit-log.jsonl is blocked" }
else { Fail "Absolute /proj/.council/audit-log.jsonl should be blocked" }

# --- ALLOW cases ---

# Same basename but NOT under .council/ is a different file — must NOT over-block
$envelope = '{"tool_name":"Write","tool_args":{"file_path":"henka-register.jsonl"},"cwd":"/proj","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -eq 0) { Pass "Bare henka-register.jsonl from project root (not .council) is allowed" }
else { Fail "henka-register.jsonl at project root should be allowed (exit was $code)" }

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
# (Pipeline + $LASTEXITCODE must be two statements; PowerShell rejects
#  `(pipeline; $LASTEXITCODE)` as a single grouping expression.)
'' | pwsh -NoLogo -NoProfile -File 'hooks/win/enforce-append-only.ps1'
$code = $LASTEXITCODE
if ($code -eq 0) { Pass "Empty envelope fails open (exit 0)" }
else { Fail "Empty envelope should fail open (exit was $code)" }

# --- Results ---
Write-Host ""
if ($Errors -eq 0) {
    Write-Host "ALL TESTS PASSED"
    exit 0
} else {
    Write-Host "$Errors TEST(S) FAILED"
    exit 1
}
