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

# --- BLOCK cases: cwd-relative path resolution (issue #18 append-only bypass regression) ---
# A protected log written via a path relative to a shifted cwd must still be matched.

$envelope = '{"tool_name":"Write","tool_args":{"file_path":"henka-register.jsonl"},"cwd":"/proj/.council","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -ne 0) { Pass "Bare henka-register.jsonl from cwd=.council is blocked" }
else { Fail "Bare henka-register.jsonl from cwd=/proj/.council should be blocked (append-only bypass)" }

$envelope = '{"tool_name":"Write","tool_args":{"file_path":"./decision-log.jsonl"},"cwd":"/proj/.council","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -ne 0) { Pass "./decision-log.jsonl from cwd=.council is blocked" }
else { Fail "./decision-log.jsonl from cwd=/proj/.council should be blocked" }

$envelope = '{"tool_name":"Write","tool_args":{"file_path":"/proj/.council/audit-log.jsonl"},"cwd":"/somewhere/else","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -ne 0) { Pass "Absolute path to audit-log.jsonl is blocked" }
else { Fail "Absolute /proj/.council/audit-log.jsonl should be blocked" }

# --- BLOCK cases: Windows backslash paths (native Windows envelopes) ---
# The hook must normalize backslash separators in file_path and cwd before
# matching; without that, backslash paths silently under-block.

$envelope = '{"tool_name":"Write","tool_args":{"file_path":".council\\henka-register.jsonl"},"cwd":"C:\\proj","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -ne 0) { Pass "Backslash-relative .council path is blocked" }
else { Fail "Backslash .council\henka-register.jsonl should be blocked" }

$envelope = '{"tool_name":"Write","tool_args":{"file_path":"C:\\proj\\.council\\decision-log.jsonl"},"cwd":"C:\\somewhere\\else","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -ne 0) { Pass "Absolute Windows backslash path to decision-log.jsonl is blocked" }
else { Fail "Absolute C:\proj\.council\decision-log.jsonl should be blocked" }

$envelope = '{"tool_name":"Write","tool_args":{"file_path":"audit-log.jsonl"},"cwd":"C:\\proj\\.council","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -ne 0) { Pass "Bare audit-log.jsonl from backslash Windows cwd is blocked" }
else { Fail "Bare audit-log.jsonl from backslash cwd C:\proj\.council should be blocked" }

# --- ALLOW cases ---

# Backslash path with the protected basename but NOT under .council must NOT over-block
$envelope = '{"tool_name":"Write","tool_args":{"file_path":"C:\\proj\\henka-register.jsonl"},"cwd":"C:\\proj","session_id":"test"}'
$code = Invoke-Hook $envelope
if ($code -eq 0) { Pass "Backslash path to non-.council henka-register.jsonl is allowed" }
else { Fail "C:\proj\henka-register.jsonl (not under .council) should be allowed (exit was $code)" }

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
