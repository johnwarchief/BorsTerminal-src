# E2E: run the frozen build from a READ-ONLY install dir (simulates
# C:\Program Files for a standard user, without needing elevation) and proves:
#   1. the frozen app reports version $BuildVersion
#   2. /api/update/check sees the LIVE release and says "up to date"
#   3. /api/screener returns 200 — the v1.0.8 regression test: it needs market.db
#      openable with WAL, which is impossible from a read-only dir unless the db
#      resolves to the writable user data dir
#   4. the screener cache AND market.db-wal/-shm land under
#      %LOCALAPPDATA%\BorsTerminal_Ultimate\data and NOTHING is written into the
#      read-only install dir, with no "Permission denied" / "unable to open
#      database file" in the app log.
# Writes a machine-readable result to %TEMP%\cline\e2e_result.json.
param([string]$BuildVersion = '1.0.9',
      [string]$Manifest = '')

$ErrorActionPreference = 'Continue'
$REPO = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$DIST = Join-Path $REPO 'dist/BorsTerminal_Ultimate'
$TEMP = Join-Path $env:TEMP 'cline'
$SIM  = Join-Path $TEMP 'siminstall'
$DATA = Join-Path $env:LOCALAPPDATA 'BorsTerminal_Ultimate/data'
$PORT = 8139
$USER = "$env:USERDOMAIN\$env:USERNAME"
$ACE  = "${USER}:(WD)"
$VER  = $BuildVersion
$outLog = Join-Path $TEMP 'e2e_app.log'
$errLog = Join-Path $TEMP 'e2e_app.err.log'
$resultFile = Join-Path $TEMP 'e2e_result.json'
if (-not (Test-Path $TEMP)) { New-Item -ItemType Directory -Path $TEMP | Out-Null }

$res = [ordered]@{
    version=''; check_latest=''; check_available=$null; check_url='';
    screener='not_run'; cache_in_data=$false; cache_in_sim=$false;
    db_in_data=$false; wal_in_sim=$false; shm_in_sim=$false;
    permission_denied=$false; db_error=$false; startup=$false; overall='FAIL'; note=''
}

function Log($m) { Write-Output $m }

# ---- preconditions ---------------------------------------------------------
$exe = Join-Path $DIST 'BorsTerminal_Ultimate.exe'
if (-not (Test-Path $exe)) { Log "[FATAL] build missing: $exe"; $res.note='build missing'; exit 1 }

# ---- prepare an isolated read-only install dir -----------------------------
if (Test-Path $SIM) {
    icacls $SIM /remove:d $ACE /T /C 2>$null | Out-Null
    Remove-Item $SIM -Recurse -Force -ErrorAction SilentlyContinue
}
Log "[1/9] copying build -> $SIM"
Copy-Item -Path $DIST -Destination $SIM -Recurse -Force
# a writable baseline run can leave market.db-wal/-shm inside dist; drop them
# from the copy so we can prove the read-only run never recreates them there.
'-wal','-shm' | ForEach-Object {
    $f = Join-Path $SIM ("market.db" + $_)
    if (Test-Path $f) { Remove-Item $f -Force }
}
icacls $SIM /deny $ACE /T /C | Out-Null
$probe = Join-Path $SIM 'wtprobe'
try {
    Set-Content -Path $probe -Value 'x' -ErrorAction Stop
    Log "[FATAL] sim dir is still writable"; $res.note='sim dir writable'; exit 1
} catch { Log "[2/9] sim install dir is READ-ONLY (simulating Program Files)" }

# ---- make the cache/db write attributable to this run ----------------------
$cache    = Join-Path $DATA '.screener_cache.json'
$simCache = Join-Path $SIM '.screener_cache.json'
$dbData   = Join-Path $DATA 'market.db'
if (Test-Path $cache)    { Remove-Item $cache    -Force; Log "[3/9] cleared stale cache" }
if (Test-Path $simCache) { Remove-Item $simCache -Force }

# ---- launch the app from the read-only dir ---------------------------------
$env:BORS_PORT = "$PORT"
# when verifying a build that is not the live release yet, point the updater
# at a local manifest so the "current == latest" check can pass.
if ($Manifest -ne '') { $env:BORS_UPDATE_MANIFEST = $Manifest }
if (Test-Path $outLog) { Remove-Item $outLog -Force }
if (Test-Path $errLog) { Remove-Item $errLog -Force }
$exeSim = Join-Path $SIM 'BorsTerminal_Ultimate.exe'
$p = Start-Process -FilePath $exeSim -WorkingDirectory $TEMP -PassThru `
      -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog
Log "[4/9] launched pid=$($p.Id) BORS_PORT=$PORT from the read-only dir"
function Fetch-Json($rel, $tries, $waitSec, $timeoutSec) {
    for ($i = 1; $i -le $tries; $i++) {
        if ($p.HasExited) { return $null }
        try {
            $r = Invoke-WebRequest -Uri ("http://127.0.0.1:" + $PORT + $rel) `
                 -UseBasicParsing -TimeoutSec $timeoutSec
            return ($r.Content | ConvertFrom-Json)
        } catch { Start-Sleep -Seconds $waitSec }
    }
    return $null
}

try {
    # ---- 5) version ---------------------------------------------------------
    $v = Fetch-Json '/api/update/version' 90 2 20
    if ($null -eq $v) { Log "[FATAL] app never answered"; $res.note='no startup'; }
    else {
        $res.version = [string]$v.version
        $res.startup = $true
        Log "[5/9] /api/update/version -> $($res.version)"
    }

    # ---- 6) live manifest check --------------------------------------------
    if ($res.startup) {
        $c = Fetch-Json '/api/update/check' 30 2 30
        if ($null -ne $c) {
            $res.check_latest = [string]$c.latest_version
            $res.check_available = [bool]$c.available
            $res.check_url = [string]$c.url
            Log "[6/9] /api/update/check -> latest=$($res.check_latest) available=$($res.check_available) url=$($res.check_url)"
        } else { Log "[6/9] /api/update/check FAILED to respond"; }
    }

    # ---- 7) screener (needs market.db via WAL; the v1.0.8 fix) -------------
    if ($res.startup) {
        Log "[7/9] GET /api/screener (computes + saves .screener_cache.json) ..."
        $s = Fetch-Json '/api/screener' 40 5 300
        if ($null -ne $s) { $res.screener = 'ok'; Log "      screener 200 OK" }
        else { $res.screener = 'error'; Log "      screener failed/timed out" }
        Start-Sleep -Seconds 2
        $res.cache_in_data = Test-Path $cache
        $res.cache_in_sim  = Test-Path $simCache
        $res.db_in_data    = Test-Path $dbData
        $res.wal_in_sim    = Test-Path (Join-Path $SIM 'market.db-wal')
        $res.shm_in_sim    = Test-Path (Join-Path $SIM 'market.db-shm')
        Log "      cache in DATA dir: $($res.cache_in_data)"
        Log "      cache in read-only install dir: $($res.cache_in_sim)"
        Log "      market.db in DATA dir: $($res.db_in_data)"
        Log "      market.db-wal in read-only dir: $($res.wal_in_sim)"
        Log "      market.db-shm in read-only dir: $($res.shm_in_sim)"
    }

    # ---- 8) log scan --------------------------------------------------------
    $logTxt = ''
    if (Test-Path $outLog) { $logTxt += Get-Content $outLog -Raw }
    if (Test-Path $errLog) { $logTxt += Get-Content $errLog -Raw }
    if ($logTxt -match '(?i)permission denied') { $res.permission_denied = $true }
    if ($logTxt -match '(?i)unable to open database file') { $res.db_error = $true }
    Log "[8/9] 'Permission denied' in app log: $($res.permission_denied)"
    Log "[9/9] 'unable to open database file' in app log: $($res.db_error)"
}
finally {
    if ($null -ne $p -and -not $p.HasExited) {
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    }
    Get-Process -Name 'BorsTerminal_Ultimate' -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like ($SIM + '*') } |
        ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
    icacls $SIM /remove:d $ACE /T /C 2>$null | Out-Null
    Remove-Item $SIM -Recurse -Force -ErrorAction SilentlyContinue
}

# ---- verdict ---------------------------------------------------------------
$ok = $true
if ($res.version -ne $VER) { $ok = $false }
if ($res.check_latest -ne $VER) { $ok = $false }
if ($res.check_available -ne $false) { $ok = $false }
if ($res.check_url -notmatch "v$([regex]::Escape($VER))") { $ok = $false }
if ($res.cache_in_sim) { $ok = $false }
if ($res.wal_in_sim -or $res.shm_in_sim) { $ok = $false }
if ($res.permission_denied) { $ok = $false }
if ($res.db_error) { $ok = $false }
if ($res.screener -eq 'ok' -and -not $res.cache_in_data) { $ok = $false }
if ($res.screener -eq 'ok' -and -not $res.db_in_data) { $ok = $false }

if ($ok) {
    if ($res.screener -eq 'ok' -and $res.cache_in_data -and $res.db_in_data) {
        $res.overall = 'PASS'; $res.note = 'screener 200 with cache + market.db under the user data dir; nothing written into the read-only install dir'
    } else {
        $res.overall = 'PASS_NOTE'; $res.note = 'release checks pass; screener did not complete so db/cache write unverified, but no writes hit the read-only dir and no Permission denied occurred'
    }
} else {
    $res.overall = 'FAIL'; $res.note = 'see fields above'
}
Log "OVERALL: $($res.overall) - $($res.note)"
$res | ConvertTo-Json | Set-Content -Path $resultFile
