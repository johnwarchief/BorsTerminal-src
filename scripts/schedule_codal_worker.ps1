# schedule_codal_worker.ps1 — ثبتِ «workerِ مستقلِ کدال» درِ Task Scheduler (اختیاری)
#
# چرا این اسکریپت هست: رشتۀ زمان‌بند داخلِ backend است، پس وقتی BorsTerminal باز
# نیست هیچ چرخۀ تازه‌ای نمی‌رود. تنها راهِ پوششِ آن بازه، یکِ executorِ بیرونی است
# که همان `codal_pipeline.py --once` را اجرا کند — همان قفل، همان checkpoint، همان
# صف؛ هیچِ سیستمِ موازی نساخته می‌شود.
#
# ── مرزِ عملیاتی (این بخش را بخوانید پیش از اجرایِ واقعی) ────────────────────
# ۱) این اسکریپت **به‌طورِ پیش‌فرض هیچ چیزی نصب نمی‌کند**. بی‌`-Install` فقط
#    فرمانی که اجرا می‌شد را چاپ می‌کند (dry-run). ایجنت/توسعه‌دهنده بدونِ مجوزِ
#    صریحِ مالک `-Install` را اجرا نمی‌کند.
# ۲) درخواستِ شبکه به `search.codal.ir` و `codal.ir` از IPِ همین ماشین می‌رود.
#    هر چرخه سقفش `DISCOVERY_MAX_PAGES` صفحه به‌ازایِ هر دسته است (پیش‌فرض ۶×۲
#    درخواستِ جستجو + بازکردنِ گزارش‌هایِ تازه). اگر BorsTerminal هم‌زمان باز
#    باشد، `crawler_busy` همان `sync_status.json` را می‌بیند و پاسِ شبکه را موکول
#    می‌کند؛ قفلِ `pipeline_lock` هم دو پردازشِ هم‌زمان رویِ یکِ اطلاعیه را
#    رد می‌کند (`skipped: "locked"`).
# ۳) اگر سیستم خاموش باشد یا شبکه قطع باشد، در آن بازه **هیچ داده‌ای دریافت
#    نمی‌شود** — ادعایِ دریافتِ پیوسته نداریم. پس از روشن‌شدن،
#    `-StartWhenAvailable` یکِ اجرا جبران می‌کند و خودِ چرخه از checkpoint
#    (نشانکِ `tracing_no` درِ `pipeline_cursor`) عقب‌ماندگی را برمی‌دارد.
# ۴) بانکِ هدف `market.db` همان فایلِ کنارِ EXE است؛ نوشتن‌ها افزودنی و
#    idempotent‌اند (`INSERT ... ON CONFLICT DO UPDATE` رویِ کلیدهایِ موجود).
#    بی‌اجرایِ بک‌اند، قفلِ SQLite تنها سازۀ همزمانی است (timeout=120s).
# ۵) حذف: `-Remove`. هیچ effect دیگری رویِ سیستم ندارد (بدونِ service، بدونِ
#    registry، بدونِ autostart).
#
# دستورِ واقعی (PowerShell، درِ ریشۀِ مخزن):
#   dry-run :  powershell -ExecutionPolicy Bypass -File scripts/schedule_codal_worker.ps1
#   install :  powershell -ExecutionPolicy Bypass -File scripts/schedule_codal_worker.ps1 -Install
#   remove  :  powershell -ExecutionPolicy Bypass -File scripts/schedule_codal_worker.ps1 -Remove

param([switch]$Install, [switch]$Remove, [int]$Hourly = 6, [string]$TaskName = "BorsCodalAutoWorker")
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
# «python» رویِ PATH معمولاً aliasِ WindowsApps است که درِ Task Scheduler (محیطِ
# غیرتعاملی) با 0x80070002 می‌شکند — مسیرِ مطلقِ مفسر از sys.executable.
$Py = ((python -c "import sys;print(sys.executable)") 2>$null)
if (-not $Py) { Write-Error "python interpreter not found on PATH"; exit 1 }
$Py = "$Py".Trim()

$Script = Join-Path $RepoRoot "codal_pipeline.py"
if (-not (Test-Path $Script)) { Write-Error "missing $Script"; exit 1 }
$Argument = "`"$Script`" --once --budget 8 --json"

Write-Host "interpreter : $Py"
Write-Host "task name   : $TaskName"
Write-Host "action      : $Py $Argument"
Write-Host "working dir : $RepoRoot"
Write-Host "cadence     : every $Hourly hour (queue backlog wakes the in-app worker sooner)"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "removed $TaskName"
    exit 0
}

if (-not $Install) {
    Write-Host ""
    Write-Host "DRY-RUN: no scheduled task was registered."
    Write-Host "Re-run with -Install (owner approval required - the agent never registers system tasks on its own)."
    exit 0
}

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) `
          -RepetitionInterval (New-TimeSpan -Hours $Hourly) `
          -RepetitionDuration (New-TimeSpan -Days 999)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
           -MultipleInstances IgnoreNew `
           -ExecutionTimeLimit (New-TimeSpan -Minutes 45)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
            -LogonType Interactive -RunLevel Limited
$action = New-ScheduledTaskAction -Execute $Py -Argument $Argument `
         -WorkingDirectory $RepoRoot

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "BorsTerminal codal auto-update worker (one durable cycle; shares the pipeline lock with the app)" | Out-Null
Write-Host "registered $TaskName"
Write-Host "status: schtasks /query /tn $TaskName /v /fo LIST"
Write-Host "log   : python codal_pipeline.py --status --json   (or the /api/fundamental/pipeline endpoint)"
