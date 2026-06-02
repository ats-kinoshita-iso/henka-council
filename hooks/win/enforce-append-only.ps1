# PreToolUse hook — block Write/Edit on append-only council logs.
# Reads Claude Code tool-call envelope JSON from stdin.
# Exit 0 = allow.  Non-zero exit = block (stderr message surfaced to user).
# Requires PowerShell 7+ (pwsh).

$ProtectedFiles = @(
    '.council/henka-register.jsonl'
    '.council/decision-log.jsonl'
    '.council/audit-log.jsonl'
)

# Read envelope from stdin
try {
    $rawInput = [Console]::In.ReadToEnd()
} catch {
    exit 0
}

if ([string]::IsNullOrWhiteSpace($rawInput)) {
    exit 0
}

# Parse JSON envelope
try {
    $envelope = $rawInput | ConvertFrom-Json -ErrorAction Stop
} catch {
    # Malformed JSON — fail open
    [Console]::Error.WriteLine("enforce-append-only: malformed JSON envelope — hook skipped (fail open)")
    exit 0
}

$toolName = if ($envelope.tool_name) { $envelope.tool_name } else { '' }
$filePath = if ($envelope.tool_args -and $envelope.tool_args.file_path) { $envelope.tool_args.file_path } else { '' }

# Only inspect Write and Edit tool calls
if ($toolName -ne 'Write' -and $toolName -ne 'Edit') {
    exit 0
}

# Resolve the write target against the tool-call cwd before matching. A path expressed
# relative to a shifted cwd (cwd=<root>/.council, file_path=henka-register.jsonl) must
# still resolve to <root>/.council/henka-register.jsonl. Without this, a bare or
# ./-relative path slips past the protected-file check — the append-only bypass (issue #18).
$cwd = if ($envelope.cwd) { $envelope.cwd } else { '' }
$normPath = ($filePath -replace '\\', '/') -replace '^\./', ''
$cwd = $cwd -replace '\\', '/'

if ($normPath -match '^(/|[A-Za-z]:/)') {
    $absPath = $normPath
} elseif ($cwd) {
    $absPath = $cwd.TrimEnd('/') + '/' + $normPath
} else {
    $absPath = $normPath
}

foreach ($protected in $ProtectedFiles) {
    # Match the cwd-resolved absolute path (catches relative-to-.council evasions) and the
    # raw normalized path (catches the plain ".council/<log>" form when no cwd is present).
    if ($absPath -eq $protected -or $absPath.EndsWith("/$protected") -or $normPath -eq $protected) {
        [Console]::Error.WriteLine("BLOCKED: Direct $toolName on append-only log '$filePath' is forbidden.")
        [Console]::Error.WriteLine("  Approved write paths: scripts/append-henka.py, scripts/append-decision.py")
        exit 1
    }
}

exit 0
