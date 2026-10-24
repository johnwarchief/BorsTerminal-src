# M1 desktop prototype (market + technical)

Real React prototype used only for the desktop-shell comparison. It reads the
same FastAPI backend and `market.db` as the production app; there is no mock
market data.

- Market board: `/api/market` (6,018 rows), filters, sort, 5 s delta polling,
  virtualized dense tape, queue/buyer-power/flags.
- Technical page: `/api/chart/<symbol>` with `/api/history` fallback,
  KLineCharts 10.0.3, raw/combined adjustment, weekly/monthly aggregation,
  MA/BOLL/RSI, three drawing tools, data-path/freshness panel.
- Other destinations are explicit “not migrated” placeholders. This prototype is
  a shell measurement, not a feature-parity candidate.

## Build and run

```bash
cd frontend
../_tools/node/node.exe node_modules/vite/bin/vite.js build --config prototype/vite.config.mjs
cd ..
.venv/Scripts/python.exe tools/desktop-migration/serve_prototype.py \
  --root frontend/prototype/dist --backend http://127.0.0.1:8102 --port 8105
```

The prototype must be served through the same-origin loopback proxy; it must not
be opened through `file://` or a bundled `tauri.localhost` origin, because the
production loopback guard rejects those origins. Login for the prototype is
`admin` / `bors123` (local demo only; not the production auth path).
