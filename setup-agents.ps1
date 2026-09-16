# setup-agents.ps1 — بازسازی ایجنت‌های BorsTerminal روی یک سیستم جدید
# استفاده:
#   .\setup-agents.ps1 -RepoRoot "D:\Proj\BorsTerminal" -WorktreeRoot "D:\Proj\_worktrees"
# پس از اجرا: ۴ ورکتری + AGENTS.md هر ایجنت ساخته می‌شود و دستورات کانفیگ اپ چاپ می‌گردد.
param(
  [string]$RepoRoot     = "C:\Users\PCMOD\Desktop\BorsTerminal_Ultimate_Base",
  [string]$WorktreeRoot = "C:\Users\PCMOD\Desktop\BorsTerminal_Ultimate_Base_worktrees"
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path (Join-Path $RepoRoot '.git'))) { throw "ریپو پیدا نشد: $RepoRoot" }
New-Item -ItemType Directory -Path $WorktreeRoot -Force | Out-Null

$map = [ordered]@{
  'agent/tape'             = @{ dir='silky-arch';      name='تابلو و نبض بازار'; scope='frontend/src/features/market/**' }
  'agent/fundamental'      = @{ dir='serene-mountain'; name='بنیادی (FTS)';       scope='frontend/src/features/fundamental/**' }
  'agent/technical'        = @{ dir='neat-plateau';    name='تکنیکال (چارت)';     scope='frontend/src/features/technical/**' }
  'agent/master-portfolio' = @{ dir='mellow-brook';    name='ارشد و پرتفو';       scope='features/master/** + features/portfolio/**' }
}

$common = @'

## هماهنگی با ایجنت‌هد (main)
اگر ویرایشی خارج از قلمرو لازم شد (`contracts/**`، `app/**`، `*Math.ts` تب‌های دیگر، پایتون بک‌اند، دیتابیس‌ها):
۱) خودت ویرایش نکن. ۲) با `sessions_send` به ایجنت `main` پیام بده و دقیق بگو چه فایل/چه تغییر/چرا.
۳) ایجنت‌هد بررسی و اعمال می‌کند. ۴) در پایان، هد همهٔ برنچ‌ها را به master مرج می‌کند.

## تحویل هر مأموریت
`npx vitest run --reporter=basic > vt.log 2>&1` سبز (برای تأیید نهایی: `--no-file-parallelism`) + eslint صفر + `vite build` سالم + کامیت فقط در قلمرو خودت.
'@

Push-Location $RepoRoot
foreach ($b in $map.Keys) {
  $p = Join-Path $WorktreeRoot $map[$b].dir
  if (-not (Test-Path $p)) {
    if (-not (git rev-parse --verify --quiet $b)) { git branch $b master }
    git worktree add $p $b 2>&1 | Out-Null
    Write-Host "worktree: $($map[$b].dir) -> $b"
  } else { Write-Host "exists: $($map[$b].dir)" }

  $agents = Join-Path $p 'AGENTS.md'
  $body = @"
# AGENTS.md — $($map[$b].name)  (branch: $b)

قلمرو کاری تو: ``$($map[$b].scope)``. فقط در همین محدوده بنویس.
حریم ممنوعه: هر چیز بیرون آن (contracts، app، shared، پایتون بک‌اند، دیتابیس‌ها).
سرور مرکزی: http://127.0.0.1:8001 (سرور/دیتابیس جدید باز نکن). دادهٔ غایب ⇒ «بدون داده» صادقانه؛ بدون mock.
"@ + $common
  [System.IO.File]::WriteAllText($agents, $body, (New-Object System.Text.UTF8Encoding($false)))
  Write-Host "  AGENTS.md نوشته شد"

  $nm = Join-Path $p 'frontend\node_modules'
  if ((Test-Path (Join-Path $p 'frontend')) -and -not (Test-Path $nm)) {
    cmd /c mklink /J "$nm" "$(Join-Path $RepoRoot 'frontend\node_modules')" | Out-Null
    Write-Host "  node_modules junction ساخته شد"
  }
}
Pop-Location

Write-Host "`n=== گام‌های سمت اپ AutoClaw (دستی) ===" -ForegroundColor Cyan
Write-Host "1) در اپ، همین ۴ ایجنت را با این workspaceها بساز:"
foreach ($b in $map.Keys) { Write-Host ("   - " + $b + "  ->  " + (Join-Path $WorktreeRoot $map[$b].dir)) }
Write-Host "2) در کانفیگ gateway این دو را ست کن (یا از فایل settings منتقل کن):"
Write-Host "   tools.sessions.visibility = all"
Write-Host "   tools.agentToAgent.enabled = true"
Write-Host "3) دیتابیس‌ها (market.db/codal.db) و .env را کنار پروژه کپی کن."
