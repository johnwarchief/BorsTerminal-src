# Desktop migration measurement kit (M0/M1)

Everything here is additive: no production route, algorithm or API contract is
modified. The harness only issues read-only GETs and kills processes it started.

## What is measured

| Metric | Source |
| --- | --- |
| Shell init (process → WebView2 CDP ready) | `bench_shell.mjs` (`cdpMs`) |
| Login → app chrome ready | `shellReadyMs` |
| Market board usable (real `/api/market` rows rendered) | `marketReadyMs` |
| Technical page usable (`/api/chart` rendered in KLineCharts) | `technicalReadyMs` |
| Shell RAM / CPU (process tree) | `Win32_Process` snapshot at idle |
| Scrolling responsiveness | rAF frame intervals while scrolling the board |
| API latency / payload | `tools/performance/bench_api.py` + resource timings |
| Screenshots 1366×768 / 1920×1080 | `run-N/*.png` |

`NOT_MEASURED` is recorded rather than estimated when a value cannot be
obtained (for example, a shell that never exposes CDP).

## Prerequisites (this machine)

- Portable Node 22.22.0 at `_tools/node` (used by Vite, Vitest, Puppeteer).
- Python 3.12.10 venv at `.venv` (`uv pip install -r requirements.txt`).
- `market.db` extracted from the release snapshot `data-latest`
  (6,018 instruments, max `d_even=20261014`, 129,577 daily rows,
  8,723 financial statements). Same snapshot for every option.
- All benchmark runs use `BORS_NO_FETCH_LOOPS=1` and `BORS_CODAL_AUTO=0`, so no
  instance polls TSETMC during comparison. Live fetching is a separate,
  single-instance test.

## Commands

```bash
# backend (read-only benchmark mode)
BORS_NO_FETCH_LOOPS=1 BORS_CODAL_AUTO=0 .venv/Scripts/python.exe \
  -m uvicorn app:app --host 127.0.0.1 --port 8102

# current shell (pywebview + React served by FastAPI)
_tools/node/node.exe tools/desktop-migration/bench_shell.mjs \
  --label pywebview-dev --runs 3 --backend http://127.0.0.1:8102 --cdp 9300

# shipped portable EXE (self-contained backend + window; run 1 extracts data)
_tools/node/node.exe tools/desktop-migration/bench_shell.mjs \
  --label portable-1.0.97 --shell exe \
  --path _tools/shell-1.0.97/BorsTerminal_Ultimate.exe \
  --backend http://127.0.0.1:8101 --cdp 9600 \
  --self-contained 1 --cold-data 1 --runs 3

# prototype build + same-origin API proxy
cd frontend && ../_tools/node/npm.cmd exec vite build -- --config prototype/vite.config.mjs
.venv/Scripts/python.exe tools/desktop-migration/serve_prototype.py \
  --root frontend/prototype/dist --backend http://127.0.0.1:8102 --port 8105

# prototype shell benchmark (pywebview first, then the same URL under Tauri)
_tools/node/node.exe tools/desktop-migration/bench_shell.mjs \
  --label proto-pywebview --runs 3 --backend http://127.0.0.1:8105 --cdp 9700 \
  --ready-selector '[data-testid="proto-shell"]' \
  --market-nav '[data-testid="proto-nav-market"]' \
  --tech-nav '[data-testid="proto-nav-technical"]' \
  --market-row '[data-testid="market-row"]' \
  --tech-ready '[data-testid="chart-host"] canvas' \
  --scroll '[data-testid="market-scroll"]' \
  --args 'tools/desktop-migration/launch_proto_pywebview.py --url http://127.0.0.1:8105/'
```

## Security contract

The prototype server is a same-origin loopback proxy, so the production
`loopback_guard` (`app.py`) sees `Host: 127.0.0.1` and a loopback `Origin`.
`Origin: null` is never allowed and no CORS rule is added. A shell that loads
its UI from `file://` or `tauri.localhost` cannot call the API without a real
native bridge; that is measured as a compatibility finding, not bypassed.

## Additional M1 tools

```bash
# TinyJS window/API/RAM probe (no CDP; PrintWindow screenshots)
.venv/Scripts/python.exe tools/desktop-migration/bench_tinyjs.py --runs 3

# focused API/data-path probe for the two prototype pages
.venv/Scripts/python.exe tools/desktop-migration/bench_proto_api.py \
  --base http://127.0.0.1:8102 --reps 10

# Host/Origin contract on backend and prototype proxy
.venv/Scripts/python.exe tools/desktop-migration/check_guard.py

# technical-page functional smoke against a shell with CDP
_tools/node/node.exe tools/desktop-migration/ui_smoke.mjs --cdp 9810
```

`serve_prototype.py` enforces the same loopback Host/Origin contract as
`app.loopback_guard` before proxying. This is not optional: the first version
rewrote `Host` upstream without checking it, so an external Host reached the
backend as 200. That bug was found during M0 and fixed; `check_guard.py` is the
regression check.

TinyJS does not forward `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS`. Its in-page heap,
console errors and frame timings are `NOT_MEASURED`; do not fill them with
estimates. The prototype proxy and all benchmark shells bind/connect only to
`127.0.0.1`.
