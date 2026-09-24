# release.ps1 — تولید نسخه‌های BorsTerminal Ultimate از ریشهٔ ریپو اجرا کن
#   .\release.ps1 setup      → فقط نصب‌کننده (setup.exe)
#   .\release.ps1 base       → فقط آرشیو بیس‌کد خام
#   .\release.ps1 portable   → باندل قابل‌حمل (بدون نصب)
#   .\release.ps1 patch      → پچِ دلتای امضاشده (فقط تغییرات، بدونِ نصبِ کامل)
#   .\release.ps1 all        → هر سه
#   .\release.ps1 allpatch   → همه + پچِ دلتا
#
# v1.0.20: کانالِ Velopack و bors_exe_onedir.spec حذف شدند. آن‌ها هرگز منتشر
# نشدند — چیزی که کاربر اجرا می‌کند onedirِ fts_terminal.spec با نصب‌کنندهٔ Inno و
# آپدیترِ درون‌برنامه‌ایِ پایتون (api/update.py) است. کامنتِ قبلی می‌گفت «بیلدِ
# اصلی onedir + Velopack شد» که نادرست بود و همین، سه مسیرِ متضادِ ریلیز ساخته بود.
# جزئیات: plans/production-packaging-and-unpark-plan.md
#
# v1.0.10: پچِ دلتا. PATCH_FROM نسخهٔ قبلیِ منتشرشده است (پیش‌فرض 1.0.9)؛
# آپدیتِرِ درون‌برنامه‌ای فقط روی همان نسخه پچ را اعمال می‌کند و در غیر این
# صورت شفافاً به نصبِ کامل برمی‌گردد. پچ با همان کلیدِ minisign امضا می‌شود.
param([ValidateSet('setup','base','portable','all','patch','allpatch','release')][string]$Mode = 'setup',
      [string]$PatchFrom = '1.0.9',
      [string]$Baseline = '',
      [string]$Dist = 'dist',
      [switch]$SkipTests = $false)
$ErrorActionPreference = 'Stop'

# --- تنظیمات مسیرها (در صورت تفاوت، این‌ها را عوض کن) ---
# ابزارها: اگر متغیرِ محیطی داده نشده باشد از PATH پیدا می‌شوند. مسیرهایِ
# مطلقِ دست‌نویس رویِ هر ماشینِ دیگر (و رویِ CI) می‌شکستند و ریلیز را وسطِ کار
# می‌خواباندند؛ پس حالا فقط فال‌بک‌اند، نه پیش‌فرضِ اجباری.
function Resolve-Tool([string]$envName, [string]$cmd, [string]$fallback) {
    $fromEnv = (Get-Item -Path "Env:$envName" -ErrorAction SilentlyContinue).Value
    if ($fromEnv) { return $fromEnv }
    $g = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($g) { return $g.Source }
    if ($fallback -and (Test-Path $fallback)) { return $fallback }
    Write-Error "tool '$cmd' not found - set environment variable $envName to its full path. ABORT."
    exit 1
}
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path (Join-Path $root 'bors_entry.py'))) { $root = (Get-Location).Path }
Set-Location $root

# Where the build output goes. Windows sometimes keeps a handle on
# dist\BorsTerminal_Ultimate (search indexer / Defender / IDE watcher) and
# PyInstaller then dies in rmtree. A release must not wedge on that:
#     .\release.ps1 setup -Dist dist2
$DistRoot = Join-Path $root $Dist
$Bundle   = Join-Path $DistRoot 'BorsTerminal_Ultimate'

# مفسرِ بیلد = مفسرِ CI. .venvِ پروژه همان 3.12 + requirements.txt است؛
# پایتونِ PATH می‌تواند مفسری بدونِ pywebview باشد، و بیلدِ چنین مفسری EXEیِ
# «سالم» می‌دهد که فقط پنجرهٔ بومی‌اش حذف شده و بی‌صدا به msedge --app
# می‌افتد. پس venv مقدم است و BORS_PY راهِ فرارِ صریح می‌ماند.
$venvPy = Join-Path $root '.venv\Scripts\python.exe'
if ($env:BORS_PY) { $PY = $env:BORS_PY }
elseif (Test-Path $venvPy) { $PY = $venvPy }
else { $PY = Resolve-Tool 'BORS_PY' 'python' 'C:\Users\PCMOD\AppData\Local\Python\pythoncore-3.14-64\python.exe' }
$NPM  = Resolve-Tool 'BORS_NPM'  'npm'    'C:\Program Files\AutoClaw\resources\node\npm.cmd'
$ISCC = Resolve-Tool 'BORS_ISCC' 'iscc'   'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'

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

    # توجه: PowerShell 5.1 هنگامِ ارسالِ آرگومان به یک EXE بومی، کوتیشنهایِ
    # دوتاییِ جاسازی‌شده را می‌بلعد و کدِ پایتونِ زیر می‌شکست:
    #   sqlite3.connect(file:market.db?mode=ro,uri=True)  ← SyntaxError
    # و سپس Ensure-Db بهاشتباه «دیتابیسِ ناقص» تشخیص می‌داد و ریلیز را
    # متوقف می‌کرد. راه‌حل: کلِّ اسکریپتِ درون‌خطی فقط کوتیشنِ تکی است؛
    # برایِ رشتهٔ تحتِاللفظیِ SQL از chr(34) ساخته می‌شود.
    Write-Host '[db] validating source market.db'
    & $PY scripts\check_release_db.py
    if ($LASTEXITCODE -ne 0) {
        Write-Error '[db] source market.db is incomplete — refusing to overwrite the committed market.db.lzma baseline. ABORT.'
        exit 1
    }

    if (Test-Path 'market.db.lzma') {
        Copy-Item 'market.db.lzma' 'market.db.lzma.bak' -Force
        Write-Host '[db] backed up previous market.db.lzma -> market.db.lzma.bak'
    }
    # فشرده‌سازی + round-trip هم در همان فایل انجام می‌شود (دلیل: همان
    # مشکلِ بلعیده‌شدنِ کوتیشن توسطِ PowerShell 5.1).
    Write-Host '[db] compressing market.db -> market.db.lzma'
    & $PY scripts\check_release_db.py --pack
    if ($LASTEXITCODE -ne 0) {
        Write-Error '[db] market.db.lzma round-trip verification FAILED — restored previous baseline. ABORT.'
        exit 1
    }
}
function Build-Frontend {
    Write-Host '[fe] npm install + build'
    Push-Location frontend; & $NPM install --no-audit --no-fund; & $NPM run build; Pop-Location
}
# v1.0.11 (Phase B): بیلدِ اصلی onedir شد. onefile یک CArchiveِ فشردهٔ واحد
# است → diffِ دو بیلد تقریباً هیچ پس‌اندازی ندارد (به همین دلیل «دلتای»
# فعلی از خودِ exe هم بزرگتر است). onedir هر DLL/PYD را جدا نگه می‌دارد،
# پس باینری‌های تغییرنکرده به ~0 دیف می‌شوند. specِ onefile برای نسخهٔ
# portable نگه داشته شده است.
$ExeSpec = 'fts_terminal.spec'

function Build-Exe {
    Write-Host "[exe] PyInstaller ($ExeSpec)"
    # پیش‌چکِ مفسر: یک دقیقه زودتر از چکِ پسازبیلد می‌گوید کدام پکیج در این
    # مفسر نیست (بودجهٔ بیلد ~۲ دقیقه است و بیلدِ ناقص، ریلیزِ ناقص).
    & $PY scripts\check_build_env.py
    if ($LASTEXITCODE -ne 0) { Write-Error '[exe] build interpreter is missing a declared dependency. ABORT.'; exit 1 }
    & $PY -m PyInstaller $ExeSpec --noconfirm --distpath "$DistRoot" --workpath "$root\build"
    if ($LASTEXITCODE -ne 0) { Write-Error '[exe] PyInstaller failed. ABORT.'; exit 1 }
    # قراردادِ onedir: _internal/ باید باشد، همهٔ api.* در hiddenimports،
    # و پنجرهٔ بومی (webview/pythonnet) داخلِ باندل باشد.
    if (-not (Test-DistBundle)) { Write-Error '[exe] onedir contract FAILED. ABORT.'; exit 1 }
}
function Move-StaleDist([string]$why, [string]$detail) {
    # دیستارِ قدیمی را دور نمی‌اندازیم و ریلیز را هم با آن نمی‌سازیم: یک‌بار
    # به dist\BorsTerminal_Ultimate.stale قرنطینه می‌شود (برگشت‌پذیر) و همان
    # مرحله، بیلدِ تازه را روِ همان مسیر می‌سازد. پیش‌تر این نقطه با
    # «dist\ را خودت پاک کن و دوباره بزن» می‌ایستاد و تک‌دستوری‌بودنِ
    # ریلیز را می‌شکست.
    $dir = Join-Path $DistRoot 'BorsTerminal_Ultimate'
    $quar = $dir + '.stale'
    Write-Host ("[dist] stale build output -> " + $why) -ForegroundColor Yellow
    if ($detail) { Write-Host ("[dist] " + $detail) -ForegroundColor Yellow }
    if (Test-Path $quar) { Remove-Item $quar -Recurse -Force }
    try {
        Move-Item $dir $quar -Force
        Write-Host ("[dist] previous output kept for rollback at " + $quar)
    } catch {
        Write-Error ("[dist] could not move the stale output aside: " + $_.Exception.Message + " - remove dist\BorsTerminal_Ultimate and re-run. ABORT.")
        exit 1
    }
}

function Test-DistBundle {
    # آیا خروجیِ موجود، همان باندلِ موردِ توافق است؟ چک در Build-Exe فقط
    # مسیرِ «بیلدِ نو» را می‌پوشاند، ولی Build-Setup/Portable/Patch می‌توانند
    # یک distیِ از پیش موجود را بسته‌بندی کنند — همان راهی که باندلِ بی‌پنجره
    # (بدونِ webview) را به نصابِ امضاشده رساند.
    # توجه: خروجیِ stdoutِ فرمانِ بومی بخشی از مقدارِ بازگشتیِ تابع می‌شود،
    # پس گرفتنش در $out و چاپِ دستی با Write-Host الزامی است.
    $out = & $PY dev/onedir_contract_v11.py --dist "$DistRoot" 2>&1
    $ok = ($LASTEXITCODE -eq 0)
    $out | ForEach-Object { Write-Host ("  " + $_) }
    return $ok
}

function Assert-DistFresh {
    # جلوگیری از بسته‌بندیِ یک distیِ قدیمی در نصابِ جدید. ریشهٔ یک کلاس
    # باگِ خطرناک: اگر dist/ از قبل وجود داشته باشد، Build-Setup/Build-Portable
    # بدونِ هیچ بررسی‌ای دوباره از آن استفاده می‌کنند. پس اگر اپِ فریزشده
    # قدیمی‌تر از منابع باشد (مثلاً بعد از bumpِ نسخه یا یک فیکس، rebuild
    # نشده باشد)، یا نسخه‌اش با bors_setup.iss یکی نباشد، اینجا همان خروجیِ کهنه
# قرنطینه و از نو ساخته می‌شود — بسته‌بندیِ distِ قدیمی هرگز رخ نمی‌دهد.
    $exe = Join-Path $DistRoot 'BorsTerminal_Ultimate\BorsTerminal_Ultimate.exe'
    if (-not (Test-Path $exe)) { return }
    $built = (Get-Item $exe).LastWriteTime

    $issVer = $null
    $iss = Get-Content (Join-Path $root 'installer\bors_setup.iss') -Raw
    if ($iss -match '(?m)^\s*#define\s+AppVersion\s+"([^"]+)"') { $issVer = $Matches[1] }

    $appVer = $null
    $cfg = Join-Path $DistRoot 'BorsTerminal_Ultimate\_internal\bors_config.py'
    if (-not (Test-Path $cfg)) { $cfg = Join-Path $DistRoot 'BorsTerminal_Ultimate\bors_config.py' }
    if (Test-Path $cfg) {
        $m = [regex]::Match((Get-Content $cfg -Raw), 'APP_VERSION\s*=\s*"([^"]+)"')
        if ($m.Success) { $appVer = $m.Groups[1].Value }
    }
    if ($issVer -and $appVer -and ($appVer -ne $issVer)) {
        # نصابی که نسخه‌اش با سرِ نصب‌کننده نمی‌خواند هرگز نباید بسته شود؛
        # ولی پاسخ درست «بیلدِ دوباره» است نه «دستورِ دستی به کاربر».
        Move-StaleDist ("frozen app is v" + $appVer + " but bors_setup.iss is v" + $issVer) `
                       "after a version bump the app is rebuilt from source"
        return
    }

    # آنچه داخلِ باندل می‌رود، تازگی‌اش هم باید بررسی شود. فهرست را از خودِ
    # spec می‌خوانیم: فهرستِ دستی (بورس‌کانفیک/انتری/…) تغییرِ fts_engine.py
    # را «تازه» نمی‌دانست و نصاب با کدِ کهنهٔ موتورِ FTS بسته می‌شد.
    $specSrc = ''
    if (Test-Path (Join-Path $root 'fts_terminal.spec')) {
        $specSrc = Get-Content (Join-Path $root 'fts_terminal.spec') -Raw
    }
    # bors_setup.iss در این فهرست نیست: داخلِ باندل نمی‌رود، پس تغییرش نباید
    # rebuildِ PyInstaller بخواهد (تطابقِ نسخه‌اش پایین‌تر چک می‌شود).
    $watch = @('bors_config.py','bors_entry.py','bors_minisign.py','codal_fetcher.py',
               'fts_engine.py','mstat_engine.py','watchlist_store.py','app.py',
               'bootstrap_first_run.py','bors_flags.py',
               'fts_terminal.spec','bors_setup.spec',
               'frontend/package.json','frontend/package-lock.json',
               'frontend/src-tauri/tauri.conf.json')
    $watch += @([regex]::Matches($specSrc, "\('([A-Za-z0-9_./-]+\.(?:py|json))',\s*'\.'\)") |
                 ForEach-Object { $_.Groups[1].Value })
    $watch = @($watch | Sort-Object -Unique)

    $stale = @()
    foreach ($f in $watch) {
        $p = Join-Path $root ($f -replace '/', '\')
        if ((Test-Path $p) -and ((Get-Item $p).LastWriteTime -gt $built)) { $stale += $f }
    }
    foreach ($d in 'api','frontend/src') {
        $p = Join-Path $root $d
        if (Test-Path $p) {
            # __pycache__/*.pyc فقط محصولِ اجرایِ تست‌ها/کامپایل هستند، نه
            # تغییرِ منبع. بدونِ این فیلتر، صرفِ «python dev\test_*.py» کردن
            # گارد را به‌اشتباه روشن می‌کرد و rebuildِ بی‌دلیل می‌خواست.
            Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object { $_.LastWriteTime -gt $built -and
                               $_.FullName -notmatch '\\__pycache__\\' -and
                               $_.Extension -ne '.pyc' } |
                ForEach-Object { $stale += $_.FullName.Substring($root.Length + 1) }
        }
    }
    if ($stale.Count) {
        $shown = ($stale | Select-Object -First 8) -join ', '
        if ($stale.Count -gt 8) { $shown += (" … (+{0} more)" -f ($stale.Count - 8)) }
        Move-StaleDist 'dist is older than these sources' $shown
        return
    }
    Clear-DistRuntime          # هر سه مسیرِ بسته‌بندی از اینجا می‌گذرند
    if (-not (Test-DistBundle)) {
        Move-StaleDist 'the existing bundle fails the onedir contract' `
                       'the packaged app is missing what the contract requires - rebuilding'
    }
}
function Assert-TestsGreen {
    # درگاهِ سبزِ سوئیت‌ها: هیچ ریلیزی نباید با تستِ قرمز بیرون برود.
    # این همان قراردادی که plans/production-packaging-and-unpark-plan.md
    # در هر ریزمرحلهٔ آن را تعهد کردیم. -SkipTests فقط برایِ دیباگِ محلی است.
    if ($SkipTests) { Write-Host '[tests] skipped (-SkipTests)'; return }
    Write-Host '[tests] dev/run_all_tests.py'
    & $PY dev/run_all_tests.py
    if ($LASTEXITCODE -ne 0) {
        Write-Error '[tests] SUITES FAILED — a red suite cannot ship. ABORT.'
        exit 1
    }
    Write-Host '[tests] ALL SUITES PASSED' -ForegroundColor Green
}


function Clear-DistRuntime {
    # هر چه هنگامِ *اجرای* باندل در پوشهٔ آن نوشته شده، از بسته‌بندی بیرون
    # می‌ماند. شواهد: بعد از یک تستِ دودِ محلی، نصابِ v1.0.20 پوشهٔ logs/،
    # .screener_cache.json (822 کیب)، market.db.baseline، market.db.part-shm/-wal
    # و market_sync/sync_summary را با خودش به ماشینِ کاربر برد. بدترین‌شان
    # baseline است: یک *مُهرِ* نسخهٔ دیگر را روی نصبِ تازه می‌گذارد.
    $b = "$Bundle"
    if (-not (Test-Path $b)) { return }
    $files = 'market.db','market.db-wal','market.db-shm','market.db.baseline',
             'market.db.stale','market.db.stale-wal','market.db.stale-shm',
             'codal.db','.screener_cache.json','market_sync.json','sync_summary.json',
             'codal_control.json','codal_db_status.json','user.db','fts_thresholds.json'
    $dirs = 'logs','backups','__pycache__'
    $gone = @()
    foreach ($f in $files) {
        $p = Join-Path $b $f
        if (Test-Path $p) { Remove-Item $p -Force -Recurse -ErrorAction SilentlyContinue; $gone += $f }
    }
    foreach ($d in $dirs) {
        $p = Join-Path $b $d
        if (Test-Path $p) { Remove-Item $p -Recurse -Force -ErrorAction SilentlyContinue; $gone += ($d + '/') }
    }
    foreach ($p in (Get-Item (Join-Path $b '*.db.part*') -ErrorAction SilentlyContinue)) {
        Remove-Item $p -Force -ErrorAction SilentlyContinue; $gone += $p.Name
    }
    if ($gone.Count) { Write-Host ('[dist] removed runtime artifacts from the bundle: ' + ($gone -join ', ')) -ForegroundColor Yellow }
}

function Build-Setup {
    Assert-DistFresh
    if (-not (Test-Path "$Bundle\BorsTerminal_Ultimate.exe")) { Build-Frontend; Build-Exe }
    if (Test-Path 'market.db.lzma') { Copy-Item 'market.db.lzma' "$Bundle\market.db.lzma" -Force }
    # هر باقی‌ماندهٔ زمانِ اجرا از باندل بیرون می‌ماند؛ خودِ این پاک‌سازی در
    # Assert-DistFresh است تا مسیرهایِ portable/patch هم از آن بی‌بهره نمانند.
    # بازارِ داده کنارِ EXE باندل می‌شود، داخلِ آن نه. نبودش یعنی اپ بالا
    # می‌آید ولی تابلو خالی است — و نصاب هم ساخته می‌شود، پس این تنها جایی است
    # که می‌توان جلویِ ریلیزِ بی‌داده را گرفت.
    $distLzma = "$Bundle\market.db.lzma"
    if (-not (Test-Path $distLzma) -or (Get-Item $distLzma).Length -lt 1MB) {
        Write-Error '[setup] market.db.lzma is not beside the EXE (missing or under 1 MB) - nothing would be installed. ABORT.'
        exit 1
    }
    Write-Host ('[setup] market.db.lzma beside exe: ' + [math]::Round((Get-Item $distLzma).Length / 1MB, 1) + ' MB')
    Write-Host '[setup] Inno Setup'
    & $ISCC "$root\installer\bors_setup.iss"
    if ($LASTEXITCODE -ne 0) {
        # پیش از این خط نبود: ISCC با «Compile aborted» برمی‌گشت، اسکریپت به
        # Sign-Setup می‌رفت و نصابِ نسخهٔ *قبلی* را که هنوز در out/ مانده بود
        # امضا می‌کرد و «انجام شد» می‌گفت. یعنی ریلیزِ شکسته، ریلیز خوانده
        # می‌شد. خروجِ ISCC تنها معیارِ موفقیت است.
        Write-Error '[setup] Inno compilation FAILED - nothing new was produced. ABORT.'
        exit 1
    }
    Get-ChildItem "$root\installer\out\*.exe" | ForEach-Object { Write-Host ("  -> " + $_.FullName + "  (" + [math]::Round($_.Length/1MB,1) + " MB)") }
    Sign-Setup
}

function Sign-Setup {
    # امضای minisign (Ed25519 روی blake2b-512) که آپدیتِرِ tauri لازم دارد.
    # کلِ منطق در scripts/sign_setup.py: اول tauri signer (با timeout سخت)،
    # سپس fallbackِ minisignِ خالصِ پایتون، و در پایان تأییدِ امضا. بدونِ امضای
    # معتبر آپدیتِر این بیلد را رد می‌کند — پس بیلد را اینجا متوقف می‌کنیم.
    # نامِ فایل باید نسخهٔ همان بیلد را داشته باشد، وگرنه «تازه‌ترین فایل» می‌تواند
    # نصابِ دو نسخه قبل باشد و امضاشودگیش به‌عنوانِ آپدیتِ جدید منتشر شود.
    $iss = Get-Content (Join-Path $root 'installer\bors_setup.iss') -Raw
    $want = $null
    if ($iss -match '(?m)^\s*#define\s+AppVersion\s+"([^"]+)"') { $want = $Matches[1] }
    $cands = Get-ChildItem "$root\installer\out\BorsTerminal_Ultimate_Setup_*.exe" |
             Sort-Object LastWriteTime -Descending
    if (-not $cands) { Write-Host '[sign] no installer found (skip)'; return }
    $setup = $cands | Select-Object -First 1
    if ($want -and ($setup.Name -notlike ("*_v" + $want + "*.exe"))) {
        Write-Error ("[sign] newest installer is " + $setup.Name + " but the build is v" + $want +
                     " - the compile did not produce it. ABORT.")
        exit 1
    }
    Write-Host '[sign] minisign (tauri-first, python fallback, verify)'
    & $PY "$root\scripts\sign_setup.py" $setup.FullName
    if ($LASTEXITCODE -ne 0) {
        Write-Error '[sign] signature missing or invalid — the updater would reject this build. ABORT.'
        exit 1
    }
    Get-ChildItem "$root\installer\out\*.sig" | ForEach-Object { Write-Host ("  -> " + $_.Name + "  (" + [math]::Round($_.Length/1KB,1) + " KB)") }
}
function Publish-Release {
    # ریلیز + آپلودِ نصاب، .sig و latest.json رویِ گیت‌هاب. نسخه را خودِ اسکریپت
    # از bors_config.APP_VERSION می‌خواند (دست‌نویس نیست) و متنِ یادداشت‌ها را از
    # docs/RELEASE_NOTES.md برمی‌دارد.
    Write-Host '[publish] github release + latest.json'
    & $PY "$root\scripts\publish_github_release.py"
    if ($LASTEXITCODE -ne 0) {
        Write-Error '[publish] release failed - the updater endpoint still serves the previous version. ABORT.'
        exit 1
    }
}

function Build-Base {
    $out = "$root\..\BorsTerminal_BaseCode_$ver.zip"
    Write-Host "[base] git archive -> $out"
    if (Test-Path $out) { Remove-Item $out -Force }
    # 'master' دیگر وجود ندارد (شاخه main است) و این خط هر بار بی‌صدا
    # آرشیوِ ناقص می‌ساخت؛ HEAD یعنی همان چیزی که بیلد می‌شود.
    git archive --format=zip --output="$out" HEAD
    Write-Host ("  -> " + $out + "  (" + [math]::Round((Get-Item $out).Length/1MB,2) + " MB)")
}
function Build-Portable {
    Assert-DistFresh
    if (-not (Test-Path "$Bundle\BorsTerminal_Ultimate.exe")) { Build-Frontend; Build-Exe }
    $stage = "$root\releases\portable_$ver"
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    Copy-Item "$Bundle\*" $stage -Recurse -Force
    if (Test-Path 'market.db.lzma') { Copy-Item 'market.db.lzma' "$stage\market.db.lzma" -Force }
    Write-Host "[portable] staged: $stage"
}

function Build-Patch {
    # v1.0.10: پچِ دلتای امضاشده. scripts/make_patch.py کلِ distِ تازه را به
    # یک zipِ overlay تبدیل می‌کند (بدونِ دیتای کاربر)، Version.txt را مهر
    # می‌زند و با همان کلیدِ minisign امضا می‌کند. این پچ فقط رویِ
    # $PatchFrom اعمال می‌شود؛ آپدیتِر در غیر این صورت نصبِ کامل را می‌زند.
    #
    # $Baseline مسیرِ نصبِ نسخهٔ مبدأ است. وقتی داده شود، پچ فقط فایلهای
    # تغییرکرده/جدید را شامل می‌شود (دلتای واقعی)؛ در غیر این صورت همهٔ
    # فایلها (overlayِ کامل) که برای نصبِ قدیمیِ فاقدِ apply_update.bat
    # سازگار می‌ماند.
    Assert-DistFresh
    if (-not (Test-Path "$Bundle\BorsTerminal_Ultimate.exe")) { Build-Frontend; Build-Exe }
    if ($Baseline) {
        Write-Host "[patch] delta $PatchFrom -> (current)  baseline=$Baseline  signed"
        & $PY "$root\scripts\make_patch.py" --from $PatchFrom --baseline $Baseline
    } else {
        Write-Host "[patch] delta $PatchFrom -> (current)  full-overlay  signed"
        & $PY "$root\scripts\make_patch.py" --from $PatchFrom
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error '[patch] make_patch.py failed — the delta update would be broken. ABORT.'
        exit 1
    }
    Get-ChildItem "$DistRoot\BorsTerminal_Patch_*.zip", "$DistRoot\BorsTerminal_Patch_*.zip.sig" -ErrorAction SilentlyContinue |
        ForEach-Object { Write-Host ("  -> " + $_.Name + "  (" + [math]::Round($_.Length/1MB,2) + " MB)") }
}

# حلقهٔ نگهبان: تا سوئیتِ گاردها سبز نشود هیچ خروجی‌ای ساخته نمی‌شود.
# این تابع قبلاً تعریف شده بود ولی هیچ‌جا صدا زده نمی‌شد، یعنی ریلیز با تستِ
# قرمز از نظرِ ظاهری کاملاً ممکن بود.
Assert-TestsGreen

switch ($Mode) {
    'base'      { Build-Base }
    'setup'     { Ensure-Db; Build-Setup }
    'portable'  { Ensure-Db; Build-Portable }
    'patch'     { Ensure-Db; Build-Patch }
    'all'       { Ensure-Db; Build-Base; Build-Setup; Build-Portable }
    'allpatch'  { Ensure-Db; Build-Base; Build-Setup; Build-Portable; Build-Patch }
    'release'   {
        # تک‌دستوریِ کامل: دیتابیس ← بیلد ← نصاب ← امضا ← انتشارِ گیت‌هاب.
        Ensure-Db; Build-Setup; Publish-Release
    }
}
Write-Host '== done' -ForegroundColor Green
