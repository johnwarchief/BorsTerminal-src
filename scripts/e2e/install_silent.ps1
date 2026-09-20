# Silent-update E2E against a real built setup (mirrors api/update.py flow):
#   1. stop the running app (Inno cannot replace a locked exe)
#   2. run setup with the SAME flags the updater builds
#   3. registry DisplayVersion + exe FileVersion must say $SetupVersion
#   4. the [Run] section already launched the app: /api/update/version -> ver, /api/screener -> 200
# Writes %TEMP%\cline\install_e2e_result.json.
param([string]$SetupVersion = '1.0.9')
$ErrorActionPreference = 'Continue'
$REPO   = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$SETUP  = Join-Path $REPO "installer/out/BorsTerminal_Ultimate_Setup_v$SetupVersion.exe"
$PWF    = Join-Path $REPO 'installer/.setup_password.iss'
$GUID   = '{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}_is1'
$TEMP   = Join-Path $env:TEMP 'cline'
$VER    = $SetupVersion
$innoLog = Join-Path $TEMP 'inno_install.log'
$resFile = Join-Path $TEMP 'install_e2e_result.json'
if (-not (Test-Path $TEMP)) { New-Item -ItemType Directory -Path $TEMP | Out-Null }

$res = [ordered]@{
    elevated=$false; mode=''; installer_rc=$null; reg_displayversion='';
    install_location=''; exe_file_version=''; version_api='';
    screener='not_run'; app_running=$false; overall='FAIL'; note=''
}
function Log($m) { Write-Output $m }

if (-not (Test-Path $SETUP)) { $res.note='setup missing'; $res | ConvertTo-Json | Set-Content $resFile; Log "[FATAL] setup missing: $SETUP"; exit 1 }

# 1) elevation level decides ALLUSERS vs CURRENTUSER (exactly like _install_flags)
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($id)
$res.elevated = $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)

# 2) installer password (same extraction as api/update.py _setup_password)
$pw = $null
if (Test-Path $PWF) {
    $t = Get-Content $PWF -Raw
    if ($t -match '#define\s+SetupPassword\s+"([^"]*)"') { $pw = $Matches[1] }
}
if (-not $pw) { $res.note='password not found'; $res | ConvertTo-Json | Set-Content $resFile; Log '[FATAL] password not found'; exit 1 }

# 3) stop a running app first (the updater exits itself; a locked exe aborts the install)
Get-Process -Name 'BorsTerminal_Ultimate' -EA SilentlyContinue | ForEach-Object { Stop-Process -Id $_.Id -Force }
Start-Sleep -Seconds 2

# 4) flags identical to api/update.py._install_flags()
$flags = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', "/PASSWORD=$pw")
$dir = 'C:\Program Files\BorsTerminal Ultimate'
$hive = 'HKLM:'
if ($res.elevated) { $flags += '/ALLUSERS'; $res.mode = 'ALLUSERS' }
else {
    $flags += '/CURRENTUSER'; $res.mode = 'CURRENTUSER'
    $dir = Join-Path $env:LOCALAPPDATA 'Programs\BorsTerminal Ultimate'
    $hive = 'HKCU:'
}
$flags += "/DIR=`"$dir`"", "/LOG=`"$innoLog`""

Log ("[1/6] setup $VER ($($res.mode)) -> $dir")
# NOTE: no -Wait on Start-Process (it hangs here once the [Run] section has
# spawned the detached app). Instead poll the uninstall key for $VER.
$key = "$hive\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\$GUID"
$proc = Start-Process -FilePath $SETUP -ArgumentList $flags -PassThru
$found = $false
for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 2
    if ($proc.HasExited) { $res.installer_rc = $proc.ExitCode }
    $p = Get-ItemProperty $key -EA SilentlyContinue
    if ($p -and "$($p.DisplayVersion)" -eq $VER) { $found = $true; break }
}
Log ("      setup exit code = $($res.installer_rc); reg $VER seen = $found")

# 5) registry + file version
$p = Get-ItemProperty $key -EA SilentlyContinue
if ($p) { $res.reg_displayversion = "$($p.DisplayVersion)"; $res.install_location = "$($p.InstallLocation)" }
$exe = Join-Path $res.install_location 'BorsTerminal_Ultimate.exe'
if (Test-Path $exe) { $res.exe_file_version = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($exe).FileVersion }
Log ("[2/6] reg DisplayVersion = '$($res.reg_displayversion)'  exe FileVersion = '$($res.exe_file_version)'")

# 6) the [Run] section (nowait postinstall) already launched the app on the
# DEFAULT port (8001). The app is single-instance, so we probe that instance
# instead of trying to start a second one on a custom port.
$base = "http://127.0.0.1:8001"
Log "[3/6] waiting for app API on $base ..."
$ok = $false
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri "$base/api/update/version" -UseBasicParsing -TimeoutSec 5 -EA Stop
        if ($r.StatusCode -eq 200) {
            try { $res.version_api = ($r.Content | ConvertFrom-Json).version } catch { $res.version_api = $r.Content }
            $ok = $true; break
        }
    } catch { }
}
if ($ok) {
    Log ("[4/6] /api/update/version -> $($res.version_api)")
    $res.app_running = $true
    Log "[5/6] GET /api/screener ..."
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $s = Invoke-WebRequest -Uri "$base/api/screener" -UseBasicParsing -TimeoutSec 300 -EA Stop
            if ($s.StatusCode -eq 200) { $res.screener = 'ok'; break }
        } catch { Start-Sleep -Seconds 5 }
    }
    Log ("      screener = $($res.screener)")
} else { Log "[4/6] app never answered on $base" }

if ($res.reg_displayversion -eq $VER -and $res.version_api -eq $VER -and $res.screener -eq 'ok') {
    $res.overall = 'PASS'
} else { $res.note = 'see fields' }
Log ("[6/6] OVERALL: $($res.overall)")
Get-Process -Name 'BorsTerminal_Ultimate' -EA SilentlyContinue | ForEach-Object { Stop-Process -Id $_.Id -Force }
$res | ConvertTo-Json | Set-Content $resFile
