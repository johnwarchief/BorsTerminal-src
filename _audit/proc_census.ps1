$ErrorActionPreference = 'SilentlyContinue'
$wv = Get-CimInstance Win32_Process -Filter "Name='msedgewebview2.exe'"
"webview2_total=" + @($wv).Count
$bad = @($wv | Where-Object { $_.CommandLine -match '--user-data-dir=.*\\Temp\\' })
"webview2_temp_profile=" + $bad.Count
$wv | ForEach-Object {
  $u = ''
  if ($_.CommandLine -match '--user-data-dir="([^"]+)"') { $u = $Matches[1] }
  elseif ($_.CommandLine -match '--user-data-dir=(\S+)') { $u = $Matches[1] }
  "pid=$($_.ProcessId) type=" + $(if ($_.CommandLine -match '--type=([a-z-]+)') { $Matches[1] } else { 'browser' }) + " profile=$u"
} | Select-Object -First 25
"stable_dir_exists=" + (Test-Path "$env:LOCALAPPDATA\BorsTerminal_Ultimate\webview2")
Get-ChildItem "$env:LOCALAPPDATA\BorsTerminal_Ultimate" -Directory | ForEach-Object { "sub: " + $_.Name }
$bors = Get-CimInstance Win32_Process -Filter "Name='BorsTerminal_Ultimate.exe'"
"bors_exe=" + @($bors).Count
$bors | ForEach-Object { "  pid=$($_.ProcessId) ppid=$($_.ParentProcessId) started=$($_.CreationDate)" }
$py = Get-CimInstance Win32_Process -Filter "Name='python.exe'"
"python=" + @($py).Count
$py | ForEach-Object { "  pid=$($_.ProcessId) cmd=" + $_.CommandLine.Substring(0, [Math]::Min(120, $_.CommandLine.Length)) }
