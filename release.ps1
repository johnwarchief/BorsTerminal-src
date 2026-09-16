# release.ps1 — تولید نسخه‌های BorsTerminal Ultimate از ریشهٔ ریپو اجرا کن
#   .\release.ps1 setup      → فقط نصب‌کننده (setup.exe)
#   .\release.ps1 base       → فقط آرشیو بیس‌کد خام
#   .\release.ps1 portable   → باندل قابل‌حمل (بدون نصب)
#   .\release.ps1 all        → هر سه
param([ValidateSet('setup','base','portable','all')][string]$Mode = 'setup')
$ErrorActionPreference = 'Stop'

# --- تنظیمات مسیرها (در صورت تفاوت، این‌ها را عوض کن) ---
$PY   = 'C:\Program Files\AutoClaw\resources\python\python.exe'
$NPM  = 'C:\Program Files\AutoClaw\resources\node\npm.cmd'
$ISCC = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path (Join-Path $root 'bors_entry.py'))) { $root = (Get-Location).Path }
Set-Location $root
$ver = (Get-Date -Format 'yyyy.MM.dd')
Write-Host "== BorsTerminal release: mode=$Mode  root=$root" -ForegroundColor Cyan

function Ensure-Db {
    if (Test-Path 'market.db') {
        Write-Host '[db] compressing market.db -> market.db.lzma'
        & $PY -c "import lzma,os;d=open('market.db','rb').read();open('market.db.lzma','wb').write(lzma.compress(d,preset=9));print('  lzma MB', round(os.path.getsize('market.db.lzma')/1048576,1))"
    } else { Write-Host '[db] market.db not found (skip)' }
}
function Build-Frontend {
    Write-Host '[fe] npm install + build'
    Push-Location frontend; & $NPM install --no-audit --no-fund; & $NPM run build; Pop-Location
}
function Build-Exe {
    Write-Host '[exe] PyInstaller'
    & $PY -m PyInstaller bors_setup.spec --noconfirm --distpath "$root\dist" --workpath "$root\build"
}
function Build-Setup {
    if (-not (Test-Path "$root\dist\BorsTerminal_Ultimate\BorsTerminal_Ultimate.exe")) { Build-Frontend; Build-Exe }
    if (Test-Path 'market.db.lzma') { Copy-Item 'market.db.lzma' "$root\dist\BorsTerminal_Ultimate\market.db.lzma" -Force }
    Write-Host '[setup] Inno Setup'
    & $ISCC "$root\installer\bors_setup.iss"
    Get-ChildItem "$root\installer\out\*.exe" | ForEach-Object { Write-Host ("  -> " + $_.FullName + "  (" + [math]::Round($_.Length/1MB,1) + " MB)") }
}
function Build-Base {
    $out = "$root\..\BorsTerminal_BaseCode_$ver.zip"
    Write-Host "[base] git archive -> $out"
    if (Test-Path $out) { Remove-Item $out -Force }
    git archive --format=zip --output="$out" master
    Write-Host ("  -> " + $out + "  (" + [math]::Round((Get-Item $out).Length/1MB,2) + " MB)")
}
function Build-Portable {
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
