# Stop hook — append a SESSION_STOPPED marker to progress.md.
# Reads (or ignores) any envelope from stdin.
# Exit 0 always (stop hooks cannot block).
# Requires PowerShell 7+ (pwsh).

# Env-var override for testability; also accept legacy COUNCIL_PROGRESS_FILE
$TargetFile = if ($env:SESSION_MARKER_PATH) {
    $env:SESSION_MARKER_PATH
} elseif ($env:COUNCIL_PROGRESS_FILE) {
    $env:COUNCIL_PROGRESS_FILE
} else {
    '.harness/progress.md'
}

# Read and discard stdin
try {
    $null = [Console]::In.ReadToEnd()
} catch {
    # ignore
}

# Generate UTC timestamp
$timestamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')

# Ensure parent directory exists
$targetDir = Split-Path $TargetFile -Parent
if ($targetDir -and -not (Test-Path $targetDir)) {
    try {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    } catch {
        [Console]::Error.WriteLine("session-stopped-marker: failed to create directory for $TargetFile")
        exit 0
    }
}

# Append marker
try {
    $marker = @(
        ''
        "## Session $timestamp"
        'SESSION_STOPPED. Current sprint state should be committed.'
    ) -join "`n"
    Add-Content -Path $TargetFile -Value $marker -Encoding UTF8
} catch {
    [Console]::Error.WriteLine("session-stopped-marker: failed to write to $TargetFile")
    exit 0
}

exit 0
