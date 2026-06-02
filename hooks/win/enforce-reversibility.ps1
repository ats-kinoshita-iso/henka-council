# PreToolUse hook — block irreversible Bash commands when effective autonomy level < 5.
# Reads Claude Code tool-call envelope JSON from stdin.
# Exit 0 = allow.  Non-zero exit = block.
# Requires PowerShell 7+ (pwsh).

$IrreversiblePatterns = @(
    'git push'
    'git push --force'
    'git reset --hard'
    'git rebase'
    'git merge'
    'rm -rf'
    'git filter-branch'
)

# Resolve the project root for anchoring the effective-autonomy path.
# Priority: CLAUDE_PROJECT_DIR (set by Claude Code at hook-fire time) ->
# nearest ancestor of the start dir containing a .git marker -> start dir.
# Without this, a shifted cwd makes the file unreadable and the hook silently
# falls back to the default level (issue #18).
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

# Env-var override for testability; default path is anchored to the project root below.
$AutonomyFile = $env:EFFECTIVE_AUTONOMY_PATH

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
    [Console]::Error.WriteLine("enforce-reversibility: malformed JSON envelope — hook skipped (fail open)")
    exit 0
}

$toolName = if ($envelope.tool_name) { $envelope.tool_name } else { '' }

# Only inspect Bash tool calls
if ($toolName -ne 'Bash') {
    exit 0
}

# Anchor the autonomy-state path to the project root unless an explicit override was given.
if (-not $AutonomyFile) {
    $cwd = if ($envelope.cwd) { $envelope.cwd } else { (Get-Location).Path }
    $AutonomyFile = (Get-CouncilProjectRoot -Start $cwd).TrimEnd('/', '\') + '/.council/state/effective-autonomy.json'
}

# Read effective autonomy level; default to 4 if file absent
$level = 4
if (Test-Path $AutonomyFile) {
    try {
        $autonomyState = Get-Content -Raw $AutonomyFile | ConvertFrom-Json -ErrorAction Stop
        if ($null -ne $autonomyState.level -and $autonomyState.level -is [int]) {
            $level = $autonomyState.level
        } elseif ($null -ne $autonomyState.level) {
            $level = [int]$autonomyState.level
        }
    } catch {
        [Console]::Error.WriteLine("enforce-reversibility: could not parse level from $AutonomyFile — defaulting to 4 (fail open)")
    }
} else {
    [Console]::Error.WriteLine("enforce-reversibility: $AutonomyFile not found — defaulting to level 4 (fail open)")
}

# If level >= 5, all commands allowed
if ($level -ge 5) {
    exit 0
}

# Extract the command
$commandStr = if ($envelope.tool_args -and $envelope.tool_args.command) { $envelope.tool_args.command } else { '' }

if ([string]::IsNullOrWhiteSpace($commandStr)) {
    exit 0
}

# Check for irreversible patterns
foreach ($pattern in $IrreversiblePatterns) {
    if ($commandStr.Contains($pattern)) {
        [Console]::Error.WriteLine("BLOCKED: Irreversible command '$pattern' detected in Bash tool call.")
        [Console]::Error.WriteLine("  Effective autonomy level is $level (< 5). Irreversible operations require level 5.")
        [Console]::Error.WriteLine("  Command: $commandStr")
        exit 1
    }
}

exit 0
