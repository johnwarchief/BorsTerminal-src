# tools/proc_tree_audit.ps1
# Per-process resource split of the running app (main python/PyInstaller process +
# the WebView2 browser tree). Without this split "the app feels heavy" is not
# actionable: this prints CPU% (share of one core), Working Set, Peak WS and
# Private Bytes for every process, classified by its --type= command line, plus a
# rollup per type. ASCII only on purpose: Windows PowerShell 5.1 reads .ps1 as the
# ANSI codepage, so non-ASCII comments silently break parsing.
param(
  [int]$Seconds = 30,
  [string]$Match = 'BorsTerminal_Ultimate|msedgewebview2',
  [string]$Out = ''
)

$ErrorActionPreference = 'Stop'

function Snap($ids) {
  $h = @{}
  foreach ($p in Get-Process -Id $ids -ErrorAction SilentlyContinue) {
    $h[[int]$p.Id] = @{ cpu = $p.TotalProcessorTime.TotalSeconds; ws = $p.WorkingSet64; priv = $p.PrivateMemorySize64 }
  }
  return $h
}

$procs = Get-CimInstance Win32_Process -Filter "Name LIKE '%.exe'" |
  Where-Object { $_.Name -match $Match }
if (-not $procs) { Write-Error "no process matched '$Match'"; exit 2 }

$ids = @($procs | ForEach-Object { $_.ProcessId })
$t0 = Get-Date
$a0 = Snap $ids
Start-Sleep -Seconds $Seconds
$t1 = Get-Date
$a1 = Snap $ids
$span = ($t1 - $t0).TotalSeconds
$cores = [Environment]::ProcessorCount

$rows = foreach ($pr in $procs) {
  $id = [int]$pr.ProcessId
  if (-not $a1.ContainsKey($id)) { continue }
  $cl = '' + $pr.CommandLine
  $type = 'host'
  if ($cl -match '--type=([a-z-]+)') { $type = $Matches[1] }
  elseif ($pr.Name -match 'BorsTerminal') { $type = 'main(python)' }
  $cpu = $null
  if ($a0.ContainsKey($id)) { $cpu = [math]::Round((($a1[$id].cpu - $a0[$id].cpu) / $span) * 100, 2) }
  $peak = 0.0
  try { $peak = (Get-Process -Id $id).PeakWorkingSet64 / 1MB } catch {}
  [pscustomobject]@{
    pid            = $id
    name           = $pr.Name
    type           = $type
    cpu_percent    = $cpu
    working_set_mb = [math]::Round($a1[$id].ws / 1MB, 1)
    peak_ws_mb     = [math]::Round($peak, 1)
    private_mb     = [math]::Round($a1[$id].priv / 1MB, 1)
  }
}

$rows = @($rows | Sort-Object -Property working_set_mb -Descending)
$rows | Format-Table -AutoSize | Out-String -Width 200 | Write-Output

$byType = @($rows | Group-Object type | ForEach-Object {
  [pscustomobject]@{
    type           = $_.Name
    count          = $_.Count
    cpu_percent    = [math]::Round((($_.Group | Measure-Object cpu_percent -Sum).Sum), 2)
    working_set_mb = [math]::Round((($_.Group | Measure-Object working_set_mb -Sum).Sum), 1)
    private_mb     = [math]::Round((($_.Group | Measure-Object private_mb -Sum).Sum), 1)
  }
})
"`n---- by type ----"
$byType | Sort-Object -Property working_set_mb -Descending | Format-Table -AutoSize | Out-String -Width 200 | Write-Output

$tot = [pscustomobject]@{
  window_seconds  = [math]::Round($span, 1)
  logical_cores   = $cores
  processes       = $rows.Count
  cpu_percent_sum = [math]::Round((($rows | Measure-Object cpu_percent -Sum).Sum), 2)
  working_set_mb  = [math]::Round((($rows | Measure-Object working_set_mb -Sum).Sum), 1)
  private_mb      = [math]::Round((($rows | Measure-Object private_mb -Sum).Sum), 1)
}
"`n---- total ----"; $tot | Format-List | Out-String | Write-Output

if ($Out -ne '') {
  [pscustomobject]@{ total = $tot; byType = $byType; processes = $rows } |
    ConvertTo-Json -Depth 5 | Set-Content -Path $Out -Encoding UTF8
  "`nJSON -> $Out"
}
