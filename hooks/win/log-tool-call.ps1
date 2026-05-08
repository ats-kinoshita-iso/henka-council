# PostToolUse hook — append a schema-valid audit entry to audit-log.jsonl.
# Reads Claude Code tool-call envelope JSON from stdin.
# Exit 0 = continue.  (PostToolUse hooks do not block — tool already ran.)
# Requires PowerShell 7+ (pwsh).

# Env-var override for testability
$AuditLog = if ($env:AUDIT_LOG_PATH) { $env:AUDIT_LOG_PATH } else { '.council/audit-log.jsonl' }

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
    [Console]::Error.WriteLine("log-tool-call: malformed JSON envelope — audit logging skipped")
    exit 0
}

$toolName = if ($envelope.tool_name) { $envelope.tool_name } else { 'unknown' }
$sessionId = if ($envelope.session_id) { $envelope.session_id } else { 'unknown' }
$agentId = if ($envelope.agent_id) { $envelope.agent_id } else { 'hook/log-tool-call' }

# Build a privacy-safe input summary
$inputSummary = switch ($toolName) {
    'Bash' {
        $cmd = if ($envelope.tool_args -and $envelope.tool_args.command) { $envelope.tool_args.command } else { '' }
        if ($cmd.Length -gt 200) { $cmd.Substring(0, 200) } else { $cmd }
    }
    { $_ -in 'Write', 'Edit', 'Read' } {
        $fp = if ($envelope.tool_args -and $envelope.tool_args.file_path) { $envelope.tool_args.file_path } else { '' }
        "file_path=$fp"
    }
    default { "$toolName call" }
}

# Determine event_type
$eventType = 'tool-call'
$lowerEnv = $rawInput.ToLower()
if ($lowerEnv -match '"andon|andon_signal|stop.*signal|alert.*signal') {
    $eventType = 'andon-signal'
}

# Generate entry_id and timestamp
$timestamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$nonce = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$entryId = "AUD-$nonce"

# Track andon_pull_count per agent
$andonStateDir = Join-Path ([System.IO.Path]::GetTempPath()) 'council-andon-counts'
if (-not (Test-Path $andonStateDir)) {
    New-Item -ItemType Directory -Path $andonStateDir -Force | Out-Null
}
$safeAgentId = $agentId -replace '[/:]', '_'
$andonCountFile = Join-Path $andonStateDir "$safeAgentId.count"

$andonCount = 0
if (Test-Path $andonCountFile) {
    try {
        $stored = [int](Get-Content $andonCountFile -Raw).Trim()
        $andonCount = $stored
    } catch {
        $andonCount = 0
    }
}

if ($eventType -eq 'andon-signal') {
    $andonCount++
    Set-Content -Path $andonCountFile -Value "$andonCount" -NoNewline
}

# Build audit entry object
$entry = [ordered]@{
    entry_id           = $entryId
    timestamp          = $timestamp
    event_type         = $eventType
    agent_id           = $agentId
    tool_name          = $toolName
    tool_input_summary = $inputSummary
    tool_outcome       = 'success'
    andon_pull_count   = $andonCount
}

# Serialize to JSON
try {
    $jsonLine = $entry | ConvertTo-Json -Compress -Depth 5
} catch {
    [Console]::Error.WriteLine("log-tool-call: failed to serialize audit entry — skipping")
    exit 0
}

# Ensure parent directory exists
$auditDir = Split-Path $AuditLog -Parent
if ($auditDir -and -not (Test-Path $auditDir)) {
    try {
        New-Item -ItemType Directory -Path $auditDir -Force | Out-Null
    } catch {
        [Console]::Error.WriteLine("log-tool-call: failed to create audit log directory — skipping")
        exit 0
    }
}

# Append entry
try {
    Add-Content -Path $AuditLog -Value $jsonLine -Encoding UTF8
} catch {
    [Console]::Error.WriteLine("log-tool-call: failed to append to $AuditLog — skipping")
    exit 0
}

exit 0
