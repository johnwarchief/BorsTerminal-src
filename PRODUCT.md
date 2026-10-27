# Product

<!-- impeccable:product-schema 1 -->

## Platform

web (desktop shell: Tauri 2 window + local FastAPI; the design language stays web — a native wrapper does not make it native). Desktop (Windows) is the current and first target. A mobile build is planned later; its form (responsive web surface vs native Android) is not decided yet and must not drive current design decisions.

## Stack

Chosen and in progress: new frontend app `frontend-v2/` (React 18 + TypeScript + Vite 5 + Tailwind 4 + TanStack Query/Virtual + Zustand + Zod), talking to the existing FastAPI backend; the old React app stays as the fallback until route parity. Backend language stays Python for now (owner ruling, option B; option C open at his call).

## Users

Single operator: the owner, a Tehran stock-market trader/analyst who trades with this terminal daily and holds the physical FTS notebook as the method authority. Works in Persian RTL on Windows desktop, viewports 1366×768 through 2560×1440, often at market open.

## Product Purpose

A local-first desktop terminal for the Tehran market: board (تابلو), FTS tape screening, technical analysis, fundamentals/Codal, watchlist, portfolio, strategy tools. Success means: faithful to the FTS notebook and Rahavard behavior, fast, and visually excellent — in that owner priority order (visual quality and speed co-first, then data trust).

## Positioning

The notebook-exact FTS funnel plus Rahavard-parity technicals, running offline against a local database — not a generic charting website. The mechanism others cannot copy is the test/parity corpus and the notebook rules encoded in guards.

## Operating Context

Installed Windows app (onedir + Inno Setup), local `market.db`/`user.db`, Codal auto-update, market-hours automations; daily use before/at market open; screenshots and same-instant comparisons as verification; the old app remains runnable as the fallback during the migration.

## Capabilities and Constraints

- 11 routes: master (default), market, market-status, notifications, technical, engine-lab, fundamental, strategy-tree, portfolio, sarkhati, watch.
- Frozen contracts that must not be re-implemented differently: `price_basis`, `candle_contract`, `codal_periods`.
- Backend constraints: `numpy==2.0.2` pin; at most ONE live TSETMC loop; no real orders (Sarkhati simulation only); never delete/rewrite an operational DB or WAL.
- Repo rules: `fetch` only in the shared HTTP door; Persian digits only through helpers; Persian-only RTL copy with notebook vocabulary.
- Parity gates: Rahavard (technical/adjustment) and the FTS notebook; no invented thresholds or methodology.
- Time-boxed coexistence: replace each route after equivalence, then retire the old one (no two permanent versions).

## Brand Commitments

Name: BorsTerminal / بورس‌ترمینال. Persian-only RTL, dark default (brass direction in the approved prototype), notebook vocabulary, no metaphors in visible copy, short labels.

## Evidence on Hand

- `docs/BorsTerminal-Desktop-Migration-Decisions.md` (510-line authoritative record + §13 owner ruling: option B chosen, option C open).
- Approved visual reference: prototype v2 market page (`Desktop\BorsTerminal_migration_v2`, served at 5302) and its live-data preview (`_audit/preview/market_live`, 5303).
- D1 shell proof (Tauri window inside the product) and the performance baseline of the installed app.
- Gap matrix, screenshots at 1366/1920/2560, and 100+ existing guards as the acceptance corpus.

## Product Principles

1. Visual quality and speed are co-first; data trust gates them.
2. The notebook and Rahavard are the authority; thresholds are never invented.
3. Evidence over assumption: same-instant comparisons, numbers in reports, no self-declared PASS.
4. Local-first, one live loop, no secrets in the repo, no destructive DB operations.
5. The old app is the source of domain truth and the temporary fallback; it is replaced only after parity.

## Accessibility & Inclusion

Reduced-motion respected; Persian RTL; supports 1366×768 (compact density) and scales to 2K/4K.

## Open Decisions

- **Confirmed 2026-10-28 by the owner:** single operator (the owner); priority order is visual quality and speed co-first, then data trust; Windows desktop is the first target.
- **Mobile later (owner, 2026-10-28):** a mobile build is wanted after the desktop rebuild; the mobile form (responsive web surface vs native Android) is still undecided.
- **Workflow setting not yet recorded:** how new surfaces are built — comp-first (an image sets the bar before code) or code-first (build directly). Asked separately; nothing stored until answered.
