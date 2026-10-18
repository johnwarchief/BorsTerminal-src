# _audit/perf/procs.ps1 — Stage 0: شمارشِ فرایندهایِ مرتبط با برنامه با CPU/RAM/IO
# فقط خواندنی. دو نمونه با فاصله می‌گیرد تا درصدِ CPU معنادار باشد.
param([int]$SampleSeconds = 5)
$ErrorActionPreference = 'SilentlyContinue'

$pat = 'python|node|msedge|Bors|bors|uvicorn|tauri|electron'
$before = @{}
Get-CimInstance Win32_Process | Where-Object {
  $_.Name -match $pat -or $_.CommandLine -match 'app\.py|BorsTerminal|market\.db'
} | ForEach-Object {
  $before[[int]$_.ProcessId] = (Get-Process -Id $_.ProcessId).TotalProcessorTime
}
$names = @{}
Get-CimInstance Win32_Process | Where-Object {
  $_.Name -match $pat -or $_.CommandLine -match 'app\.py|BorsTerminal|market\.db'
} | ForEach-Object { $names[[int]$_.ProcessId] = $_ }

Start-Sleep -Seconds $SampleSeconds

foreach ($pid2 in ($names.Keys | Sort-Object)) {
  $p = Get-Process -Id $pid2
  if (-not $p) { continue }
  $ci = $names[$pid2]
  $cpuPct = 0
  if ($before.ContainsKey($pid2)) {
    $dt = ($p.TotalProcessorTime - $before[$pid2]).TotalMilliseconds
    $cpuPct = [math]::Round($dt / ($SampleSeconds * 1000) * 100, 1)
  }
  $io = $p.PagedMemorySize64 / 1MB
  "PID=$pid2 NAME=" + $p.ProcessName + " WS_MB=" + [math]::Round($p.WorkingSet64 / 1MB, 1) +
    " Priv_MB=" + [math]::Round($p.PrivateMemorySize64 / 1MB, 1) + " Peak_MB=" + [math]::Round($p.PeakWorkingSet64 / 1MB, 1) +
    " Threads=" + $p.Threads.Count + " CPU%/" + $SampleSeconds + "s=" + $cpuPct +
    " TotalCPU_s=" + [math]::Round($p.TotalProcessorTime.TotalSeconds, 1) +
    " Started=" + $p.StartTime + " PATH=" + $p.Path
  "   CMD=" + $ci.CommandLine
}

"--- listening ports (app-relevant) ---"
$conns = Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 8000, 8001, 8002, 5173, 5174, 1420, 3000 }
foreach ($c in $conns) {
  $owner = Get-Process -Id $c.OwningProcess
  "LISTEN " + $c.LocalAddress + ":" + $c.LocalPort + " pid=" + $c.OwningProcess + " name=" + $owner.ProcessName
}
"--- total ---"
$all = Get-Process | Where-Object { $_.ProcessName -match 'python|node|msedge' }
"python+node+msedge processes: " + $all.Count + "  combined_WS_MB: " + [math]::Round(($all | Measure-Object WorkingSet64 -Sum).Sum / 1MB, 0)
