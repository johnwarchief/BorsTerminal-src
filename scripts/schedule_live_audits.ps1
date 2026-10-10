# schedule_live_audits.ps1 — زمان‌بندیِ دو Jobِ مستقلِ پایشِ زنده (فاز ۴)
#
# دو taskِ مستقلِ Windows Task Scheduler می‌سازد؛ شکستِ یکی دیگری را متوقف نمی‌کند.
# اجرا را به باز بودنِ ترمینالِ کدنویس وابسته نمی‌کند (RunWhetherUserLoggedOnOrNot).
# پنجرۀِ نشست: شنبه..چهارشنبۀِ ۰۸:۴۵ تا ۱۲:۳۰ تهران — هر ۱۵ دقیقه یک‌بار؛ خودِ
# اسکریپتِ پایتون هم خارجِ پنجره بی‌عمل می‌شود (in_session) و قفلِ تک‌نسخه دارد،
# پس اجرایِ هم‌زمانِ تکراری رخ نمی‌دهد.
#
# نصب (از PowerShellِ ادمین، درِ ریشۀِ مخزن):
#   powershell -ExecutionPolicy Bypass -File scripts/schedule_live_audits.ps1
# حذف:
#   powershell -ExecutionPolicy Bypass -File scripts/schedule_live_audits.ps1 -Remove
#
# تعطیلات: TSETMC درِ روزهایِ تعطیل تابلو را باز نمی‌کند؛ feed کهنگیِ خودش را
# دارد و Jobِ FTS بر اساسِ آخرینِ کندلِ موجود رأی می‌دهد. روزِ تعطیل، task اجرا
# می‌شود اما دادهٔ تازه‌ای نیست — این «اجرایِ از‌دست‌رفته» نیست، اجرا شده است.
#
# از‌دست‌رفتنِ اجرا: اگر سیستم خاموش بوده، Task Scheduler «StartWhenAvailable»
# اجرا را پس از روشن‌شدن جبران می‌کند؛ لاگِ هر دور درِ _audit/<job>/audit-*.jsonl
# با observed_at ثبت می‌شود، پس می‌توان دید کدامِ پنجره پوششِ داده نشده است.

param([switch]$Remove)
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
# «python» رویِ PATH معمولاً aliasِ WindowsApps است که درِ Task Scheduler (محیطِ
# غیرتعاملی) با 0x80070002 «file not found» می‌شکند. مسیرِ مطلقِ مفسرِ واقعی را
# از sys.executable می‌گیریم.
$Py = ((python -c "import sys;print(sys.executable)") 2>$null)
if (-not $Py) { $Py = "python" }
$Py = "$Py".Trim()
Write-Host "interpreter: $Py"
$Jobs = @(
  @{ Id="BorsFTSLiveAudit";  Script="tools\fts_live_audit.py";        Arg="--limit 0" },
  @{ Id="BorsTapeLiveAudit"; Script="tools\market_tape_live_audit.py"; Arg="--limit 0 --compare 12" }
)

foreach ($j in $Jobs) {
  if ($Remove) {
    Unregister-ScheduledTask -TaskName $j.Id -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "removed $($j.Id)"
    continue
  }
  $workdir = $RepoRoot
  $argument = "`"$workdir\$($j.Script)`" $($j.Arg)"
  $action = New-ScheduledTaskAction -Execute $Py -Argument $argument -WorkingDirectory $workdir
  # شنبه..چهارشنبه ۰۸:۴۵ هر ۱۵ دقیقه تا ۴ ساعت. Repetition را از یک triggerِ -Once
  # می‌گیریم و رویِ -Weekly می‌گذاریم؛ -Weekly مستقیماً -RepetitionInterval قبول نمی‌کند.
  $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday,Sunday,Monday,Tuesday,Wednesday -At "08:45"
  $rep = (New-ScheduledTaskTrigger -Once -At "08:45" `
            -RepetitionInterval (New-TimeSpan -Minutes 15) `
            -RepetitionDuration (New-TimeSpan -Hours 4)).Repetition
  $trigger.Repetition = $rep
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
             -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
             -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)
  # S4U (اجرا حتی وقتی کاربر خارج است) ادمین می‌خواهد؛ اگر رد شد، به Interactive
  # برمی‌گردیم (وقتی درِ ویندوز لاگین هستید اجرا می‌شود — به باز بودنِ ترمینالِ
  # کدنویس وابسته نیست).
  try {
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
    Register-ScheduledTask -TaskName $j.Id -Action $action -Trigger $trigger -Settings $settings `
             -Principal $principal -Description "BorsTerminal live audit ($($j.Id))" -Force | Out-Null
    Write-Host "registered $($j.Id) [S4U] -> $Py $argument"
  } catch {
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $j.Id -Action $action -Trigger $trigger -Settings $settings `
             -Principal $principal -Description "BorsTerminal live audit ($($j.Id))" -Force | Out-Null
    Write-Host "registered $($j.Id) [Interactive — S4U لازم‌داشت ادمین] -> $Py $argument"
  }
}
