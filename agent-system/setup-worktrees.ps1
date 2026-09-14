# ساخت ۴ ورک‌تری ایجنت — از ریشهٔ چک‌اوت اصلی اجرا شود
$ErrorActionPreference = 'Stop'
$root  = (Get-Location).Path
$base  = Split-Path $root -Parent
$name  = Split-Path $root -Leaf
$wtRoot = Join-Path $base ($name + '_worktrees')

$map = @{
    'agent/tape'             = 'silky-arch'
    'agent/fundamental'      = 'serene-mountain'
    'agent/technical'        = 'neat-plateau'
    'agent/master-portfolio' = 'mellow-brook'
}
New-Item -ItemType Directory -Path $wtRoot -Force | Out-Null
foreach ($branch in $map.Keys) {
    $path = Join-Path $wtRoot $map[$branch]
    if (Test-Path $path) { Write-Host "[skip] $($map[$branch]) موجود است"; continue }
    if (-not (git rev-parse --verify --quiet $branch)) {
        git branch $branch master
        Write-Host "[branch] $branch ساخته شد"
    }
    git worktree add $path $branch
    Write-Host "[worktree] $($map[$branch]) -> $branch"
    # npm ci داخل frontend هر ورک‌تری (یک‌بار، اختیاری — ایجنت خودش هم می‌زند):
    # Push-Location (Join-Path $path 'frontend'); npm ci; Pop-Location
}
git worktree list
Write-Host "`nبعد از این، در محیط agent خود ۴ سشن بسازید: هر سشن روی پوشهٔ ورک‌تری‌اش + SystemPrompt از agent-system/agents/<name>.md"
