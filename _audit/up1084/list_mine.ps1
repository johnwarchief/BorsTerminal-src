$mine = Get-Process BorsTerminal_Ultimate -ErrorAction SilentlyContinue |
  Where-Object { $_.Path -like '*up1084_verify*' -or $_.Path -like '*port1084_verify*' }
if ($mine) {
  $mine | ForEach-Object { "PID $($_.Id)  $($_.Path)" }
} else {
  "none of my launched copies are running"
}
