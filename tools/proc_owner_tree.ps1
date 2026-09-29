# tools/proc_owner_tree.ps1 — which WebView2 processes belong to the live app, and
# which are orphans left behind by a previous launch/updater run.
# Prints parent-aliveness and --user-data-dir so several browser stacks can be
# told apart. ASCII only: Windows PowerShell 5.1 reads .ps1 as the ANSI codepage.
param([string]$Match = 'BorsTerminal_Ultimate|msedgewebview2')

$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match $Match })
foreach ($p in $procs) {
  $cl = '' + $p.CommandLine
  $ty = 'host'
  if ($cl -match '--type=([a-z-]+)') { $ty = $Matches[1] }
  elseif ($p.Name -match 'BorsTerminal') { $ty = 'MAIN' }
  $ws = 0.0
  try { $ws = (Get-Process -Id $p.ProcessId).WorkingSet64 / 1MB } catch {}
  $ud = '-'
  if ($cl -match '--user-data-dir="?([^"\s]+)"?') { $ud = $Matches[1] }
  $alive = [bool](Get-Process -Id $p.ParentProcessId -ErrorAction SilentlyContinue)
  '{0,-6} ppid={1,-6} type={2,-16} parentAlive={3,-5} ws={4,7} udd={5} started={6}' -f `
    $p.ProcessId, $p.ParentProcessId, $ty, $alive, ([math]::Round($ws, 1)), $ud, [string]$p.CreationDate
}

"`n---- distinct user-data-dirs ----"
$procs | ForEach-Object {
  $cl = '' + $_.CommandLine
  if ($cl -match '--user-data-dir="?([^"\s]+)"?') { $Matches[1] }
} | Group-Object | ForEach-Object { '{0,-70} procs={1}' -f $_.Name, $_.Count }
