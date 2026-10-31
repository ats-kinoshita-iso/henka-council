# PostToolUse hook — thin wrapper over scripts/log-tool-call.py (parity with
# hooks/log-tool-call.sh, v2.1 amendment A7). Reads the native hook payload on
# stdin and passes it through unchanged. Exit 0 always.
# Requires PowerShell 7+ (pwsh) and python on PATH.
$script = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..' '..' 'scripts' 'log-tool-call.py'))
try { $raw = [Console]::In.ReadToEnd() } catch { exit 0 }
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) { [Console]::Error.WriteLine('log-tool-call: python not found — audit logging skipped'); exit 0 }
try { $raw | & $py.Source $script 2>$null | Out-Null } catch { }
exit 0
