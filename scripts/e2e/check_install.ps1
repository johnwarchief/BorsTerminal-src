# Where is the app installed, and is it running?
$guid = '{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}_is1'
foreach ($hive in 'HKCU:','HKLM:') {
  $k = "$hive\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\$guid"
  $p = Get-ItemProperty $k -EA SilentlyContinue
  if ($p) { Write-Output ("$hive  DisplayVersion=" + $p.DisplayVersion + "  InstallLocation=" + $p.InstallLocation) }
  else { Write-Output "$hive  none" }
}
try { $pr = Get-Process -Name 'BorsTerminal_Ultimate' -EA Stop; Write-Output ("running pids=" + ($pr.Id -join ',')) } catch { Write-Output 'running: no' }
