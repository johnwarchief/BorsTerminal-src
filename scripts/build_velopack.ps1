# scripts/build_velopack.ps1 — Phase C: Velopack packaging for BorsTerminal
#
# جایگزینِ Inno Setup + apply_update.bat + taskkill. Velopack:
#   * دلتای باینریِ خودکار از نسخهٔ قبلی (کفِ اندازه‌گیری‌شده: 1.33 MB رویِ
#     onedir — plans/production-packaging-and-unpark-plan.md §3.2)
#   * دایرکتوری‌های نصبِ نسخه‌دار → آپدیت هرگز باینریِ در حال اجرا را
#     بازنویسی نمی‌کند، پس taskkill لازم نیست.
#   * اعمال + ری‌استارت توسطِ خودِ Velopack.
#
# نیازمندی‌ها: vpk (نصب‌شده در C:\Users\PCMOD\.dotnet\tools\vpk.exe)،
# خروجیِ onedir در dist/BorsTerminal_Ultimate (release.ps1 Build-Exe).
#
# استفاده (از ریشهٔ ریپو):
#   .\scripts\build_velopack.ps1                    # نسخه را از bors_config می‌خواند
#   .\scripts\build_velopack.ps1 -Version 1.0.12    # نسخهٔ صریح
#   .\scripts\build_velopack.ps1 -Sign              # امضایِ کد با signtool
param([string]$Version = '',
      [string]$PackDir = '',
      [string]$OutputDir = '',
      [switch]$Sign = $false,
      [string]$Channel = 'win')
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Test-Path (Join-Path $root 'bors_entry.py'))) { $root = (Get-Location).Path }
Set-Location $root

# ── مسیرها و نسخه ─────────────────────────────────────────────────────
$PY = 'C:\Users\PCMOD\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$vpk = 'C:\Users\PCMOD\.dotnet\tools\vpk.exe'
if (-not (Test-Path $vpk)) {
    $vpk = (Get-Command vpk -ErrorAction SilentlyContinue).Source
}
if (-not $vpk -or -not (Test-Path $vpk)) {
    Write-Error '[vpk] Velopack CLI not found. install: dotnet tool install -g vpk. ABORT.'; exit 1
}

if (-not $Version) {
    # منبعِ یگانهٔ حقیقت: bors_config.APP_VERSION — همان چیزی که درونِ
    # برنامه نمایش داده می‌شود و در latest.json می‌رود.
    $cfgLine = Select-String -Path (Join-Path $root 'bors_config.py') `
        -Pattern '^\s*APP_VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
    if (-not $cfgLine) { Write-Error '[ver] APP_VERSION not found in bors_config.py. ABORT.'; exit 1 }
    $Version = $cfgLine.Matches[0].Groups[1].Value
}
if (-not $PackDir)  { $PackDir  = Join-Path $root 'dist\BorsTerminal_Ultimate' }
if (-not $OutputDir) { $OutputDir = Join-Path $root 'dist\velopack' }

$mainExe = 'BorsTerminal_Ultimate.exe'
if (-not (Test-Path (Join-Path $PackDir $mainExe))) {
    Write-Error "[pack] onedir build not found: $PackDir\$mainExe. run release.ps1 first. ABORT."
    exit 1
}
# قراردادِ onedir باید قبل از بسته‌بندی سبز باشد.
& $PY dev/onedir_contract_v11.py --dist (Join-Path $root 'dist')
if ($LASTEXITCODE -ne 0) { Write-Error '[contract] onedir contract FAILED. ABORT.'; exit 1 }

Write-Host "== Velopack pack: v$Version  packDir=$PackDir  out=$OutputDir" -ForegroundColor Cyan

# ── بسته‌بندی ──────────────────────────────────────────────────────────
# --delta BestSpeed (پیش‌فرض): دلتای باینری از نسخهٔ قبلیِ موجود در
# OutputDir ساخته می‌شود. اگر نسخهٔ قبلی نبود، پکیجِ کامل تولید می‌شود.
# NOTE: $args یک متغیرِ خودکارِ PowerShell است؛ استفاده از آن به‌عنوان
# لیستِ آرگومانها مقدارها را بی‌صدا قورت می‌دهد. از $vpkArgs استفاده می‌کنیم.
$vpkArgs = @(
    'pack',
    '--packId', 'BorsTerminalUltimate',
    '--packVersion', $Version,
    '--packDir', $PackDir,
    '--mainExe', $mainExe,
    '--packTitle', 'BorsTerminal Ultimate',
    '--packAuthors', 'BorsTerminal',
    '--outputDir', $OutputDir,
    '--channel', $Channel,
    '--delta', 'BestSpeed',
    '--exclude', '.*\.pdb'
)
$icon = Join-Path $root 'assets\bors.ico'
if (-not (Test-Path $icon)) { $icon = Join-Path $root 'installer\bors.ico' }
if (Test-Path $icon) { $vpkArgs += '--icon'; $vpkArgs += $icon }
if ($Sign) {
    # امضا با signtool؛ پارامترها از متغیرهای محیطی می‌آیند تا کلیدها در
    # ریپو نباشند. بدونِ -Sign، بیلد امضانشده اما کامل تولید می‌شود.
    $signParams = $env:BORS_SIGN_PARAMS
    if (-not $signParams) {
        Write-Error '[sign] -Sign given but BORS_SIGN_PARAMS env var is empty. ABORT.'; exit 1
    }
    $vpkArgs += '--signParams'; $vpkArgs += $signParams
}

Write-Host "[vpk] $($vpkArgs -join ' ')"
& $vpk @vpkArgs
if ($LASTEXITCODE -ne 0) { Write-Error '[vpk] pack failed. ABORT.'; exit 1 }

# ── گزارشِ خروجی ───────────────────────────────────────────────────────
Write-Host "`n== Velopack release artifacts ==" -ForegroundColor Green
Get-ChildItem -Path $OutputDir -Recurse -File -ErrorAction SilentlyContinue |
    Sort-Object Length -Descending |
    ForEach-Object {
        $rel = $_.FullName.Substring($OutputDir.Length + 1)
        Write-Host ("  {0,10:N1} MB  {1}" -f ($_.Length / 1048576.0), $rel)
    }

# ستونِ اصلیِ موفقیت: دلتا باید از پکیجِ کامل کوچکتر باشد. در onefile
# این‌طور نبود (دلتا از خودِ exe بزرگتر بود) — این کلِ دلیلِ این ریفاکتور است.
$full = Get-ChildItem -Path $OutputDir -Filter '*-full.nupkg' -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending | Select-Object -First 1
$delta = Get-ChildItem -Path $OutputDir -Filter '*-delta.nupkg' -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending | Select-Object -First 1
if ($full) {
    Write-Host ("`n  full package:   {0:N1} MB" -f ($full.Length / 1048576.0))
}
if ($delta) {
    Write-Host ("  delta package:   {0:N1} MB  ({1:P0} of full)" -f (
        $delta.Length / 1048576.0), ($delta.Length / $full.Length))
    if ($delta.Length -ge $full.Length) {
        Write-Warning '[warn] delta is NOT smaller than the full package — the whole point of this refactor.'
    } else {
        Write-Host '  ✓ delta is smaller than full — Velopack is delivering savings.' -ForegroundColor Green
    }
} else {
    Write-Host '  (no previous version found - first full package; deltas appear from the next release)'
}

# ── زنجیرهٔ تجمعی (v1.0.13) ─────────────────────────────────────────────
# از این به بعد هر ریلیز شاملِ تغییراتِ قبلی هم هست: نسخه‌های قدیمی در
# OutputDir نگه داشته می‌شوند تا Velopack از هر نسخه‌ای به هر نسخهٔ جدیدتری
# برسد. این گزارشِ زنجیره را نشان می‌دهد تا قابلِ دیدن باشد.
$chain = Get-ChildItem -Path $OutputDir -Filter '*.nupkg' -ErrorAction SilentlyContinue |
    Sort-Object Name
if ($chain.Count -gt 0) {
    Write-Host "`n== cumulative release chain (older -> newer) ==" -ForegroundColor Cyan
    foreach ($p in $chain) {
        $kind = if ($p.Name -match '-delta-') { 'delta' } elseif ($p.Name -match '-full-') { 'full ' } else { ' ?   ' }
        Write-Host ("  [{0}] {1,-52} {2,8:N1} MB" -f $kind, $p.Name, ($p.Length / 1048576.0))
    }
    Write-Host ("  releases.win.json lists {0} package(s) - any older install can delta forward." -f $chain.Count)
}
Write-Host "`n== Velopack pack DONE: v$Version ==" -ForegroundColor Green
