# Delta-update E2E (v1.0.10+): proves the in-app updater downloads and applies
# ONLY the changed files, never the full ~86 MB setup.
#
# Preconditions:
#   * an installed, delta-capable BorsTerminal (>= 1.0.10, ships apply_update.bat)
#   * the app is NOT running (we start it ourselves so we own its environment)
#   * a freshly built dist\BorsTerminal_Ultimate at $TargetVersion
#
# Flow (all real, no mocks):
#   1. build a true content-hash delta patch against the installed baseline
#   2. write latest.json with a patches[] entry pointing at the local patch
#   3. start the app with BORS_UPDATE_MANIFEST set to that manifest
#   4. drive the real HTTP updater: /check -> /download -> /install
#   5. poll until the app comes back at $TargetVersion
#   6. assert: downloaded bytes << setup bytes, version bumped, screener alive
#
# Usage:  powershell -File scripts\e2e\delta_apply.ps1 -TargetVersion 1.0.11
param([string]$TargetVersion = '1.0.11',
      [string]$FromVersion   = '1.0.10')
$ErrorActionPreference = 'Stop'
$REPO   = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$PY     = 'C:\Users\PCMOD\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$GUID   = '{8F3A2E7C-1B44-4C2E-9A77-0B0B5C0DE001}_is1'
$TEMP   = Join-Path $env:TEMP 'cline'
$API    = 'http://127.0.0.1:8001'
$resFile = Join-Path $TEMP 'delta_e2e_result.json'
if (-not (Test-Path $TEMP)) { New-Item -ItemType Directory -Path $TEMP | Out-Null }

$res = [ordered]@{
    from_version=$FromVersion; target_version=$TargetVersion
    baseline_files=0; patch_mb=0.0; setup_mb=0.0; ratio_pct=0.0
    check_delta=$false; check_size=0; download_delta=$false
    downloaded_bytes=0; applied=$false; version_api=''; screener='not_run'
    app_relaunched=$false; reg_displayversion=''; overall='FAIL'; note=''
}
function Log($m) { Write-Output $m }
function Fail($m) { $res.note = $m; $res.overall = 'FAIL'; $res | ConvertTo-Json | Set-Content $resFile; Log "[FATAL] $m"; exit 1 }

# ---------------------------------------------------------------- install dir
$installDir = $null
foreach ($hive in 'HKCU:','HKLM:') {
    $key = "$hive\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\$GUID"
    $p = Get-ItemProperty $key -ErrorAction SilentlyContinue
    if ($p -and $p.InstallLocation) { $installDir = $p.InstallLocation; break }
}
if (-not $installDir) { Fail 'installed app not found (run install_silent.ps1 first)' }
# Inno stamps a trailing backslash; it would escape the quote we pass to
# make_patch.py, turning "--baseline C:\...\Ultimate"" into a broken path.
$installDir = $installDir.TrimEnd('\')
Log ("[0/7] install dir: $installDir")

# the baseline must be a delta-capable release: it ships the applier
$applier = Join-Path $installDir 'apply_update.bat'
if (-not (Test-Path $applier)) { Fail "baseline $FromVersion has no apply_update.bat (delta needs >= 1.0.10)" }

# ------------------------------------------------- 1) build the delta patch
$patchName = "BorsTerminal_Patch_${FromVersion}_to_${TargetVersion}.zip"
$patch     = Join-Path $REPO "dist\$patchName"
$manifestPath = Join-Path $TEMP "latest_delta_${TargetVersion}.json"

Log "[1/7] building content-hash delta patch (baseline = the live install)"
& $PY (Join-Path $REPO 'scripts\make_patch.py') "--from" $FromVersion "--baseline" $installDir
if ($LASTEXITCODE -ne 0) { Fail 'make_patch.py failed' }
if (-not (Test-Path $patch)) { Fail "patch not produced: $patch" }
if (-not (Test-Path "$patch.sig")) { Fail "patch signature missing" }
$res.patch_mb = [math]::Round((Get-Item $patch).Length / 1MB, 2)
$res.baseline_files = (Get-ChildItem $installDir -Recurse -File |
    Where-Object { $_.FullName -notmatch '\\__pycache__\\' -and $_.Extension -ne '.pyc' }).Count

# the full setup is the alternative the updater must NOT take
$setup = Get-ChildItem (Join-Path $REPO 'installer\out\BorsTerminal_Ultimate_Setup_*.exe') |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($setup) {
    $res.setup_mb = [math]::Round($setup.Length / 1MB, 2)
    $res.ratio_pct = [math]::Round(100 * $res.patch_mb / $res.setup_mb, 1)
}
Log ("      patch = {0} MB   setup = {1} MB   ratio = {2}%" -f $res.patch_mb, $res.setup_mb, $res.ratio_pct)

# ------------------------------------------------- 2) manifest with patches[]
$sig = (Get-Content "$patch.sig" -Raw).Trim()
$manifest = [ordered]@{
    version = $TargetVersion
    notes   = "delta e2e $FromVersion -> $TargetVersion"
    pub_date = (Get-Date -Format 'ddd, dd MMM yyyy HH:mm:ss GMT')
    platforms = [ordered]@{ 'windows-x86_64' = [ordered]@{
        url = ($setup.FullName); signature = 'SIG-INSTALLER-PLACEHOLDER' } }
    patches = @(@{ from = $FromVersion; to = $TargetVersion
                   url = $patch; signature = $sig
                   size = (Get-Item $patch).Length })
}
# write without a byte-order mark: a BOM breaks Python json.load and would
# silently disable the whole update check. the UTF8NoBOM encoding name only
# exists in PowerShell 7, so go through the .NET writer which also works on
# the built-in 5.1 shell.
$json = $manifest | ConvertTo-Json -Depth 6
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($manifestPath, $json, $utf8)
Log "[2/7] manifest: $manifestPath"

# ------------------------------------------------- 3) start the app pointed at it
Get-Process -Name 'BorsTerminal_Ultimate' -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.Id -Force }
Start-Sleep -Seconds 2

$exe = Join-Path $installDir 'BorsTerminal_Ultimate.exe'
Log "[3/7] starting the app with BORS_UPDATE_MANIFEST"
$env:BORS_UPDATE_MANIFEST = $manifestPath
Start-Process -FilePath $exe -WorkingDirectory $installDir
Remove-Item Env:\BORS_UPDATE_MANIFEST -ErrorAction SilentlyContinue

$up = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    try { $r = Invoke-WebRequest -UseBasicParsing "$API/api/update/version" -TimeoutSec 2
          if ($r.StatusCode -eq 200) { $up = $true; break } } catch { }
}
if (-not $up) { Fail 'app API never came up' }
$before = (Invoke-WebRequest -UseBasicParsing "$API/api/update/version" -TimeoutSec 5).Content
Log ("      app up, reports: $before")
if ($before -notmatch [regex]::Escape($FromVersion)) {
    Fail "installed app is not at $FromVersion (got $before) - refusing to patch the wrong baseline"
}

# ------------------------------------------------- 4) drive the real updater
Log "[4/7] /api/update/check"
$chk = (Invoke-WebRequest -UseBasicParsing "$API/api/update/check" -TimeoutSec 15).Content | ConvertFrom-Json
$res.check_delta = [bool]$chk.delta
$res.check_size  = [int]$chk.size
Log ("      available={0} delta={1} size={2} MB url={3}" -f $chk.available, $chk.delta, [math]::Round($chk.size/1MB,2), $chk.url)
if (-not $chk.available) { Fail "/check says no update available" }
if (-not $chk.delta) { Fail "/check did NOT select the delta patch - it would download the full setup" }
if ($chk.url -ne $patch) { Fail "/check url is not the patch url" }

Log "[5/7] /api/update/download"
$dl = (Invoke-WebRequest -UseBasicParsing -Method Post "$API/api/update/download" `
       -ContentType 'application/json' `
       -Body (@{ url = $chk.url; signature = $chk.signature; version = $chk.latest_version } | ConvertTo-Json) `
       -TimeoutSec 15).Content | ConvertFrom-Json
$res.download_delta = [bool]$dl.delta
Log ("      started delta={0} path={1}" -f $dl.delta, $dl.path)
if (-not $dl.delta) { Fail "/download fell back to the full installer" }

# wait for the download + minisign verification to finish
$ready = $false
for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 1
    $pr = (Invoke-WebRequest -UseBasicParsing "$API/api/update/progress" -TimeoutSec 5).Content | ConvertFrom-Json
    if ($pr.status -eq 'ready' -or $pr.status -eq 'installing') { $ready = $true; break }
    if ($pr.status -eq 'error') { Fail ("updater error: " + $pr.message) }
}
if (-not $ready) { Fail 'download never became ready' }
$pr = (Invoke-WebRequest -UseBasicParsing "$API/api/update/progress" -TimeoutSec 5).Content | ConvertFrom-Json
$res.downloaded_bytes = [int]$pr.downloaded
Log ("      downloaded {0} MB (status={1})" -f [math]::Round($pr.downloaded/1MB,2), $pr.status)

Log "[6/7] /api/update/install  (the app will exit and apply the patch)"
try {
    (Invoke-WebRequest -UseBasicParsing -Method Post "$API/api/update/install" `
     -ContentType 'application/json' -Body '{}' -TimeoutSec 20).Content | Out-Null
} catch {
    # expected: the app exits (delayed exit) and the socket closes
    Log "      install endpoint closed as expected (app is exiting)"
}

# ------------------------------------------------- 5) wait for the relaunch
$after = $null
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 1
    try { $r = Invoke-WebRequest -UseBasicParsing "$API/api/update/version" -TimeoutSec 2
          if ($r.StatusCode -eq 200) { $after = $r.Content; break } } catch { }
}
if (-not $after) { Fail 'app did not come back after the patch' }
$res.app_relaunched = $true
$res.version_api = $after
Log ("      app came back: $after")

# ------------------------------------------------- 6) assertions
Log "[7/7] verifying"
if ($after -notmatch [regex]::Escape($TargetVersion)) { Fail "still at $after, expected $TargetVersion" }
$res.applied = $true

try { $sc = (Invoke-WebRequest -UseBasicParsing "$API/api/screener" -TimeoutSec 20).StatusCode }
catch { $sc = 0 }
$res.screener = if ($sc -eq 200) { 'ok' } else { 'http_' + $sc }
if ($sc -ne 200) { Fail "screener unhealthy after the delta (http $sc)" }

if ($res.downloaded_bytes -gt (Get-Item $patch).Length + 1024) {
    Fail ("downloaded {0} bytes, patch is only {1} - the updater pulled more than the delta" -f $res.downloaded_bytes, (Get-Item $patch).Length)
}

# a patch only overlays files, so Add/Remove Programs would still advertise
# $FromVersion unless the applier synced it. this caught the applier
# self-update gap (the worker is the PRE-update copy, so a fix in it never
# ran on the delta that shipped it).
foreach ($hive in 'HKCU:','HKLM:') {
    $rk = "$hive\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\$GUID"
    $rp = Get-ItemProperty $rk -ErrorAction SilentlyContinue
    if ($rp -and $rp.InstallLocation -and "$($rp.InstallLocation)".TrimEnd('\') -eq $installDir) {
        $res.reg_displayversion = "$($rp.DisplayVersion)"
    }
}
if ($res.reg_displayversion -ne $TargetVersion) {
    Fail ("Add/Remove Programs still says '{0}', expected {1} - the applier did not sync the uninstall registry" -f $res.reg_displayversion, $TargetVersion)
}

$res.overall = 'PASS'
$res | ConvertTo-Json | Set-Content $resFile
Log ("OVERALL: PASS   delta {0} -> {1}  ({2} MB instead of {3} MB, {4}% of setup)" -f $FromVersion, $TargetVersion, $res.patch_mb, $res.setup_mb, $res.ratio_pct)
exit 0
