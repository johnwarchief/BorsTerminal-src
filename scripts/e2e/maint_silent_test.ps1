# Regression test for the Inno maintenance mode: installs an arbitrary setup
# /VERYSILENT (the auto-update path) and asserts the app comes back healthy.
# Maintenance mode must be a NO-OP here: WizardSilent() suppresses the option
# page, so a silent install must behave exactly like before.
# Usage: .\maint_silent_test.ps1 [-Setup 'C:\path\to\setup.exe']
param([string]$Setup = '')
$ErrorActionPreference = 'Continue'
$REPO  = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $Setup) { $Setup = Join-Path $REPO 'installer/out/BorsTerminal_Ultimate_Setup_v1.0.9.exe' }
$base  = 'http://127.0.0.1:8001'
$TEMP  = Join-Path $env:TEMP 'cline'
$log   = Join-Path $TEMP 'maint_silent_install.log'
$resF  = Join-Path $TEMP 'maint_silent_result.json'
$regkey = 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}_is1'
if (-not (Test-Path $TEMP)) { New-Item -ItemType Directory -Path $TEMP | Out-Null }

$res = [ordered]@{ overall='FAIL'; setup_rc=$null; reg_displayversion=''; version_api='';
                   check_available=$null; screener='not_run'; note='' }
function Log($m) { Write-Output $m }
if (-not (Test-Path $Setup)) { $res.note="setup missing: $Setup"; $res | ConvertTo-Json | Set-Content $resF; Log "[FATAL] $($res.note)"; exit 1 }

# 1) stop the running app (files must be replaceable)
$before = (Get-Process -Name BorsTerminal_Ultimate -ErrorAction SilentlyContinue).Count
Log "app running before install: $before"
Get-Process -Name BorsTerminal_Ultimate -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# 2) password, read dynamically from the gitignored file (never hardcode it)
$pwFile = Join-Path $REPO 'installer/.setup_password.iss'
$pw = $null
if (Test-Path $pwFile) {
    $m = [regex]::Match((Get-Content $pwFile -Raw), '#define\s+SetupPassword\s+"([^"]*)"')
    if ($m.Success) { $pw = $m.Groups[1].Value }
}
# exactly the flags api/update.py builds
$flags = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/CURRENTUSER', "/LOG=`"$log`"")
if ($pw) { $flags += "/PASSWORD=$pw"; Log 'password: loaded from .setup_password.iss' }
else { Log 'WARNING: password not found -> falling back to /SILENT'; $flags[0] = '/SILENT' }

# 3) install; do NOT -Wait (Inno's [Run] spawns a detached app) -> poll setup exit
$p = Start-Process -FilePath $Setup -ArgumentList $flags -PassThru
Log "setup pid=$($p.Id) started"
$exited = $false
for ($i = 1; $i -le 90; $i++) {
    Start-Sleep -Seconds 2
    if ($p.HasExited) { Log "setup process exited after $($i*2)s (exit=$($p.ExitCode))"; $res.setup_rc = $p.ExitCode; $exited = $true; break }
    if ($i % 15 -eq 0) { Log "waiting for setup ($($i*2)s)..." }
}
if (-not $exited) { $res.note='setup still running (timeout)'; try { $p.Kill() } catch {} }

# 4) registry
try {
    $reg = Get-ItemProperty $regkey -ErrorAction Stop
    $res.reg_displayversion = "$($reg.DisplayVersion)"
    Log "registry DisplayVersion=$($reg.DisplayVersion)"
    Log "registry InstallLocation=$($reg.InstallLocation)"
} catch { Log "registry read failed: $_" }

# 5) the new app's API
$up = $false
for ($i = 1; $i -le 25; $i++) {
    Start-Sleep -Seconds 3
    try {
        $v = (Invoke-WebRequest -Uri "$base/api/update/version" -UseBasicParsing -TimeoutSec 6).Content
        Log "app ready after $($i*3)s -> $v"; $up = $true; break
    } catch { Log "waiting api ($i)..." }
}
if (-not $up) { $res.note='APP NOT UP'; $res | ConvertTo-Json | Set-Content $resF; Log 'APP NOT UP'; exit 2 }
try { $res.version_api = ((Invoke-WebRequest -Uri "$base/api/update/version" -UseBasicParsing -TimeoutSec 6).Content | ConvertFrom-Json).version } catch {}
try {
    $chk = (Invoke-WebRequest -Uri "$base/api/update/check" -UseBasicParsing -TimeoutSec 60).Content | ConvertFrom-Json
    $res.check_available = $chk.available
    Log ("check: current={0} latest={1} available={2}" -f $chk.current_version, $chk.latest_version, $chk.available)
} catch { Log "check failed: $_" }
try {
    $r = Invoke-WebRequest -Uri "$base/api/screener?limit=3" -UseBasicParsing -TimeoutSec 90
    $res.screener = "ok($($r.StatusCode))"
    Log "screener -> $($r.StatusCode) bytes=$($r.RawContentLength)"
} catch { Log "screener failed: $_" }

# 6) stop the app
Get-Process -Name BorsTerminal_Ultimate -ErrorAction SilentlyContinue | Stop-Process -Force
Log "app stopped:" (Get-Process -Name BorsTerminal_Ultimate -ErrorAction SilentlyContinue).Count

if ($res.setup_rc -eq 0 -and $res.version_api -and $res.check_available -eq $false -and $res.screener -like 'ok*') {
    $res.overall = 'PASS'
} else { $res.note = 'see fields' }
Log "OVERALL: $($res.overall)"
$res | ConvertTo-Json | Set-Content $resF
