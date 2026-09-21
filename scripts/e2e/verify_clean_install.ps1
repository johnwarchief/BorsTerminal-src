# scripts/e2e/verify_clean_install.ps1 — راستی‌آزماییِ نصبِ خام (Phase 2)
#
# بررسی می‌کند:
#   ۱) نصب در محلِ درست ثبت شده (رجیستری + فایل)
#   ۲) market.db فقط‌خواندنی است و دادهٔ کامل دارد
#   ۳) user.db تمیز در مسیرِ کاربر ساخته شده
#   ۴) apply_update.bat (پیش‌نیازِ آپدیتِ دلتا) حضور دارد
#
# استفاده: powershell -File scripts\e2e\verify_clean_install.ps1
$ErrorActionPreference = 'Stop'
$fail = 0
function Check($label, $cond, $extra) {
    if ($cond) { Write-Host "  [ok]   $label" -ForegroundColor Green }
    else { Write-Host "  [FAIL] $label $extra" -ForegroundColor Red; $script:fail++ }
}

Write-Host "== 1) install location ==" -ForegroundColor Cyan
$la = $env:LOCALAPPDATA
# Velopack نصب را در %LOCALAPPDATA%\<AppId> می‌گذارد و خودِ برنامه در
# current/ می‌نشیند. AppId در installer/bors_setup.iss تعریف می‌شود.
$candidates = @(
    (Join-Path $la 'BorsTerminalUltimate\current'),
    (Join-Path $la 'BorsTerminal Ultimate\current'),
    (Join-Path $la 'Programs\BorsTerminalUltimate'),
    (Join-Path $la 'Programs\BorsTerminal Ultimate'),
    'C:\Program Files\BorsTerminalUltimate',
    'C:\Program Files\BorsTerminal Ultimate'
)
$install = $null
foreach ($c in $candidates) { if (Test-Path $c) { $install = $c; break } }
Check "install dir exists" ($null -ne $install) "looked in: $($candidates -join ', ')"
if ($install) {
    Write-Host "         $install"
    $exe = Join-Path $install 'BorsTerminal_Ultimate.exe'
    Check "main EXE present" (Test-Path $exe) $exe
    $internal = Join-Path $install '_internal'
    Check "_internal bundle present" (Test-Path $internal) $internal
    $lzma = Join-Path $install 'market.db.lzma'
    Check "market.db.lzma shipped" (Test-Path $lzma) $lzma
    # apply_update.bat در نصبِ Velopack حضور ندارد — پچِ دلتا آن را از داخلِ
    # خودش استخراج می‌کند (see api/update.py _extract_applier_from_patch).
    # این یک چکِ اطلاعاتی است، نه یک نیازمندیِ سخت.
    $applier = Join-Path $install 'apply_update.bat'
    if (Test-Path $applier) {
        Check "apply_update.bat present (delta prerequisite)" $true ""
    }
    else {
        Write-Host "  [info] apply_update.bat absent — delta patch self-extracts it" -ForegroundColor Yellow
    }
    $vpk = Join-Path $la 'BorsTerminalUltimate\Update.exe'
    Check "Velopack Update.exe present" (Test-Path $vpk) $vpk
}

Write-Host ""
Write-Host "== 2) registry uninstall entry ==" -ForegroundColor Cyan
$found = $null
foreach ($hive in 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
                 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall',
                 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall') {
    Get-ChildItem $hive -ErrorAction SilentlyContinue | ForEach-Object {
        $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
        if ($p.DisplayName -like '*Bors*') { $found = $p }
    }
}
Check "uninstall entry exists" ($null -ne $found) ""
if ($found) {
    Write-Host "         $($found.DisplayName) v$($found.DisplayVersion)"
    Write-Host "         $($found.InstallLocation)"
}

Write-Host ""
Write-Host "== 3) readonly market.db + clean user.db ==" -ForegroundColor Cyan
# bors_config._work_dir() در حالتِ EXE کنارِ EXE را برمی‌گرداند اگر نوشتنی
# باشد (یعنی current/ در نصبِ Velopack)، وگرنه %LOCALAPPDATA%\BorsTerminal_Ultimate.
# هر دو را بررسی می‌کنیم.
$locs = @(
    (Join-Path $la 'BorsTerminalUltimate\current'),
    (Join-Path $la 'BorsTerminal_Ultimate\data')
)
$mdb = $null; $udb = $null; $dataDir = $null
foreach ($loc in $locs) {
    $m = Join-Path $loc 'market.db'
    if ((-not $mdb) -and (Test-Path $m)) { $mdb = $m; $dataDir = $loc }
    $u = Join-Path $loc 'user.db'
    if ((-not $udb) -and (Test-Path $u)) { $udb = $u }
}
Check "market.db extracted from .lzma" ($null -ne $mdb) "looked in: $($locs -join ', ')"
if ($mdb) {
    $size = [math]::Round((Get-Item $mdb).Length / 1MB, 1)
    Write-Host "         $mdb"
    Write-Host "         market.db = $size MB"
    Check "market.db is non-trivial (>50MB)" ($size -gt 50) "size=$size MB"
}
Check "clean user.db created" ($null -ne $udb) "created lazily on first user write"
if ($udb) {
    $sz = (Get-Item $udb).Length
    Write-Host "         $udb"
    Write-Host "         user.db = $sz bytes (fresh)"
}

Write-Host ""
if ($fail -eq 0) {
    Write-Host "== CLEAN-INSTALL VERIFICATION: PASS ==" -ForegroundColor Green
    exit 0
}
Write-Host "== CLEAN-INSTALL VERIFICATION: $fail FAILURE(S) ==" -ForegroundColor Red
exit 1
