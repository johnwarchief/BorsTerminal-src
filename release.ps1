# release.ps1 — تولید نسخه‌های BorsTerminal Ultimate از ریشهٔ ریپو اجرا کن
#   .\release.ps1 setup      → فقط نصب‌کننده (setup.exe)
#   .\release.ps1 base       → فقط آرشیو بیس‌کد خام
#   .\release.ps1 portable   → باندل قابل‌حمل (بدون نصب)
#   .\release.ps1 all        → هر سه
param([ValidateSet('setup','base','portable','all')][string]$Mode = 'setup')
$ErrorActionPreference = 'Stop'

# --- تنظیمات مسیرها (در صورت تفاوت، این‌ها را عوض کن) ---
$PY   = 'C:\Users\PCMOD\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$NPM  = 'C:\Program Files\AutoClaw\resources\node\npm.cmd'
$ISCC = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path (Join-Path $root 'bors_entry.py'))) { $root = (Get-Location).Path }
Set-Location $root
$ver = (Get-Date -Format 'yyyy.MM.dd')
Write-Host "== BorsTerminal release: mode=$Mode  root=$root" -ForegroundColor Cyan

function Ensure-Db {
    # تا به حال این تابع هر market.dbی را با هر محتوایی فشرده می‌کرد. اگر dbِ
    # محلی ناقص باشد (سینکِ نیمه‌تمام، یا یک dbیِ خالیِ ساخته‌شده توسط مسیری
    # که preflight را دور می‌زند)، همان چیز به‌عنوانِ market.db.lzmaیِ ریلیز
    # بسته می‌شد — دقیقاً ریشهٔ باگِ v1.0.7/8. اکنون ابتدا منبع اعتبارسنجی
    # می‌شود؛ اگر ناقص بود با خطا متوقف می‌شویم تا baselineیِ commit‌شده
    # دست‌نخورده بماند.
    if (-not (Test-Path 'market.db')) { Write-Host '[db] market.db not found (skip)'; return }

    Write-Host '[db] validating source market.db'
    & $PY -c 'import sqlite3,sys
need={"instruments","daily_prices","financial_statements"}
try:
    cur=sqlite3.connect("file:market.db?mode=ro",uri=True)
    have={r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type=\"table\"")}
    fs=cur.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0] if "financial_statements" in have else 0
    cur.close()
except Exception as e:
    print("SRC_BAD: %r"%e); sys.exit(1)
miss=sorted(need-have)
if miss:
    print("SRC_INCOMPLETE missing=%s"%",".join(miss)); sys.exit(1)
if fs<1000:
    print("SRC_TOO_SMALL financial_statements rows=%d"%fs); sys.exit(1)
print("SRC_OK financial_statements rows=%d"%fs)'
    if ($LASTEXITCODE -ne 0) {
        Write-Error '[db] source market.db is incomplete — refusing to overwrite the committed market.db.lzma baseline. ABORT.'
        exit 1
    }

    if (Test-Path 'market.db.lzma') {
        Copy-Item 'market.db.lzma' 'market.db.lzma.bak' -Force
        Write-Host '[db] backed up previous market.db.lzma -> market.db.lzma.bak'
    }
    Write-Host '[db] compressing market.db -> market.db.lzma'
    & $PY -c 'import lzma,os
d=open("market.db","rb").read()
open("market.db.lzma","wb").write(lzma.compress(d,preset=9))
print("  lzma MB", round(os.path.getsize("market.db.lzma")/1048576,1))'
    # round-trip: lzma باید دقیقاً همانیِ منبع را برگرداند؛ وگرنه baselineیِ
    # قبلی را برگردان و متوقف شو.
    & $PY -c 'import lzma
d=open("market.db.lzma","rb").read(); s=open("market.db","rb").read()
assert lzma.decompress(d)==s, "round-trip mismatch"
print("  round-trip OK")'
    if ($LASTEXITCODE -ne 0) {
        if (Test-Path 'market.db.lzma.bak') { Copy-Item 'market.db.lzma.bak' 'market.db.lzma' -Force }
        Write-Error '[db] market.db.lzma round-trip verification FAILED — restored previous baseline. ABORT.'
        exit 1
    }
}
function Build-Frontend {
    Write-Host '[fe] npm install + build'
    Push-Location frontend; & $NPM install --no-audit --no-fund; & $NPM run build; Pop-Location
}
function Build-Exe {
    Write-Host '[exe] PyInstaller'
    & $PY -m PyInstaller bors_setup.spec --noconfirm --distpath "$root\dist" --workpath "$root\build"
}
function Assert-DistFresh {
    # جلوگیری از بسته‌بندیِ یک distیِ قدیمی در نصابِ جدید. ریشهٔ یک کلاس
    # باگِ خطرناک: اگر dist/ از قبل وجود داشته باشد، Build-Setup/Build-Portable
    # بدونِ هیچ بررسی‌ای دوباره از آن استفاده می‌کنند. پس اگر اپِ فریزشده
    # قدیمی‌تر از منابع باشد (مثلاً بعد از bumpِ نسخه یا یک فیکس، rebuild
    # نشده باشد)، یا نسخه‌اش با bors_setup.iss یکی نباشد، اینجا متوقف می‌شویم.
    $exe = Join-Path $root 'dist\BorsTerminal_Ultimate\BorsTerminal_Ultimate.exe'
    if (-not (Test-Path $exe)) { return }
    $built = (Get-Item $exe).LastWriteTime

    $issVer = $null
    $iss = Get-Content (Join-Path $root 'installer\bors_setup.iss') -Raw
    if ($iss -match '(?m)^\s*#define\s+AppVersion\s+"([^"]+)"') { $issVer = $Matches[1] }

    $appVer = $null
    $cfg = Join-Path $root 'dist\BorsTerminal_Ultimate\_internal\bors_config.py'
    if (-not (Test-Path $cfg)) { $cfg = Join-Path $root 'dist\BorsTerminal_Ultimate\bors_config.py' }
    if (Test-Path $cfg) {
        $m = [regex]::Match((Get-Content $cfg -Raw), 'APP_VERSION\s*=\s*"([^"]+)"')
        if ($m.Success) { $appVer = $m.Groups[1].Value }
    }
    if ($issVer -and $appVer -and ($appVer -ne $issVer)) {
        Write-Error ("[guard] stale dist: frozen app is v{0} but bors_setup.iss is v{1}. after a version bump the app MUST be rebuilt — delete dist\ and re-run. ABORT." -f $appVer, $issVer)
        exit 1
    }

    $watch = 'bors_config.py','bors_entry.py','bors_minisign.py','bors_setup.spec','fts_terminal.spec','installer/bors_setup.iss','frontend/package.json','frontend/package-lock.json','frontend/src-tauri/tauri.conf.json'
    $stale = @()
    foreach ($f in $watch) {
        $p = Join-Path $root ($f -replace '/', '\')
        if ((Test-Path $p) -and ((Get-Item $p).LastWriteTime -gt $built)) { $stale += $f }
    }
    foreach ($d in 'api','frontend/src') {
        $p = Join-Path $root $d
        if (Test-Path $p) {
            Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object { $_.LastWriteTime -gt $built } |
                ForEach-Object { $stale += $_.FullName.Substring($root.Length + 1) }
        }
    }
    if ($stale.Count) {
        Write-Error ("[guard] dist is older than these sources: {0}. rebuild the app first (delete dist\ and re-run). ABORT." -f ($stale -join ', '))
        exit 1
    }
}
function Build-Setup {
    Assert-DistFresh
    if (-not (Test-Path "$root\dist\BorsTerminal_Ultimate\BorsTerminal_Ultimate.exe")) { Build-Frontend; Build-Exe }
    if (Test-Path 'market.db.lzma') { Copy-Item 'market.db.lzma' "$root\dist\BorsTerminal_Ultimate\market.db.lzma" -Force }
    # فقط lzma باندل می‌شود. یک market.dbیِ سرگردان در dist (باقیمانده از runهای
    # قبلی یا ابزارهای تست) نباید سرازیرِ نصب شود؛ در غیر این صورت نصب یک dbیِ
    # خام/ناقص را هم می‌گیرد و ensure_market_db ممکن است همان را بپذیرد.
    $stray = "$root\dist\BorsTerminal_Ultimate\market.db"
    if (Test-Path $stray) { Remove-Item $stray -Force; Write-Host '[setup] removed stray dist market.db' }
    Write-Host '[setup] Inno Setup'
    & $ISCC "$root\installer\bors_setup.iss"
    Get-ChildItem "$root\installer\out\*.exe" | ForEach-Object { Write-Host ("  -> " + $_.FullName + "  (" + [math]::Round($_.Length/1MB,1) + " MB)") }
    Sign-Setup
}

function Sign-Setup {
    # امضای minisign (Ed25519 روی blake2b-512) که آپدیتِرِ tauri لازم دارد.
    # کلِ منطق در scripts/sign_setup.py: اول tauri signer (با timeout سخت)،
    # سپس fallbackِ minisignِ خالصِ پایتون، و در پایان تأییدِ امضا. بدونِ امضای
    # معتبر آپدیتِر این بیلد را رد می‌کند — پس بیلد را اینجا متوقف می‌کنیم.
    $setup = Get-ChildItem "$root\installer\out\BorsTerminal_Ultimate_Setup_*.exe" |
             Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $setup) { Write-Host '[sign] no installer found (skip)'; return }
    Write-Host '[sign] minisign (tauri-first, python fallback, verify)'
    & $PY "$root\scripts\sign_setup.py" $setup.FullName
    if ($LASTEXITCODE -ne 0) {
        Write-Error '[sign] signature missing or invalid — the updater would reject this build. ABORT.'
        exit 1
    }
    Get-ChildItem "$root\installer\out\*.sig" | ForEach-Object { Write-Host ("  -> " + $_.Name + "  (" + [math]::Round($_.Length/1KB,1) + " KB)") }
}
function Build-Base {
    $out = "$root\..\BorsTerminal_BaseCode_$ver.zip"
    Write-Host "[base] git archive -> $out"
    if (Test-Path $out) { Remove-Item $out -Force }
    git archive --format=zip --output="$out" master
    Write-Host ("  -> " + $out + "  (" + [math]::Round((Get-Item $out).Length/1MB,2) + " MB)")
}
function Build-Portable {
    Assert-DistFresh
    if (-not (Test-Path "$root\dist\BorsTerminal_Ultimate\BorsTerminal_Ultimate.exe")) { Build-Frontend; Build-Exe }
    $stage = "$root\releases\portable_$ver"
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    Copy-Item "$root\dist\BorsTerminal_Ultimate\*" $stage -Recurse -Force
    if (Test-Path 'market.db.lzma') { Copy-Item 'market.db.lzma' "$stage\market.db.lzma" -Force }
    Write-Host "[portable] staged: $stage"
}

switch ($Mode) {
    'base'     { Build-Base }
    'setup'    { Ensure-Db; Build-Setup }
    'portable' { Ensure-Db; Build-Portable }
    'all'      { Ensure-Db; Build-Base; Build-Setup; Build-Portable }
}
Write-Host '== done' -ForegroundColor Green
