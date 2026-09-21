# scripts/clean_slate.ps1 — شبیه‌سازیِ یک ویندوزِ خام برای تست نصب
#
# کارها:
#   ۱) بک‌آپِ داده‌های کاربر (data/) به _cleanstate_backup
#   ۲) کشتنِ پروسه‌های در حال اجرا
#   ۳) پاک کردنِ همهٔ مسیرهای نصب (Program Files، LocalAppData)
#   ۴) پاک کردنِ کلیدهای Uninstall رجیستری
#   ۵) پاک کردنِ شورتکات‌های دسکتاپ/استارت‌منو
#
# استفاده:  powershell -File scripts\clean_slate.ps1
#           powershell -File scripts\clean_slate.ps1 -WhatIf
#
# ⚠ هشدارِ ایمنیِ مهم: این اسکریپت فقط مسیرهای «نصب‌شده» را پاک می‌کند،
# هرگز سورس‌کد را. نسخهٔ اول شورتکات‌ها را با Get-ChildItem -Recurse -Filter
# '*Bors*' رویِ پوشهٔ دسکتاپ جستجو می‌کرد و چون پروژه رویِ دسکتاپ است،
# فایلهایی مثل bors_config.py / bors_entry.py / bors.ico و خروجی‌هایِ
# dist/ را هم بهعنوانِ «شورتکات» تشخیص داده و حذف می‌کرد! اکنون:
#   - فقط فایلهای با پسوندِ .lnk حذف می‌شوند
#   - پوشهٔ ریشهٔ پروژه (و هر مسیری که حاویِ bors_entry.py است) اکسکلود می‌شود
param([switch]$WhatIf = $false)
$ErrorActionPreference = 'Stop'
$la = $env:LOCALAPPDATA
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$bak = Join-Path $root '_cleanstate_backup'

# مسیرهایی که هرگز نباید لمس شوند — سورس‌کد و خروجی‌های بیلد.
$protected = @($root)
function Test-Protected($path) {
    foreach ($p in $protected) {
        if ($path -like "$p*") { return $true }
    }
    # هر مسیری که حاویِ سورسِ پروژه باشد هم محفوظ است.
    if (Test-Path (Join-Path $path 'bors_entry.py')) { return $true }
    return $false
}

# --- ۱) بک‌آپِ دادهٔ کاربر -------------------------------------------------
$userData = Join-Path $la 'BorsTerminal_Ultimate'
if (Test-Path $userData) {
    New-Item -ItemType Directory -Force -Path $bak | Out-Null
    foreach ($n in 'data', 'data.bak_v104') {
        $src = Join-Path $userData $n
        if (Test-Path $src) {
            Copy-Item $src $bak -Recurse -Force
            Write-Host "[backup] $n"
        }
    }
}

# --- ۲) کشتنِ پروسه‌ها ---------------------------------------------------
Get-Process -Name 'BorsTerminal*' -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "[kill] $($_.Name) pid=$($_.Id)"
    Stop-Process -Id $_.Id -Force
}
Start-Sleep -Seconds 3

# --- ۳) مسیرهای نصب ------------------------------------------------------
# نصبِ Velopack در %LOCALAPPDATA%\<AppId> می‌نشیند (بدونِ فاصله/زیرخط) و
# خودِ برنامه در current/. AppId در installer/bors_setup.iss تعریف می‌شود.
$targets = @(
    (Join-Path $la 'BorsTerminalUltimate'),
    (Join-Path $la 'BorsTerminal_Ultimate'),
    (Join-Path $la 'Bors Terminal Ultimate'),
    (Join-Path $la 'Programs\BorsTerminalUltimate'),
    (Join-Path $la 'Programs\BorsTerminal Ultimate'),
    'C:\Program Files\BorsTerminalUltimate',
    'C:\Program Files\BorsTerminal Ultimate',
    'C:\Program Files (x86)\BorsTerminalUltimate',
    'C:\Program Files (x86)\BorsTerminal Ultimate'
)
foreach ($t in $targets) {
    if (Test-Path $t) {
        if (Test-Protected $t) {
            Write-Host "[guard] SKIP protected source path: $t" -ForegroundColor Yellow
            continue
        }
        if ($WhatIf) { Write-Host "[whatif] would wipe $t"; continue }
        try {
            Remove-Item $t -Recurse -Force -ErrorAction Stop
            Write-Host "[wipe] $t"
        }
        catch { Write-Host "[FAIL]  $t :: $($_.Exception.Message)" }
    }
    else { Write-Host "[absent] $t" }
}

# --- ۴) رجیستری ----------------------------------------------------------
$hives = @(
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
    'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall',
    'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
)
foreach ($h in $hives) {
    Get-ChildItem $h -ErrorAction SilentlyContinue | ForEach-Object {
        $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
        if ($p.DisplayName -like '*Bors*') {
            Write-Host "[reg]   remove $($_.PSChildName) ($($p.DisplayName))"
            Remove-Item $_.PSPath -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# --- ۵) شورتکات‌ها --------------------------------------------------------
# فقط فایلهای .lnk واقعی حذف می‌شوند. نسخهٔ قبلی -Filter '*Bors*' بود که
# فایلهایِ سورس روی دسکتاپ (bors_config.py، bors.ico، ...) را هم می‌گرفت.
$desktop = [Environment]::GetFolderPath('Desktop')
$startmenu = [Environment]::GetFolderPath('Programs')
foreach ($dir in $desktop, $startmenu) {
    Get-ChildItem $dir -Recurse -Filter '*.lnk' -ErrorAction SilentlyContinue |
        Where-Object { ($_.Name -like '*Bors*') -and -not (Test-Protected $_.FullName) } |
        ForEach-Object {
            Write-Host "[cut]   remove $($_.Name)"
            Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
        }
}

Write-Host ""
Write-Host "== clean-slate complete ==" -ForegroundColor Green
Write-Host "  user data backed up to: $bak"
Write-Host "  (restore with: Copy-Item `"$bak\data`" `"$userData`" -Recurse -Force)"
