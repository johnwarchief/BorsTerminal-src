$items = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue |
  Where-Object { $_.DisplayName -like '*Bors*' }
if (-not $items) { "no Bors uninstall entry in HKCU"; exit }
foreach ($i in $items) {
  "{0} | DisplayVersion={1} | InstallLocation={2}" -f $i.DisplayName, $i.DisplayVersion, $i.InstallLocation
}
