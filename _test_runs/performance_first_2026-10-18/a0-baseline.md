# A0 baseline — captured 2026-10-17 18:36:03 +0330

```
branch=mission/system2-perf-market-hours-2026-10-17 head=6907af9018e4902e6fbda739cec4459a68c9424e
origin/branch=6907af9018e4902e6fbda739cec4459a68c9424e
ls-remote main: c04026145769b316381997e6931ef07c9eb46a1d	refs/heads/main
local main=1e651b1a6247cd2d07eb95056c71b519904bb22a ; ancestor-of-origin/main: yes ; behind/ahead: 0	105
local main reflog:
1e651b1 main@{2026-10-11 18:57:11 +0330}: clone: from https://github.com/johnwarchief/BorsTerminal-src.git

worktrees:
C:/Users/Johnkallnaya/Desktop/Borsterminal/BorsTerminal-src                  ff6b2fb [mission/fts-indicator-engineering]
C:/Users/Johnkallnaya/Desktop/Borsterminal/.worktrees/handoff-system-2       5f3b0a7 [handoff/system-2/inventory-2026-10-15]
C:/Users/Johnkallnaya/Desktop/Borsterminal/.worktrees/system-2-fixtures      c68dbc0 [fix/system-2-reproducible-fixtures-2026-10-15]
C:/Users/Johnkallnaya/Desktop/Borsterminal/.worktrees/system2-audit          c040261 (detached HEAD)
C:/Users/Johnkallnaya/Desktop/Borsterminal/.worktrees/system2-perf           6907af9 [mission/system2-perf-market-hours-2026-10-17]
C:/Users/Johnkallnaya/Desktop/Borsterminal/.worktrees/system2-ui             c040261 [mission/system2-connection-ui-2026-10-17]
C:/Users/Johnkallnaya/Desktop/Borsterminal/.worktrees/ui-audit-system-2      3feb525 [mission/ui-audit-system-2-2026-10-15]
C:/Users/Johnkallnaya/Desktop/Borsterminal/.worktrees/uiux-2-0               8e165f8 [mission/uiux-2-0-redesign-2026-10-16]
C:/Users/Johnkallnaya/Desktop/Borsterminal/.worktrees/windows-stable-release c183d0d [mission/windows-stable-release-2026-10-15]

tags at origin/main: 
```

## :8000 read-only GETs
```
GET /api/update/version
{"version":"1.0.86","tauri":false,"mode":"dev","instance":"9169895f1f63"}
GET /api/market/sync-state
{"status":"success","running":false,"last":{"stage":"tsetmc","phase":"error","detail":"خطای شبکه یا فایروال (10013) در دریافت تابلوخوانی","total":0,"current":0,"symbol":"","elapsed":523.6,"percent":0.0,"ts":"2026-10-15T04:11:52"}}
GET /api/mstat/phase
{"phase":"closed","label":"پایانِ نشست","phase_source":"tsetmc_marketState","official":true,"official_state":"F","official_state_title":"بسته","session_day":20261014,"activity_h_even":181315,"is_live":false,"verdict_allowed":true,"computable":{"realized_flow":true,"order_pressure":false,"session_vs_threshold":true,"close_price_final":true},"not_computable":["order_pressure"],"why_not":{"order_pressure":"دفترِ سفارشِ همین نشست در دسترس نیست"},"data_updated_at":"2026-10-15 02:17:08","clock_now":"2026-10-17 18:36:08","session_start":"09:00","session_end":"12:30","status":"ok","source":"local:market.db"}
GET /api/sync/status
{"status":"success","sync":{"source":"global","active":false,"symbol":"","stage":"idle","detail":"","phase":"","total":0,"current":0,"percent":0.0,"elapsed":0.0,"ts":"","ban_until":""}}
```

## market.db mtimes
```
2026-10-15 03:31:13  ../../BorsTerminal-src/market.db
2026-10-17 18:14:52  ../uiux-2-0/market.db
2026-10-17 17:14:35  ./market.db
```
