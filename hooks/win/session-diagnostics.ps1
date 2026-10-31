# SessionEnd hook — thin wrapper over scripts/session-diagnostics.py (parity with
# hooks/session-diagnostics.sh, v2.1 amendment A7). Exit 0 always.
# Requires PowerShell 7+ (pwsh) and python on PATH.
$script = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..' '..' 'scripts' 'session-diagnostics.py'))
try { $raw = [Console]::In.ReadToEnd() } catch { exit 0 }
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) { exit 0 }
try { $raw | & $py.Source $script 2>$null | Out-Null } catch { }
exit 0
