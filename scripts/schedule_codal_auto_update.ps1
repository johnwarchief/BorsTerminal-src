# schedule_codal_auto_update.ps1 -- daily no-ADB CODAL auto-update (Phase 2, Task 6)
#
# Registers the Windows Task Scheduler task "BorsCodalAutoUpdate", whose action is:
#   python dev/codal_auto_update.py --mode daily
# every day at 18:30. StartWhenAvailable catches up a missed run after boot;
# MultipleInstances IgnoreNew prevents overlapping runs; each run is capped at
# 2 hours and restarted up to 2 times on failure. The orchestrator itself is
# staging-first and never touches ADB (POLITE fetch only).
#
# Install (PowerShell, from the repo root):
#   powershell -ExecutionPolicy Bypass -File scripts/schedule_codal_auto_update.ps1
# Remove:
#   powershell -ExecutionPolicy Bypass -File scripts/schedule_codal_auto_update.ps1 -Remove

param([switch]$Remove)
$ErrorActionPreference = "Stop"

$TaskName = "BorsCodalAutoUpdate"
$RepoRoot = Split-Path -Parent $PSScriptRoot
# "python" on PATH is often the WindowsApps alias, which fails under Task
# Scheduler (0x80070002). Resolve the real interpreter from sys.executable.
$Python = ((python -c "import sys;print(sys.executable)") 2>$null)
if (-not $Python) { $Python = "python" }
$Python = "$Python".Trim()

if ($Remove) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "removed $TaskName"
  exit 0
}

$Script = "dev/codal_auto_update.py"
$Argument = "`"$Script`" --mode daily"
$Action = New-ScheduledTaskAction -Execute $Python -Argument $Argument -WorkingDirectory $RepoRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At "18:30"
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
           -MultipleInstances IgnoreNew `
           -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
           -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 15)

try {
  $Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
  Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
           -Principal $Principal -Description "BorsTerminal daily CODAL auto-update (no ADB)" -Force | Out-Null
  Write-Host "registered $TaskName [S4U] -> $Python $Argument"
} catch {
  $Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
           -Principal $Principal -Description "BorsTerminal daily CODAL auto-update (no ADB)" -Force | Out-Null
  Write-Host "registered $TaskName [Interactive] -> $Python $Argument"
}
