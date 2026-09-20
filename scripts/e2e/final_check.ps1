# Final live check of the installed app (default port 8001, started by the
# installer's [Run] section): version, update check (current==latest) and
# screener rows. Resolves the exe from the uninstall registry key.
$ErrorActionPreference = 'Continue'
$guid = '{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}_is1'
$exe = $null
foreach ($hive in 'HKCU:','HKLM:') {
    $p = Get-ItemProperty "$hive\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\$guid" -EA SilentlyContinue
    if ($p -and $p.InstallLocation) { $exe = Join-Path $p.InstallLocation 'BorsTerminal_Ultimate.exe'; break }
}
if (-not $exe -or -not (Test-Path $exe)) { Write-Host 'installed exe not found'; exit 1 }
Write-Host "app running before launch:" (Get-Process -Name BorsTerminal_Ultimate -ErrorAction SilentlyContinue).Count
Start-Process -FilePath $exe
$base = 'http://127.0.0.1:8001'
$up = $false
for ($i = 1; $i -le 20; $i++) {
    Start-Sleep -Seconds 3
    try {
        $v = (Invoke-WebRequest -Uri "$base/api/update/version" -UseBasicParsing -TimeoutSec 6).Content
        Write-Host "ready after $($i*3)s -> $v"
        $up = $true
        break
    } catch { Write-Host "waiting ($i)..." }
}
if (-not $up) { Write-Host "APP NOT UP"; exit 2 }
try {
    $chk = (Invoke-WebRequest -Uri "$base/api/update/check" -UseBasicParsing -TimeoutSec 60).Content | ConvertFrom-Json
    Write-Host ("check: current={0} latest={1} available={2}" -f $chk.current_version, $chk.latest_version, $chk.available)
} catch { Write-Host "check failed: $_" }
try {
    $r = Invoke-WebRequest -Uri "$base/api/screener?limit=3" -UseBasicParsing -TimeoutSec 90
    $bytes = $r.RawContentLength
    $rows = ($r.Content | ConvertFrom-Json)
    Write-Host "screener -> $($r.StatusCode) bytes=$bytes rows=$(@($rows).Count)"
} catch { Write-Host "screener failed: $_" }
Get-Process -Name BorsTerminal_Ultimate -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "app stopped:" (Get-Process -Name BorsTerminal_Ultimate -ErrorAction SilentlyContinue).Count
