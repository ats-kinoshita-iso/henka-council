# Stop hook — append a SESSION_STOPPED marker to progress.md.
# Reads (or ignores) any envelope from stdin.
# Exit 0 always (stop hooks cannot block).
# Requires PowerShell 7+ (pwsh).

# Resolve the project root for anchoring the progress-marker path.
# Priority: CLAUDE_PROJECT_DIR (set by Claude Code at hook-fire time) ->
# nearest ancestor of the start dir containing a .git marker -> start dir.
# Prevents a nested .council/.harness/progress.md when the session cwd is a
# subdirectory of the project root (issue #18).
function Get-CouncilProjectRoot {
    param([string]$Start = (Get-Location).Path)
    if ($env:CLAUDE_PROJECT_DIR) {
        return ($env:CLAUDE_PROJECT_DIR.TrimEnd('/', '\'))
    }
    $dir = $Start
    while (-not [string]::IsNullOrEmpty($dir)) {
        if (Test-Path (Join-Path $dir '.git')) {
            return $dir
        }
        $parent = Split-Path $dir -Parent
        if ([string]::IsNullOrEmpty($parent) -or $parent -eq $dir) { break }
        $dir = $parent
    }
    return $Start
}

# Env-var override for testability; also accept legacy COUNCIL_PROGRESS_FILE.
# Default path is anchored to the project root below.
$TargetFile = if ($env:SESSION_MARKER_PATH) {
    $env:SESSION_MARKER_PATH
} elseif ($env:COUNCIL_PROGRESS_FILE) {
    $env:COUNCIL_PROGRESS_FILE
} else {
    ''
}

# Read and discard stdin
try {
    $null = [Console]::In.ReadToEnd()
} catch {
    # ignore
}

# Anchor the progress-marker path to the project root unless an explicit override was given.
if (-not $TargetFile) {
    $TargetFile = (Get-CouncilProjectRoot).TrimEnd('/', '\') + '/.harness/progress.md'
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

# Append marker. Format matches the legacy mixed-case "Stopped." prose used
# throughout .harness/progress.md. The trailing HTML comment carries the
# SESSION_STOPPED tag so machine readers (e.g. the sprint-05 contract SC-11
# verification) can still locate session boundaries by substring match.
try {
    $marker = @(
        ''
        "## Session $timestamp"
        'Stopped. Current sprint state should be committed.  <!-- SESSION_STOPPED -->'
    ) -join "`n"
    Add-Content -Path $TargetFile -Value $marker -Encoding UTF8
} catch {
    [Console]::Error.WriteLine("session-stopped-marker: failed to write to $TargetFile")
    exit 0
}

exit 0
