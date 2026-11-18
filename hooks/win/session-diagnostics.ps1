# SessionEnd hook — thin wrapper over scripts/session-diagnostics.py (parity with
# hooks/session-diagnostics.sh, v2.1 amendment A7). Appends one diagnostic event per
# settled process lifetime to <root>/.council/diagnostics.jsonl (ADR-0006 A1).
# The payload reaches Python as the raw bytes Claude Code sent (UTF-8): it is never
# decoded and re-encoded here, so a non-ASCII path survives any console code page.
# Exit 0 always. Requires PowerShell 7+ (pwsh) and Python on PATH.

# Crew guard (ADR-0006 A1 D1.9): auto-mate commits a crew's leftovers, so with
# AUTOMATE_RUN set the council writes nothing.
if ($env:AUTOMATE_RUN) { exit 0 }

$script = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..' '..' 'scripts' 'session-diagnostics.py'))

# Prefer the py launcher (the Store "python" alias can hang), then python, then python3.
$exe = $null
$prefix = @()
foreach ($candidate in @(@('py', '-3'), @('python'), @('python3'))) {
    $cmd = Get-Command $candidate[0] -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) {
        $exe = $cmd.Source
        $prefix = @($candidate | Select-Object -Skip 1)
        break
    }
}
if (-not $exe) { exit 0 }

try {
    $payload = New-Object System.IO.MemoryStream
    [Console]::OpenStandardInput().CopyTo($payload)

    $info = New-Object System.Diagnostics.ProcessStartInfo
    $info.FileName = $exe
    foreach ($arg in $prefix) { $info.ArgumentList.Add($arg) }
    $info.ArgumentList.Add($script)
    $info.UseShellExecute = $false
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true

    $proc = [System.Diagnostics.Process]::Start($info)
    $stdout = $proc.StandardOutput.ReadToEndAsync()
    $stderr = $proc.StandardError.ReadToEndAsync()
    $payload.Position = 0
    $payload.CopyTo($proc.StandardInput.BaseStream)
    $proc.StandardInput.Close()
    $proc.WaitForExit()
    $null = $stdout.Result
    $null = $stderr.Result
} catch { }
exit 0
