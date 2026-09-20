# Post-install facts (bash mangles /flag args -> must use -File).
# Resolves the installed exe from the uninstall registry key (both hives) so it
# works for BOTH /ALLUSERS (Program Files) and /CURRENTUSER (LocalAppData).
$GUID = '{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}_is1'
$out = [ordered]@{}
$exe = $null
foreach ($hive in 'HKCU:','HKLM:') {
    $key = "$hive\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\$GUID"
    $p = Get-ItemProperty $key -ErrorAction SilentlyContinue
    if ($p) {
        $out."${hive}_displayversion" = $p.DisplayVersion
        $out."${hive}_install_location" = $p.InstallLocation
        if (-not $exe -and $p.InstallLocation) { $exe = Join-Path $p.InstallLocation 'BorsTerminal_Ultimate.exe' }
    }
}
if ($exe) {
    try {
        $vi = (Get-Item $exe).VersionInfo
        $out.file_version = $vi.FileVersion
        $out.product_version = $vi.ProductVersion
    } catch { $out.file_version = $null; $out.product_version = $null }
    $out.file_exists = Test-Path $exe
} else { $out.file_exists = $false }
try { $p = Get-Process -Name 'BorsTerminal_Ultimate' -ErrorAction Stop; $out.running = $true; $out.pids = @($p.Id) } catch { $out.running = $false; $out.pids = @() }
$out | ConvertTo-Json -Compress
