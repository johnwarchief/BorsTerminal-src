# میزکار چندپنلی تابلاخوانی — نقشهٔ پیاده‌سازی

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** تبدیل صفحهٔ تابلاخوانی به یک میزکارِ تایلی با کارت‌های قابل‌تنظیم، کاشیِ نماد و چارت، دیده‌بان‌های منتقل‌شده، و سایدبارِ پروتوتایپ.

**Architecture:** یک درختِ تقسیمِ خالص در `shared/workspace` چیدمان را نگه می‌دارد و `WorkspaceShell` آن را رندر می‌کند. محتوای هر کاشی از `features/market` و `features/chart` می‌آید؛ یک اندپوینتِ تازهٔ `market-snapshot` تغذیه‌کنندهٔ کارت‌های کل‌بازار است و بقیهٔ کارت‌ها از ردیف‌های بارگذاری‌شدهٔ تابلو می‌خوانند.

**Tech Stack:** React 18.3، TypeScript 5.9، Vite 5.4، Tailwind 4، Zustand 5، TanStack Query 5، Zod 4، klinecharts 10، Vitest 3 + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-28-market-workspace-design.md` (کامیت `d79527b4`)

## Global Constraints

- همهٔ کارها در `frontend-v2/` و بک‌اندِ ریشه انجام می‌شوند؛ شاخه `mission/4-axes-2026-10-10` و هیچ Push به `main`.
- `fetch` بیرون از `frontend-v2/src/shared/api/http.ts` ممنوع است.
- ایمپورت‌ها فقط با الیاس‌های `@app`, `@shared`, `@features`.
- ارقامِ نمایشی با `faNum`/`toFaDigits` و کلاس `.num`؛ متنِ رابط فارسی و RTL.
- هیچ عددِ غایب به صفر تبدیل نمی‌شود؛ `—` با دلیل.
- هیچ نوشتنی روی `market.db` عملیاتی؛ سنجشِ زنده با `BORS_NO_FETCH_LOOPS=1` روی بانکِ جدا.
- `numpy==2.0.2` و `fts_terminal.spec` دست نمی‌خورند؛ در این نقشه فایلِ `api/*.py` تازه‌ای ساخته نمی‌شود.
- پس از هر تسک: `npx vitest run` سبز و `npx tsc -b` صفر خطا. لینت در `frontend-v2` وجود ندارد.
- کامیتِ فارسی با heredoc و بدونِ backtick؛ فقط فایل‌های همان تسک `git add` می‌شوند.
- PASS بصری اعلام نمی‌شود؛ اسکرین‌شات و اعداد به مالک داده می‌شود.

---

## ساختارِ فایل‌ها

| فایل | مسئولیت |
|---|---|
| `mstat_engine.py` | خوانندهٔ سریِ `market_index` و سازندهٔ payloadِ snapshot |
| `api/market_status.py` | روتِ `/api/mstat/market-snapshot` |
| `frontend-v2/src/shared/workspace/types.ts` | نوع‌های چیدمان، برچسب‌ها و کف‌های اندازه |
| `frontend-v2/src/shared/workspace/layout.ts` | عملیاتِ خالصِ درخت + هندسه + نگاشتِ RTL |
| `frontend-v2/src/shared/workspace/store.ts` | ذخیرهٔ میزکار در `bors-workspace-v1` |
| `frontend-v2/src/shared/workspace/shortcuts.ts` | تنها منبعِ میانبرها |
| `frontend-v2/src/shared/workspace/useTileKeyboard.ts` | فلش‌ها، `Alt+۱…۴`، `Ctrl+Z` |
| `frontend-v2/src/shared/workspace/TileFrame.tsx` | سرِ کاشی، منو، نشانِ پیرو، حلقهٔ فوکوس |
| `frontend-v2/src/shared/workspace/Splitter.tsx` | تغییرِ اندازه با اشاره‌گر |
| `frontend-v2/src/shared/workspace/WorkspaceShell.tsx` | رندرِ درخت و تمرکز |
| `frontend-v2/src/features/market/panels/BoardPanel.tsx` | استخراجِ تابلو از `MarketPage` |
| `frontend-v2/src/features/market/api/useMarketSnapshot.ts` | اسکیمای snapshot |
| `frontend-v2/src/features/market/components/cards/registry.ts` | کاتالوگِ کارت‌ها |
| `frontend-v2/src/features/market/components/cards/CardTile.tsx` | رندر و پیش‌نمایشِ کارت |
| `frontend-v2/src/features/market/components/SnapshotStrip.tsx` | نوارِ کارت‌ها و شخصی‌سازی |
| `frontend-v2/src/features/market/panels/SymbolPanel.tsx` | کاشیِ نماد |
| `frontend-v2/src/features/market/panels/WatchPanel.tsx` | کاشیِ دیده‌بان‌ها |
| `frontend-v2/src/features/chart/api/useChart.ts` | قراردادِ `/api/chart` |
| `frontend-v2/src/features/chart/ui/ChartPanel.tsx` | چارتِ کندل |
| `frontend-v2/src/features/market/routes/MarketStatusPage.tsx` | صفحهٔ وضعیت بازار |
| `frontend-v2/src/features/notifications/**` | مرکزِ اعلان |
| `frontend-v2/src/app/shell/Sidebar.tsx` | سایدبارِ گروه‌بندی‌شده + راهنما |
| `frontend-v2/src/app/shell/AppShell.tsx` | استفاده از `Sidebar` و مسیرها |

---

## Task 1: خوانندهٔ سری و اندپوینتِ snapshot

**Files:**
- Create: `dev/test_market_index_series.py`
- Modify: `mstat_engine.py` (پایینِ `market_index`)
- Modify: `api/market_status.py` (کنارِ دیگر روت‌های mstat)

**Interfaces:**
- Produces:
  - `market_index_series(conn, limit=1) -> list[dict]` با کلیدهای `d_even,last,change,pct,ew_last,ew_change,ew_pct,z_tot_tran,q_tot_cap,q_tot_tran`
  - `market_snapshot(conn) -> dict` با کلیدهای `status,asof,index,prev,market,retail`
  - `GET /api/mstat/market-snapshot`

- [ ] **Step 1: تستِ ناکام بنویس**

```python
# dev/test_market_index_series.py
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import mstat_engine as M  # noqa: E402

fails = []


def say(ok, msg):
    print("  %s %s" % ("PASS" if ok else "FAIL", msg))
    if not ok:
        fails.append(msg)


def make_db(with_totals=True):
    con = sqlite3.connect(":memory:")
    totals = ", z_tot_tran REAL, q_tot_cap REAL, q_tot_tran REAL" if with_totals else ""
    con.execute("CREATE TABLE market_index (d_even INTEGER PRIMARY KEY, idx_last REAL,"
                " idx_change REAL, idx_pct REAL, ew_last REAL, ew_change REAL,"
                " ew_pct REAL%s)" % totals)
    if with_totals:
        con.execute("INSERT INTO market_index VALUES (20261027, 100, 1, 1.0, 90, 1, 1.1,"
                    " 700000, 400000000000000.0, 9000000000.0)")
        con.execute("INSERT INTO market_index VALUES (20261028, 110, 10, 10.0, 95, 5, 5.5,"
                    " 800000, 500000000000000.0, 10000000000.0)")
    else:
        con.execute("INSERT INTO market_index VALUES (20261027, 100, 1, 1.0, 90, 1, 1.1)")
    return con


con = make_db()
series = M.market_index_series(con, 2)
say(len(series) == 2, "series returns 2 rows")
say(series[0]["d_even"] == 20261028, "series is newest-first")
say(series[0]["z_tot_tran"] == 800000, "z_tot_tran is read")
say(series[1]["q_tot_cap"] == 400000000000000.0, "previous q_tot_cap is read")

con2 = make_db(with_totals=False)
legacy = M.market_index_series(con2, 1)
say(len(legacy) == 1, "legacy schema still answers")
say(legacy[0]["z_tot_tran"] is None, "legacy schema gives None, not zero")

M.macro_health = lambda _conn: {"market_value_hemat": 8123.4, "value_hemat": 45.6,
                                 "state": "good", "label": "مساعد",
                                 "good_min": 20, "bad_max": 10, "excellent_min": 50,
                                 "basis": "x", "cause": None}
snap = M.market_snapshot(make_db())
say(snap["status"] == "ok", "snapshot status ok")
say(snap["index"]["last"] == 110, "index is the newest row")
say(snap["prev"]["d_even"] == 20261027, "prev is the previous session")
say(snap["market"]["trades"] == 800000, "market.trades comes from z_tot_tran")
say(snap["market"]["trade_value_hemat"] == 50.0, "trade value converts rial to hemat")
say(snap["retail"]["value_hemat"] == 45.6, "retail comes from macro")
say(snap["retail"]["bad_max"] == 10, "thresholds are passed through")

print("\n%d failed" % len(fails))
sys.exit(1 if fails else 0)
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal && PYTHONIOENCODING=utf-8 python dev/test_market_index_series.py`
Expected: FAIL با `AttributeError: module 'mstat_engine' has no attribute 'market_index_series'`

- [ ] **Step 3: پیاده‌سازیِ خواننده و snapshot**

در `mstat_engine.py`، تابعِ فعلیِ `market_index` را با این دو تابع جایگزین کن (نام و امضای `market_index` حفظ می‌شود):

```python
def market_index_series(conn, limit=1):
    """سریِ رسمیِ شاخص از `market_index` — تنها نقطهٔ خواندنِ این جدول.

    ستون‌های گردش (`z_tot_tran`, `q_tot_cap`, `q_tot_tran`) در بانکِ کهنه
    ممکن است نباشند؛ در آن حالت None برمی‌گردند، نه صفر.
    """
    n = max(1, min(int(limit or 1), 60))
    wide = ("d_even, idx_last, idx_change, idx_pct, ew_last, ew_change, ew_pct,"
            " z_tot_tran, q_tot_cap, q_tot_tran")
    try:
        rows = conn.execute("SELECT %s FROM market_index ORDER BY d_even DESC LIMIT ?" % wide,
                            (n,)).fetchall()
        has_totals = True
    except sqlite3.Error:
        rows = conn.execute("SELECT d_even, idx_last, idx_change, idx_pct, ew_last,"
                            " ew_change, ew_pct FROM market_index ORDER BY d_even DESC"
                            " LIMIT ?", (n,)).fetchall()
        has_totals = False

    def _opt(v):
        x = _f(v)
        return x if x else None

    out = []
    for r in rows:
        out.append({"d_even": int(r[0]),
                    "last": _opt(r[1]), "change": _opt(r[2]), "pct": _opt(r[3]),
                    "ew_last": _opt(r[4]), "ew_change": _opt(r[5]), "ew_pct": _opt(r[6]),
                    "z_tot_tran": _opt(r[7]) if has_totals else None,
                    "q_tot_cap": _opt(r[8]) if has_totals else None,
                    "q_tot_tran": _opt(r[9]) if has_totals else None})
    return out


def market_index(conn):
    """سازگاریِ مصرف‌کنندگانِ فعلی: فقط شش کلیدِ پیشین."""
    series = market_index_series(conn, 1)
    if not series:
        return None
    row = series[0]
    return {k: row[k] for k in ("d_even", "last", "change", "pct",
                                "ew_last", "ew_change", "ew_pct")}


def market_snapshot(conn):
    """یک payload برای نوارِ کارت‌ها: شاخص، نشستِ قبل، بازار و خرد."""
    series = market_index_series(conn, 2)
    cur = series[0] if series else None
    prev = series[1] if len(series) > 1 else None
    macro = macro_health(conn)
    index = ({k: cur[k] for k in ("d_even", "last", "change", "pct",
                                  "ew_last", "ew_change", "ew_pct")}
             if cur else None)
    market = {
        "trade_value_hemat": (round(cur["q_tot_cap"] / HEMAT_FROM_RIAL, 2)
                              if cur and cur.get("q_tot_cap") else None),
        "volume": cur.get("q_tot_tran") if cur else None,
        "trades": cur.get("z_tot_tran") if cur else None,
        "market_value_hemat": macro.get("market_value_hemat"),
    }
    retail = {k: macro.get(k) for k in ("value_hemat", "state", "label", "basis",
                                        "cause", "good_min", "bad_max",
                                        "excellent_min")}
    return {"status": "ok",
            "asof": {"d_even": cur["d_even"] if cur else None},
            "index": index, "prev": prev, "market": market, "retail": retail}
```

در `api/market_status.py`، کنارِ `/api/mstat/smart-money`:

```python
@router.get("/api/mstat/market-snapshot")
def mstat_market_snapshot():
    """یک payload برای کارت‌های بالای تابلو؛ با کشِ همان لایهٔ mstat."""
    return _mstat_call(_mstat.market_snapshot)
```

- [ ] **Step 4: تست را سبز کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal && PYTHONIOENCODING=utf-8 python dev/test_market_index_series.py`
Expected: `13 failed` → `0 failed`

- [ ] **Step 5: کامیت**

```bash
git add dev/test_market_index_series.py mstat_engine.py api/market_status.py
git commit -m "$(cat <<'EOF'
feat(mstat): خوانندهٔ سریِ شاخص و اندپوینتِ market-snapshot

سریِ رسمی با ستون‌های گردش، بازگشتِ امن برای بانکِ کهنه، و یک payload
برای کارت‌های بالای تابلو.
EOF
)"
```

---

## Task 2: درختِ چیدمان و هندسهٔ RTL

**Files:**
- Create: `frontend-v2/src/shared/workspace/types.ts`
- Create: `frontend-v2/src/shared/workspace/layout.ts`
- Test: `frontend-v2/src/__tests__/workspace-layout.spec.ts`

**Interfaces:**
- Produces:
  - `LayoutNode`, `TilePanel`, `SplitDir`, `PANEL_LABEL`, `PANEL_MIN`, `DEFAULT_LAYOUT`
  - `panelsInOrder(root) -> Array<{id,panel,follow}>`
  - `splitTile(root,tileId,dir,newPanel,makeId?) -> LayoutNode|null`
  - `closeTile(root,tileId) -> LayoutNode|null`
  - `neighborOf(root,tileId,dir) -> string|null` با `dir: 'left'|'right'|'up'|'down'`
  - `swapWithNeighbor(root,tileId,dir) -> {root,movedTo}|null`
  - `clampRatio(node,ratio,width,height) -> number|null`
  - `ratioFromPointer(rect,dir,x,y) -> number`
  - `isValidLayout(node) -> boolean`

- [ ] **Step 1: تستِ ناکام بنویس**

```ts
// frontend-v2/src/__tests__/workspace-layout.spec.ts
import { describe, expect, it } from 'vitest';
import {
  DEFAULT_LAYOUT, clampRatio, closeTile, isValidLayout, neighborOf, panelsInOrder,
  ratioFromPointer, splitTile, swapWithNeighbor, type LayoutNode,
} from '@shared/workspace/layout';

const ids = (root: LayoutNode) => panelsInOrder(root).map((p) => p.panel);

describe('layout tree', () => {
  it('reads panels right-to-left then top-to-bottom', () => {
    expect(ids(DEFAULT_LAYOUT)).toEqual(['board', 'symbol', 'watch']);
  });

  it('splits the focused tile and refuses a duplicate panel', () => {
    const next = splitTile(DEFAULT_LAYOUT, 't-symbol', 'col', 'chart', () => 't-new');
    expect(next).not.toBeNull();
    expect(panelsInOrder(next!).map((p) => p.panel).sort()).toEqual(['board', 'chart', 'symbol', 'watch']);
    expect(splitTile(next!, 't-symbol', 'col', 'chart', () => 't-x')).toBeNull();
  });

  it('refuses to split beyond four tiles', () => {
    const four = splitTile(DEFAULT_LAYOUT, 't-symbol', 'col', 'chart', () => 't-chart')!;
    expect(splitTile(four, 't-board', 'row', 'chart', () => 't-dup')).toBeNull();
  });

  it('closes a tile and collapses its parent', () => {
    const closed = closeTile(DEFAULT_LAYOUT, 't-watch');
    expect(closed).not.toBeNull();
    expect(ids(closed!)).toEqual(['board', 'symbol']);
    expect(closeTile(DEFAULT_LAYOUT, 't-board')).toBeNull();
  });

  it('finds the visual neighbour in RTL', () => {
    expect(neighborOf(DEFAULT_LAYOUT, 't-board', 'left')).toBe('t-symbol');
    expect(neighborOf(DEFAULT_LAYOUT, 't-symbol', 'right')).toBe('t-board');
    expect(neighborOf(DEFAULT_LAYOUT, 't-symbol', 'down')).toBe('t-watch');
  });

  it('swaps payloads and keeps tree ids stable', () => {
    const moved = swapWithNeighbor(DEFAULT_LAYOUT, 't-symbol', 'down')!;
    expect(moved.movedTo).toBe('t-watch');
    expect(panelsInOrder(moved.root).map((p) => p.panel)).toEqual(['board', 'watch', 'symbol']);
    expect(moved.root.kind).toBe('split');
  });

  it('clamps ratio by pixel minimums and refuses impossible splits', () => {
    expect(clampRatio(DEFAULT_LAYOUT, 0.95, 1400, 700)).toBeCloseTo(0.6, 5);
    expect(clampRatio(DEFAULT_LAYOUT, 0.68, 1000, 700)).toBeNull();
  });

  it('maps pointer position to ratio from the start edge', () => {
    expect(ratioFromPointer({ left: 0, top: 0, width: 1000, height: 600 }, 'row', 300, 0)).toBeCloseTo(0.7);
    expect(ratioFromPointer({ left: 0, top: 0, width: 1000, height: 600 }, 'col', 0, 300)).toBeCloseTo(0.5);
  });

  it('rejects an invalid layout', () => {
    const noBoard: LayoutNode = { kind: 'tile', id: 'x', panel: 'symbol', follow: true };
    expect(isValidLayout(noBoard)).toBe(false);
    expect(isValidLayout(DEFAULT_LAYOUT)).toBe(true);
  });
});
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/workspace-layout.spec.ts`
Expected: FAIL با `Failed to resolve import "@shared/workspace/layout"`

- [ ] **Step 3: نوع‌ها را بنویس**

```ts
// frontend-v2/src/shared/workspace/types.ts
export type TilePanel = 'board' | 'symbol' | 'watch' | 'chart';
export type SplitDir = 'row' | 'col';
export type MoveDir = 'left' | 'right' | 'up' | 'down';

export type LayoutNode =
  | { kind: 'tile'; id: string; panel: TilePanel; follow: boolean }
  | { kind: 'split'; id: string; dir: SplitDir; ratio: number;
      first: LayoutNode; second: LayoutNode };

export const PANEL_LABEL: Record<TilePanel, string> = {
  board: 'تابلو',
  symbol: 'نماد',
  watch: 'دیده‌بان‌ها',
  chart: 'چارت',
};

export const PANEL_MIN: Record<TilePanel, { w: number; h: number }> = {
  board: { w: 520, h: 240 },
  symbol: { w: 300, h: 200 },
  watch: { w: 260, h: 180 },
  chart: { w: 320, h: 140 },
};

export const MAX_DEPTH = 3;
export const MAX_TILES = 4;

export const DEFAULT_LAYOUT: LayoutNode = {
  kind: 'split', id: 's-root', dir: 'row', ratio: 0.68,
  first: { kind: 'tile', id: 't-board', panel: 'board', follow: false },
  second: {
    kind: 'split', id: 's-right', dir: 'col', ratio: 0.58,
    first: { kind: 'tile', id: 't-symbol', panel: 'symbol', follow: true },
    second: { kind: 'tile', id: 't-watch', panel: 'watch', follow: false },
  },
};
```

- [ ] **Step 4: عملیاتِ خالص را بنویس**

```ts
// frontend-v2/src/shared/workspace/layout.ts
import {
  DEFAULT_LAYOUT, MAX_DEPTH, MAX_TILES, PANEL_MIN,
  type LayoutNode, type MoveDir, type SplitDir, type TilePanel,
} from './types';

export * from './types';

export function panelsInOrder(node: LayoutNode): Array<{ id: string; panel: TilePanel; follow: boolean }> {
  if (node.kind === 'tile') return [{ id: node.id, panel: node.panel, follow: node.follow }];
  return [...panelsInOrder(node.first), ...panelsInOrder(node.second)];
}

export function findTile(node: LayoutNode, id: string): Extract<LayoutNode, { kind: 'tile' }> | null {
  if (node.kind === 'tile') return node.id === id ? node : null;
  return findTile(node.first, id) ?? findTile(node.second, id);
}

export function depthOf(node: LayoutNode): number {
  if (node.kind === 'tile') return 1;
  return 1 + Math.max(depthOf(node.first), depthOf(node.second));
}

function tileCount(node: LayoutNode): number {
  return node.kind === 'tile' ? 1 : tileCount(node.first) + tileCount(node.second);
}

export function splitTile(
  root: LayoutNode, tileId: string, dir: SplitDir, newPanel: TilePanel,
  makeId: (prefix: string) => string = defaultId,
): LayoutNode | null {
  if (tileCount(root) >= MAX_TILES) return null;
  if (findTile(root, tileId) === null) return null;
  if (panelsInOrder(root).some((p) => p.panel === newPanel)) return null;

  function walk(node: LayoutNode, depth: number): { node: LayoutNode; done: boolean } {
    if (node.kind === 'tile') {
      if (node.id !== tileId || depth >= MAX_DEPTH) return { node, done: false };
      return {
        done: true,
        node: {
          kind: 'split', id: makeId('s'), dir, ratio: 0.5,
          first: node,
          second: { kind: 'tile', id: makeId('t'), panel: newPanel, follow: true },
        },
      };
    }
    const a = walk(node.first, depth + 1);
    if (a.done) return { node: { ...node, first: a.node }, done: true };
    const b = walk(node.second, depth + 1);
    if (b.done) return { node: { ...node, second: b.node }, done: true };
    return { node, done: false };
  }

  const out = walk(root, 1);
  return out.done ? out.node : null;
}

export function closeTile(root: LayoutNode, tileId: string): LayoutNode | null {
  if (findTile(root, tileId)?.panel === 'board') return null;

  function walk(node: LayoutNode): { node: LayoutNode | null; closed: boolean } {
    if (node.kind === 'tile') {
      return node.id === tileId ? { node: null, closed: true } : { node, closed: false };
    }
    const a = walk(node.first);
    if (a.closed) return { node: a.node ?? node.second, closed: true };
    const b = walk(node.second);
    if (b.closed) return { node: b.node ?? node.first, closed: true };
    return { node, closed: false };
  }

  return walk(root).node;
}

interface Rect { x: number; y: number; w: number; h: number }

function rects(node: LayoutNode, rect: Rect, out: Map<string, Rect>): void {
  if (node.kind === 'tile') {
    out.set(node.id, rect);
    return;
  }
  if (node.dir === 'row') {
    const firstW = rect.w * node.ratio;
    rects(node.first, { x: rect.x + rect.w - firstW, y: rect.y, w: firstW, h: rect.h }, out);
    rects(node.second, { x: rect.x, y: rect.y, w: rect.w - firstW, h: rect.h }, out);
  } else {
    const firstH = rect.h * node.ratio;
    rects(node.first, { x: rect.x, y: rect.y, w: rect.w, h: firstH }, out);
    rects(node.second, { x: rect.x, y: rect.y + firstH, w: rect.w, h: rect.h - firstH }, out);
  }
}

function tileRects(root: LayoutNode): Map<string, Rect> {
  const out = new Map<string, Rect>();
  rects(root, { x: 0, y: 0, w: 1, h: 1 }, out);
  return out;
}

export function neighborOf(root: LayoutNode, tileId: string, dir: MoveDir): string | null {
  const map = tileRects(root);
  const from = map.get(tileId);
  if (!from) return null;
  let best: { id: string; gap: number; overlap: number } | null = null;

  for (const [id, r] of map) {
    if (id === tileId) continue;
    const overlap = dir === 'left' || dir === 'right'
      ? Math.min(from.y + from.h, r.y + r.h) - Math.max(from.y, r.y)
      : Math.min(from.x + from.w, r.x + r.w) - Math.max(from.x, r.x);
    if (overlap <= 0.0001) continue;

    const gap = dir === 'right' ? r.x - (from.x + from.w)
      : dir === 'left' ? from.x - (r.x + r.w)
      : dir === 'down' ? r.y - (from.y + from.h)
      : from.y - (r.y + r.h);
    if (gap < -0.0001) continue;

    if (!best || gap < best.gap - 0.0001 || (Math.abs(gap - best.gap) <= 0.0001 && overlap > best.overlap)) {
      best = { id, gap, overlap };
    }
  }
  return best ? best.id : null;
}

export function swapWithNeighbor(
  root: LayoutNode, tileId: string, dir: MoveDir,
): { root: LayoutNode; movedTo: string } | null {
  const target = neighborOf(root, tileId, dir);
  if (!target) return null;
  const a = findTile(root, tileId);
  const b = findTile(root, target);
  if (!a || !b) return null;

  function walk(node: LayoutNode): LayoutNode {
    if (node.kind === 'tile') {
      if (node.id === a!.id) return { ...node, panel: b!.panel, follow: b!.follow };
      if (node.id === b!.id) return { ...node, panel: a!.panel, follow: a!.follow };
      return node;
    }
    return { ...node, first: walk(node.first), second: walk(node.second) };
  }

  return { root: walk(root), movedTo: target };
}

function minExtent(node: LayoutNode, axis: 'w' | 'h'): number {
  if (node.kind === 'tile') return PANEL_MIN[node.panel][axis];
  const sameAxis = (node.dir === 'row') === (axis === 'w');
  return sameAxis
    ? minExtent(node.first, axis) + minExtent(node.second, axis)
    : Math.max(minExtent(node.first, axis), minExtent(node.second, axis));
}

export function clampRatio(node: LayoutNode, ratio: number, width: number, height: number): number | null {
  if (node.kind !== 'split') return null;
  const total = node.dir === 'row' ? width : height;
  if (total <= 0) return null;
  const axis = node.dir === 'row' ? 'w' : 'h';
  const lo = minExtent(node.first, axis) / total;
  const hi = 1 - minExtent(node.second, axis) / total;
  if (lo > hi) return null;
  return Math.min(hi, Math.max(lo, ratio));
}

export function ratioFromPointer(
  rect: { left: number; top: number; width: number; height: number },
  dir: SplitDir, x: number, y: number,
): number {
  const raw = dir === 'row'
    ? (rect.left + rect.width - x) / Math.max(1, rect.width)
    : (y - rect.top) / Math.max(1, rect.height);
  return Math.min(0.95, Math.max(0.05, raw));
}

export function isValidLayout(node: unknown): node is LayoutNode {
  let board = 0;
  let total = 0;

  function walk(n: unknown, depth: number): boolean {
    if (!n || typeof n !== 'object') return false;
    const item = n as Record<string, unknown>;
    if (item.kind === 'tile') {
      total += 1;
      if (!['board', 'symbol', 'watch', 'chart'].includes(String(item.panel))) return false;
      if (item.panel === 'board') board += 1;
      return typeof item.id === 'string' && typeof item.follow === 'boolean';
    }
    if (item.kind === 'split') {
      if (depth >= MAX_DEPTH) return false;
      const ratio = Number(item.ratio);
      if (!(ratio >= 0.05 && ratio <= 0.95)) return false;
      if (item.dir !== 'row' && item.dir !== 'col') return false;
      return walk(item.first, depth + 1) && walk(item.second, depth + 1);
    }
    return false;
  }

  return walk(node, 1) && board === 1 && total <= MAX_TILES;
}

let counter = 0;
function defaultId(prefix: string): string {
  counter += 1;
  return `${prefix}-${Date.now().toString(36)}-${counter}`;
}
```

- [ ] **Step 5: تست را سبز کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/workspace-layout.spec.ts`
Expected: PASS (۹ تست)

- [ ] **Step 6: کامیت**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/shared/workspace/types.ts frontend-v2/src/shared/workspace/layout.ts frontend-v2/src/__tests__/workspace-layout.spec.ts
git commit -m "$(cat <<'EOF'
feat(workspace): درختِ چیدمان و هندسهٔ RTL

split/close/swap/neighbour با کفِ پیکسلی، نسبت از اشاره‌گر و اعتبارسنجیِ چیدمان.
EOF
)"
```

---

## Task 3: ذخیره‌گاهِ میزکار

**Files:**
- Create: `frontend-v2/src/shared/workspace/store.ts`
- Test: `frontend-v2/src/__tests__/workspace-store.spec.ts`

**Interfaces:**
- Consumes: `LayoutNode`, `DEFAULT_LAYOUT`, `isValidLayout`, `splitTile`, `closeTile`, `swapWithNeighbor`, `clampRatio`
- Produces: `useWorkspace`, `sanitizeWorkspace(persisted) -> WorkspaceState | null`, `DEFAULT_SLOTS`

- [ ] **Step 1: تستِ ناکام بنویس**

```ts
// frontend-v2/src/__tests__/workspace-store.spec.ts
import { beforeEach, describe, expect, it } from 'vitest';
import { DEFAULT_LAYOUT } from '@shared/workspace/layout';
import { DEFAULT_SLOTS, sanitizeWorkspace, useWorkspace } from '@shared/workspace/store';

beforeEach(() => {
  localStorage.clear();
  useWorkspace.setState(useWorkspace.getInitialState(), true);
});

describe('workspace store', () => {
  it('starts with the approved default layout and four cards', () => {
    const state = useWorkspace.getState();
    expect(state.workspaces[0].layout).toEqual(DEFAULT_LAYOUT);
    expect(state.workspaces[0].slots).toEqual(DEFAULT_SLOTS);
    expect(state.activeSymbol).toBeNull();
  });

  it('splits, closes and swaps through actions', () => {
    const store = useWorkspace.getState();
    store.split('t-symbol', 'col', 'chart');
    expect(useWorkspace.getState().workspaces[0].layout.kind).toBe('split');
    store.swap('t-symbol', 'down');
    const panelsAfterSwap = useWorkspace.getState().workspaces[0].layout;
    expect(JSON.stringify(panelsAfterSwap)).toContain('"panel":"watch"');
    useWorkspace.getState().close('t-watch');
    expect(JSON.stringify(useWorkspace.getState().workspaces[0].layout)).not.toContain('"panel":"watch"');
  });

  it('keeps slots unique and refuses fewer than three', () => {
    useWorkspace.getState().setSlots(['tedpix', 'tedpix', 'breadth']);
    expect(useWorkspace.getState().workspaces[0].slots).toEqual(DEFAULT_SLOTS);
    useWorkspace.getState().setSlots(['tedpix', 'retailValue', 'breadth', 'boardVolume', 'marketTrades', 'tedpix']);
    expect(useWorkspace.getState().workspaces[0].slots).toHaveLength(5);
    expect(new Set(useWorkspace.getState().workspaces[0].slots).size).toBe(5);
  });

  it('rejects an invalid persisted layout', () => {
    expect(sanitizeWorkspace({ version: 1, workspaces: [{ layout: { kind: 'tile' } }] })).toBeNull();
    expect(sanitizeWorkspace(null)).toBeNull();
  });

  it('resets to the default layout', () => {
    useWorkspace.getState().split('t-symbol', 'col', 'chart');
    useWorkspace.getState().resetLayout();
    expect(useWorkspace.getState().workspaces[0].layout).toEqual(DEFAULT_LAYOUT);
  });
});
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/workspace-store.spec.ts`
Expected: FAIL با `Failed to resolve import "@shared/workspace/store"`

- [ ] **Step 3: پیاده‌سازی**

```ts
// frontend-v2/src/shared/workspace/store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import {
  DEFAULT_LAYOUT, clampRatio, closeTile, isValidLayout, splitTile, swapWithNeighbor,
  type LayoutNode, type MoveDir, type SplitDir, type TilePanel,
} from './layout';

export type CardId =
  | 'tedpix' | 'retailValue' | 'breadth' | 'boardValueComposition'
  | 'boardVolume' | 'marketTrades';

export const DEFAULT_SLOTS: CardId[] = ['tedpix', 'retailValue', 'breadth', 'boardValueComposition'];

export interface Workspace {
  id: string;
  name: string;
  layout: LayoutNode;
  slots: CardId[];
  chartOpen: boolean;
  updatedAt: number;
}

interface WorkspaceStore {
  version: 1;
  activeWorkspaceId: string;
  activeSymbol: string | null;
  workspaces: Workspace[];
  split: (tileId: string, dir: SplitDir, panel: TilePanel) => void;
  close: (tileId: string) => void;
  swap: (tileId: string, dir: MoveDir) => void;
  setRatio: (splitId: string, ratio: number, width: number, height: number) => void;
  setSlots: (slots: CardId[]) => void;
  setActiveSymbol: (key: string | null) => void;
  setChartOpen: (open: boolean) => void;
  resetLayout: () => void;
}

const DEFAULT_WORKSPACE: Workspace = {
  id: 'ws-tablo', name: 'تابلوخوانی', layout: DEFAULT_LAYOUT,
  slots: DEFAULT_SLOTS, chartOpen: true, updatedAt: 0,
};

function cleanSlots(slots: unknown): CardId[] {
  const allowed: CardId[] = ['tedpix', 'retailValue', 'breadth', 'boardValueComposition',
    'boardVolume', 'marketTrades'];
  const list = Array.isArray(slots) ? slots : [];
  const out: CardId[] = [];
  for (const slot of list) {
    if (allowed.includes(slot as CardId) && !out.includes(slot as CardId)) out.push(slot as CardId);
  }
  return out.slice(0, 5);
}

export function sanitizeWorkspace(persisted: unknown): Workspace | null {
  if (!persisted || typeof persisted !== 'object') return null;
  const raw = persisted as { workspaces?: unknown; activeWorkspaceId?: unknown; activeSymbol?: unknown };
  const list = Array.isArray(raw.workspaces) ? raw.workspaces : [];
  const first = list[0] as Partial<Workspace> | undefined;
  if (!first || !isValidLayout(first.layout)) return null;
  const slots = cleanSlots(first.slots);
  return {
    id: typeof first.id === 'string' ? first.id : 'ws-tablo',
    name: typeof first.name === 'string' ? first.name : 'تابلوخوانی',
    layout: first.layout,
    slots: slots.length >= 3 ? slots : DEFAULT_SLOTS,
    chartOpen: first.chartOpen !== false,
    updatedAt: Number(first.updatedAt ?? 0),
  };
}

function patchLayout(layout: LayoutNode): Partial<Workspace> {
  return { layout, updatedAt: Date.now() };
}

export const useWorkspace = create<WorkspaceStore>()(
  persist(
    (set, get) => ({
      version: 1,
      activeWorkspaceId: DEFAULT_WORKSPACE.id,
      activeSymbol: null,
      workspaces: [DEFAULT_WORKSPACE],
      split: (tileId, dir, panel) => {
        const ws = get().workspaces[0];
        const next = splitTile(ws.layout, tileId, dir, panel);
        if (!next) return;
        set({ workspaces: [{ ...ws, ...patchLayout(next) }] });
      },
      close: (tileId) => {
        const ws = get().workspaces[0];
        const next = closeTile(ws.layout, tileId);
        if (!next) return;
        set({ workspaces: [{ ...ws, ...patchLayout(next) }] });
      },
      swap: (tileId, dir) => {
        const ws = get().workspaces[0];
        const moved = swapWithNeighbor(ws.layout, tileId, dir);
        if (!moved) return;
        set({ workspaces: [{ ...ws, ...patchLayout(moved.root) }] });
      },
      setRatio: (splitId, ratio, width, height) => {
        const ws = get().workspaces[0];
        function walk(node: LayoutNode): LayoutNode {
          if (node.kind === 'tile') return node;
          if (node.id === splitId) {
            const next = clampRatio(node, ratio, width, height);
            return next === null ? node : { ...node, ratio: next };
          }
          return { ...node, first: walk(node.first), second: walk(node.second) };
        }
        set({ workspaces: [{ ...ws, ...patchLayout(walk(ws.layout)) }] });
      },
      setSlots: (slots) => {
        const ws = get().workspaces[0];
        const clean = cleanSlots(slots);
        if (clean.length < 3) return;
        set({ workspaces: [{ ...ws, slots: clean, updatedAt: Date.now() }] });
      },
      setActiveSymbol: (activeSymbol) => set({ activeSymbol }),
      setChartOpen: (chartOpen) => {
        const ws = get().workspaces[0];
        set({ workspaces: [{ ...ws, chartOpen, updatedAt: Date.now() }] });
      },
      resetLayout: () => {
        const ws = get().workspaces[0];
        set({ workspaces: [{ ...ws, layout: DEFAULT_LAYOUT, updatedAt: Date.now() }] });
      },
    }),
    {
      name: 'bors-workspace-v1',
      version: 1,
      merge: (persisted, current) => {
        const ws = sanitizeWorkspace(persisted);
        if (!ws) return current;
        return { ...current, activeWorkspaceId: ws.id, workspaces: [ws] };
      },
    },
  ),
);

export const getWorkspace = (): Workspace => useWorkspace.getState().workspaces[0];
```

- [ ] **Step 4: تست را سبز کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/workspace-store.spec.ts`
Expected: PASS

- [ ] **Step 5: کامیت**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/shared/workspace/store.ts frontend-v2/src/__tests__/workspace-store.spec.ts
git commit -m "$(cat <<'EOF'
feat(workspace): ذخیره‌گاهِ میزکار و اعتبارسنجیِ نسخه

چیدمان، کارت‌ها و نمادِ فعال در bors-workspace-v1 می‌مانند؛ چیدمانِ نامعتبر
به پیش‌فرض برمی‌گردد.
EOF
)"
```

---

## Task 4: سرِ کاشی، مرزِ اندازه و پوستهٔ رندر

**Files:**
- Create: `frontend-v2/src/shared/workspace/TileFrame.tsx`
- Create: `frontend-v2/src/shared/workspace/Splitter.tsx`
- Create: `frontend-v2/src/shared/workspace/WorkspaceShell.tsx`
- Test: `frontend-v2/src/__tests__/workspace-shell.spec.tsx`

**Interfaces:**
- Consumes: `LayoutNode`, `PANEL_LABEL`, `PANEL_MIN`, `ratioFromPointer`
- Produces:
  - `<WorkspaceShell layout renderPanel onClose onSplit onSwap onToggleFollow onRatio />`
  - `data-tile-id`, `data-tile-header`, `data-tile-focused` روی DOM

- [ ] **Step 1: تستِ ناکام بنویس**

```tsx
// frontend-v2/src/__tests__/workspace-shell.spec.tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DEFAULT_LAYOUT } from '@shared/workspace/layout';
import { WorkspaceShell } from '@shared/workspace/WorkspaceShell';

afterEach(cleanup);

function mount(overrides: Partial<Parameters<typeof WorkspaceShell>[0]> = {}) {
  return render(
    <WorkspaceShell
      layout={DEFAULT_LAYOUT}
      renderPanel={(panel) => <div data-testid={`body-${panel}`}>{panel}</div>}
      onClose={() => {}}
      onSplit={() => {}}
      onSwap={() => {}}
      onToggleFollow={() => {}}
      onRatio={() => {}}
      {...overrides}
    />,
  );
}

describe('WorkspaceShell', () => {
  it('renders every tile with its label', () => {
    mount();
    expect(screen.getByTestId('body-board')).toBeTruthy();
    expect(screen.getByTestId('body-symbol')).toBeTruthy();
    expect(screen.getByTestId('body-watch')).toBeTruthy();
    expect(screen.getByText('تابلو')).toBeTruthy();
    expect(screen.getByText('دیده‌بان‌ها')).toBeTruthy();
  });

  it('does not offer close on the board tile', () => {
    mount();
    expect(screen.queryByTestId('tile-close-t-board')).toBeNull();
    expect(screen.getByTestId('tile-close-t-watch')).toBeTruthy();
  });

  it('calls onClose and onSplit from the tile menu', () => {
    const onClose = vi.fn();
    const onSplit = vi.fn();
    mount({ onClose, onSplit });
    fireEvent.click(screen.getByTestId('tile-close-t-watch'));
    fireEvent.click(screen.getByTestId('tile-menu-t-symbol'));
    fireEvent.click(screen.getByTestId('tile-split-t-symbol-col-chart'));
    expect(onClose).toHaveBeenCalledWith('t-watch');
    expect(onSplit).toHaveBeenCalledWith('t-symbol', 'col', 'chart');
  });

  it('marks the focused tile and exposes the arrow hint', () => {
    mount();
    const header = screen.getByTestId('tile-header-t-symbol');
    fireEvent.focus(header);
    expect(screen.getByTestId('tile-t-symbol').getAttribute('data-tile-focused')).toBe('true');
    expect(screen.getByTestId('tile-hint-t-symbol').textContent).toContain('جابه‌جا');
  });

  it('renders a separator per split', () => {
    mount();
    expect(screen.getAllByRole('separator')).toHaveLength(2);
  });
});
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/workspace-shell.spec.tsx`
Expected: FAIL با `Failed to resolve import "@shared/workspace/WorkspaceShell"`

- [ ] **Step 3: TileFrame را بنویس**

```tsx
// frontend-v2/src/shared/workspace/TileFrame.tsx
import { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';
import { PANEL_LABEL, PANEL_MIN, type MoveDir, type SplitDir, type TilePanel } from './layout';

interface Props {
  id: string;
  panel: TilePanel;
  follow: boolean;
  focused: boolean;
  onFocus: (id: string) => void;
  onClose: (id: string) => void;
  onSplit: (id: string, dir: SplitDir, panel: TilePanel) => void;
  onSwap: (id: string, dir: MoveDir) => void;
  onToggleFollow: (id: string) => void;
  children: React.ReactNode;
}

const SPLIT_TARGETS: TilePanel[] = ['symbol', 'watch', 'chart'];

export function TileFrame(props: Props) {
  const { id, panel, follow, focused, onFocus, onClose, onSplit, onSwap, onToggleFollow, children } = props;
  const [menu, setMenu] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(false);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [menu]);

  return (
    <div
      ref={root}
      data-tile-id={id}
      data-tile-focused={focused ? 'true' : 'false'}
      data-testid={`tile-${id}`}
      style={{ minWidth: PANEL_MIN[panel].w, minHeight: PANEL_MIN[panel].h }}
      className={clsx('relative flex h-full min-h-0 w-full min-w-0 flex-col bg-panel',
        focused && 'outline outline-1 outline-accent')}
    >
      <div
        data-tile-header
        tabIndex={0}
        role="group"
        aria-label={PANEL_LABEL[panel]}
        data-testid={`tile-header-${id}`}
        onFocus={() => onFocus(id)}
        onMouseDown={() => onFocus(id)}
        onKeyDown={(event) => {
          if (event.key === 'ArrowLeft') { event.preventDefault(); onSwap(id, 'left'); }
          if (event.key === 'ArrowRight') { event.preventDefault(); onSwap(id, 'right'); }
          if (event.key === 'ArrowUp') { event.preventDefault(); onSwap(id, 'up'); }
          if (event.key === 'ArrowDown') { event.preventDefault(); onSwap(id, 'down'); }
        }}
        className="flex h-7 flex-none items-center gap-1.5 border-b border-line bg-panel-2 px-2 t-10 text-text-2"
      >
        <span className="font-bold">{PANEL_LABEL[panel]}</span>
        {panel === 'symbol' || panel === 'chart' ? (
          <button
            type="button"
            data-testid={`tile-follow-${id}`}
            onClick={() => onToggleFollow(id)}
            className={clsx('rounded-[var(--radius-xs)] px-1 t-9',
              follow ? 'text-accent' : 'text-text-3')}
          >
            {follow ? 'پیرو: تابلو' : 'مستقل'}
          </button>
        ) : null}
        {focused ? (
          <span data-testid={`tile-hint-${id}`} className="t-9 text-text-3">
            با ←→↑↓ جابه‌جا کن
          </span>
        ) : null}
        <div className="ms-auto flex items-center gap-1">
          <button
            type="button"
            data-testid={`tile-menu-${id}`}
            aria-label="کارهای پنل"
            className="grid h-5 w-5 place-items-center rounded-[var(--radius-xs)] hover:bg-panel-3"
            onClick={(event) => { event.stopPropagation(); setMenu((open) => !open); }}
          >
            ⋯
          </button>
          {panel !== 'board' ? (
            <button
              type="button"
              data-testid={`tile-close-${id}`}
              aria-label="بستنِ پنل"
              className="grid h-5 w-5 place-items-center rounded-[var(--radius-xs)] hover:bg-panel-3"
              onClick={() => onClose(id)}
            >
              ×
            </button>
          ) : null}
        </div>
      </div>

      {menu ? (
        <div className="absolute z-20 mt-7 rounded-[var(--radius-sm)] border border-line bg-panel p-1 t-9 shadow-none"
          onClick={(event) => event.stopPropagation()}>
          {SPLIT_TARGETS.map((target) => (
            <button
              key={`col-${target}`}
              type="button"
              data-testid={`tile-split-${id}-col-${target}`}
              className="block w-full rounded-[var(--radius-xs)] px-2 py-1 text-start hover:bg-panel-2"
              onClick={() => { setMenu(false); onSplit(id, 'col', target); }}
            >
              تقسیمِ عمودی به {PANEL_LABEL[target]}
            </button>
          ))}
          <button type="button" data-testid={`tile-split-${id}-row-chart`}
            className="block w-full rounded-[var(--radius-xs)] px-2 py-1 text-start hover:bg-panel-2"
            onClick={() => { setMenu(false); onSplit(id, 'row', 'chart'); }}>
            تقسیمِ افقی به {PANEL_LABEL.chart}
          </button>
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
    </div>
  );
}
```

- [ ] **Step 4: Splitter و WorkspaceShell را بنویس**

```tsx
// frontend-v2/src/shared/workspace/Splitter.tsx
import { useRef } from 'react';
import clsx from 'clsx';
import { ratioFromPointer, type SplitDir } from './layout';

interface Props {
  dir: SplitDir;
  container: React.RefObject<HTMLElement>;
  onRatio: (ratio: number) => void;
}

export function Splitter({ dir, container, onRatio }: Props) {
  const dragging = useRef(false);

  return (
    <div
      role="separator"
      aria-orientation={dir === 'row' ? 'vertical' : 'horizontal'}
      tabIndex={-1}
      className={clsx('group relative z-10 flex-none bg-line hover:bg-accent',
        dir === 'row' ? 'w-px cursor-col-resize' : 'h-px cursor-row-resize')}
      onPointerDown={(event) => {
        dragging.current = true;
        (event.target as HTMLElement).setPointerCapture?.(event.pointerId);
      }}
      onPointerMove={(event) => {
        if (!dragging.current) return;
        const rect = container.current?.getBoundingClientRect();
        if (!rect || rect.width === 0) return;
        onRatio(ratioFromPointer(rect, dir, event.clientX, event.clientY));
      }}
      onPointerUp={() => { dragging.current = false; }}
      onPointerCancel={() => { dragging.current = false; }}
    >
      <span className={clsx('absolute bg-transparent',
        dir === 'row' ? 'inset-y-0 -start-1 -end-1' : 'inset-x-0 -top-1 -bottom-1')} />
    </div>
  );
}
```

```tsx
// frontend-v2/src/shared/workspace/WorkspaceShell.tsx
import { useRef, useState } from 'react';
import { Splitter } from './Splitter';
import { TileFrame } from './TileFrame';
import type { LayoutNode, MoveDir, SplitDir, TilePanel } from './layout';

export interface WorkspaceShellProps {
  layout: LayoutNode;
  renderPanel: (panel: TilePanel, tileId: string) => React.ReactNode;
  onClose: (id: string) => void;
  onSplit: (id: string, dir: SplitDir, panel: TilePanel) => void;
  onSwap: (id: string, dir: MoveDir) => void;
  onToggleFollow: (id: string) => void;
  onRatio: (splitId: string, ratio: number, width: number, height: number) => void;
}

export function WorkspaceShell(props: WorkspaceShellProps) {
  const { layout, renderPanel, onClose, onSplit, onSwap, onToggleFollow, onRatio } = props;
  const [focused, setFocused] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);

  function node(item: LayoutNode): React.ReactNode {
    if (item.kind === 'tile') {
      return (
        <TileFrame
          key={item.id}
          id={item.id}
          panel={item.panel}
          follow={item.follow}
          focused={focused === item.id}
          onFocus={setFocused}
          onClose={onClose}
          onSplit={onSplit}
          onSwap={onSwap}
          onToggleFollow={onToggleFollow}
        >
          {renderPanel(item.panel, item.id)}
        </TileFrame>
      );
    }

    const size = () => {
      const rect = root.current?.getBoundingClientRect();
      onRatio(item.id, item.ratio, rect?.width ?? 0, rect?.height ?? 0);
    };

    return (
      <div
        key={item.id}
        className={item.dir === 'row' ? 'flex h-full min-h-0 min-w-0' : 'flex h-full min-h-0 min-w-0 flex-col'}
      >
        <div className="min-h-0 min-w-0" style={{ flex: `${item.ratio} 1 0%` }}>{node(item.first)}</div>
        <Splitter dir={item.dir} container={root} onRatio={size} />
        <div className="min-h-0 min-w-0" style={{ flex: `${1 - item.ratio} 1 0%` }}>{node(item.second)}</div>
      </div>
    );
  }

  return <div ref={root} data-testid="workspace-shell" className="h-full min-h-0 w-full min-w-0">{node(layout)}</div>;
}
```

- [ ] **Step 5: تست را سبز کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/workspace-shell.spec.tsx`
Expected: PASS

- [ ] **Step 6: تایپ‌چک و کامیت**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx tsc -b
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/shared/workspace/TileFrame.tsx frontend-v2/src/shared/workspace/Splitter.tsx frontend-v2/src/shared/workspace/WorkspaceShell.tsx frontend-v2/src/__tests__/workspace-shell.spec.tsx
git commit -m "$(cat <<'EOF'
feat(workspace): سرِ کاشی، مرزِ اندازه و پوستهٔ رندر

هر کاشی سرستونِ فوکوس‌پذیر، منوی تقسیم، نشانِ پیرو و مرزِ کشیدنی دارد.
EOF
)"
```

## Task 5: میانبرها، پرشِ `Alt+۱…۴` و برگشتِ یک‌مرحله‌ای

**Files:**
- Create: `frontend-v2/src/shared/workspace/shortcuts.ts`
- Create: `frontend-v2/src/shared/workspace/useTileKeyboard.ts`
- Modify: `frontend-v2/src/shared/workspace/store.ts` (افزودنِ `history` و `undo`)
- Test: `frontend-v2/src/__tests__/workspace-keyboard.spec.tsx`

**Interfaces:**
- Produces:
  - `SHORTCUTS: ReadonlyArray<{id,keys,label}>`
  - `useTileKeyboard(layout, {enabled?})`
  - `useWorkspace.getState().undo()`

- [ ] **Step 1: تستِ ناکام بنویس**

```tsx
// frontend-v2/src/__tests__/workspace-keyboard.spec.tsx
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { DEFAULT_LAYOUT } from '@shared/workspace/layout';
import { SHORTCUTS } from '@shared/workspace/shortcuts';
import { useWorkspace } from '@shared/workspace/store';
import { useTileKeyboard } from '@shared/workspace/useTileKeyboard';

afterEach(cleanup);

beforeEach(() => {
  localStorage.clear();
  useWorkspace.setState(useWorkspace.getInitialState(), true);
});

function Harness() {
  useTileKeyboard(DEFAULT_LAYOUT);
  return (
    <div>
      <div data-tile-id="t-board"><div data-tile-header tabIndex={0} data-testid="h-board" /></div>
      <div data-tile-id="t-symbol"><div data-tile-header tabIndex={0} data-testid="h-symbol" /></div>
    </div>
  );
}

describe('tile keyboard', () => {
  it('lists the approved shortcuts in one registry', () => {
    expect(SHORTCUTS.map((s) => s.keys)).toEqual(['Alt+۱…۴', '←→↑↓', 'Ctrl+K', 'Ctrl+Z', 'Esc']);
  });

  it('focuses panels by their reading order with Alt+Digit', () => {
    render(<Harness />);
    fireEvent.keyDown(window, { key: '1', code: 'Digit1', altKey: true });
    expect(document.activeElement?.getAttribute('data-testid')).toBe('h-board');
    fireEvent.keyDown(window, { key: '2', code: 'Digit2', altKey: true });
    expect(document.activeElement?.getAttribute('data-testid')).toBe('h-symbol');
  });

  it('undoes the last layout change with Ctrl+Z', () => {
    render(<Harness />);
    useWorkspace.getState().split('t-symbol', 'col', 'chart');
    expect(JSON.stringify(useWorkspace.getState().workspaces[0].layout)).toContain('"chart"');
    fireEvent.keyDown(window, { key: 'z', code: 'KeyZ', ctrlKey: true });
    expect(useWorkspace.getState().workspaces[0].layout).toEqual(DEFAULT_LAYOUT);
  });
});
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/workspace-keyboard.spec.tsx`
Expected: FAIL با `Failed to resolve import "@shared/workspace/shortcuts"`

- [ ] **Step 3: رجیستری و هوک را بنویس**

```ts
// frontend-v2/src/shared/workspace/shortcuts.ts
export interface Shortcut {
  id: 'panels' | 'swap' | 'command' | 'undo' | 'escape';
  keys: string;
  label: string;
}

/** تنها منبعِ میانبرها: منوی کاشی، راهنمای سایدبار و تست‌ها از همین می‌خوانند. */
export const SHORTCUTS: ReadonlyArray<Shortcut> = [
  { id: 'panels', keys: 'Alt+۱…۴', label: 'رفتن به پنل' },
  { id: 'swap', keys: '←→↑↓', label: 'جابه‌جاییِ پنلِ انتخاب‌شده' },
  { id: 'command', keys: 'Ctrl+K', label: 'همهٔ کارها' },
  { id: 'undo', keys: 'Ctrl+Z', label: 'برگشتِ چیدمان' },
  { id: 'escape', keys: 'Esc', label: 'بستنِ منو' },
];
```

```ts
// frontend-v2/src/shared/workspace/useTileKeyboard.ts
import { useEffect } from 'react';
import { panelsInOrder, type LayoutNode } from './layout';
import { useWorkspace } from './store';

export function useTileKeyboard(layout: LayoutNode, options: { enabled?: boolean } = {}): void {
  const undo = useWorkspace((state) => state.undo);
  const enabled = options.enabled !== false;

  useEffect(() => {
    if (!enabled) return;
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === 'z') {
        event.preventDefault();
        undo();
        return;
      }
      if (!event.altKey || event.ctrlKey || event.metaKey) return;
      const digit = /^Digit([1-4])$/.exec(event.code);
      if (!digit) return;
      const tile = panelsInOrder(layout)[Number(digit[1]) - 1];
      if (!tile) return;
      event.preventDefault();
      document
        .querySelector<HTMLElement>(`[data-tile-id="${tile.id}"] [data-tile-header]`)
        ?.focus();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [enabled, layout, undo]);
}
```

- [ ] **Step 4: `undo` را به ذخیره‌گاه اضافه کن**

در `store.ts` به `WorkspaceStore` اضافه کن:

```ts
  history: LayoutNode[];
  undo: () => void;
```

و در بدنهٔ `create`:

```ts
      history: [],
      undo: () => {
        const past = get().history;
        if (past.length === 0) return;
        const ws = get().workspaces[0];
        const previous = past[past.length - 1];
        set({
          history: past.slice(0, -1),
          workspaces: [{ ...ws, layout: previous, updatedAt: Date.now() }],
        });
      },
```

هر پنج اکشنِ چیدمان (`split`, `close`, `swap`, `setRatio`, `resetLayout`) باید تاریخ را پر کنند. بدنهٔ `create` را به این شکل درآور (کمکی داخلِ همان closure، بدونِ تایپ‌بازیِ `set/get`):

```ts
export const useWorkspace = create<WorkspaceStore>()(
  persist(
    (set, get) => {
      const commit = (layout: LayoutNode, extra: Partial<Workspace> = {}) => {
        const ws = get().workspaces[0];
        set({
          history: [...get().history.slice(-9), ws.layout],
          workspaces: [{ ...ws, layout, ...extra, updatedAt: Date.now() }],
        });
      };

      return {
        version: 1,
        activeWorkspaceId: DEFAULT_WORKSPACE.id,
        activeSymbol: null,
        workspaces: [DEFAULT_WORKSPACE],
        history: [],
        split: (tileId, dir, panel) => {
          const next = splitTile(get().workspaces[0].layout, tileId, dir, panel);
          if (next) commit(next);
        },
        close: (tileId) => {
          const next = closeTile(get().workspaces[0].layout, tileId);
          if (next) commit(next);
        },
        swap: (tileId, dir) => {
          const moved = swapWithNeighbor(get().workspaces[0].layout, tileId, dir);
          if (moved) commit(moved.root);
        },
        setRatio: (splitId, ratio, width, height) => {
          const walk = (node: LayoutNode): LayoutNode => {
            if (node.kind === 'tile') return node;
            if (node.id === splitId) {
              const next = clampRatio(node, ratio, width, height);
              return next === null ? node : { ...node, ratio: next };
            }
            return { ...node, first: walk(node.first), second: walk(node.second) };
          };
          commit(walk(get().workspaces[0].layout));
        },
        resetLayout: () => commit(DEFAULT_LAYOUT),
        undo: () => {
          const past = get().history;
          if (past.length === 0) return;
          commit(past[past.length - 1]);
          set({ history: past.slice(0, -1) });
        },
      };
    },
    { /* persist options */ },
  ),
);
```

و `persist` باید تاریخ را ذخیره نکند:

```ts
      partialize: (state) => ({
        version: state.version,
        activeWorkspaceId: state.activeWorkspaceId,
        activeSymbol: state.activeSymbol,
        workspaces: state.workspaces,
      }),
```

- [ ] **Step 5: تست را سبز کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/workspace-keyboard.spec.tsx src/__tests__/workspace-store.spec.ts`
Expected: PASS

- [ ] **Step 6: کامیت**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/shared/workspace/shortcuts.ts frontend-v2/src/shared/workspace/useTileKeyboard.ts frontend-v2/src/shared/workspace/store.ts frontend-v2/src/__tests__/workspace-keyboard.spec.tsx
git commit -m "$(cat <<'EOF'
feat(workspace): میانبرهای ساده و برگشتِ یک‌مرحله‌ای

Alt+۱…۴ برای پرش، Ctrl+Z برای برگشت؛ فهرستِ میانبرها یک منبع دارد.
EOF
)"
```

---

## Task 6: استخراجِ پنلِ تابلو و حذفِ P/E از پیش‌فرض

**Files:**
- Create: `frontend-v2/src/features/market/panels/BoardPanel.tsx`
- Modify: `frontend-v2/src/features/market/routes/MarketPage.tsx`
- Modify: `frontend-v2/src/features/market/lib/columns.ts:126-145`
- Test: `frontend-v2/src/__tests__/board-panel.spec.tsx`
- Test: `frontend-v2/src/__tests__/default-columns.spec.ts`

**Interfaces:**
- Consumes: `useBoard`, prefs, `evaluateBoard`, `sortRows`, `boardExportTable`
- Produces:
  - `<BoardPanel selectedKey onSelect onActivate />` با
    `onSelect: (row: MarketRow, boardDay: number | null) => void`
    `onActivate: (row: MarketRow, boardDay: number | null) => void`
  - `defaultColumns('general')` بدونِ `pe`

- [ ] **Step 1: تستِ ناکام بنویس**

```ts
// frontend-v2/src/__tests__/default-columns.spec.ts
import { describe, expect, it } from 'vitest';
import { COLUMNS, defaultColumns } from '@features/market/lib/columns';

describe('default columns', () => {
  it('keeps P/E out of the general and fundamental defaults', () => {
    expect(defaultColumns('general')).not.toContain('pe');
    expect(defaultColumns('fundamental')).not.toContain('pe');
  });

  it('still offers P/E from the column menu', () => {
    expect(COLUMNS.pe.available).toBe(true);
  });
});
```

```tsx
// frontend-v2/src/__tests__/board-panel.spec.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketFeed, MarketRow } from '@shared/types/market';
import { BoardPanel } from '@features/market/panels/BoardPanel';
import { useBoard } from '@features/market/api/useBoard';

vi.mock('@features/market/api/useBoard', () => ({ useBoard: vi.fn() }));
vi.mock('@tanstack/react-virtual', async (original) => {
  const mod = await original<typeof import('@tanstack/react-virtual')>();
  return {
    ...mod,
    useVirtualizer: ({ count }: { count: number }) => ({
      getVirtualItems: () => Array.from({ length: count }, (_, index) => ({
        index, key: index, start: index * 30, size: 30,
      })),
      getTotalSize: () => count * 30,
      measureElement: () => {},
    }),
  };
});
vi.mock('@shared/lib/marketHours', () => ({
  effectivePollMs: (ms: number) => ms, sessionPollMs: (ms: number) => ms,
  isMarketOpen: () => true, CLOSED_POLL_MS: 300_000,
}));

const rows: MarketRow[] = [
  { symbol: 'الف', ins_code: '10', name: 'الف', price_yesterday: 100, p_closing: 110,
    percent_change: 10, q_tot_cap: 5_000_000_000, q_tot_tran: 2_000_000 } as MarketRow,
];

const feed: MarketFeed = {
  status: 'ok', rev: 1, count: 1, live_count: 1, fossil_count: 0,
  meta: { d_even: 20261028, last_sync: '2026-10-28 12:00:00' }, data: rows,
} as MarketFeed;

function mount(props: Partial<Parameters<typeof BoardPanel>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <BoardPanel selectedKey={null} onSelect={() => {}} onActivate={() => {}} {...props} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(useBoard).mockReturnValue({
    data: feed, isLoading: false, isError: false, isFetching: false,
    dataUpdatedAt: Date.now(), refetch: vi.fn(), error: null, status: 'success',
  } as never);
});

afterEach(cleanup);

describe('BoardPanel', () => {
  it('renders the row count footer', () => {
    mount();
    expect(screen.getByTestId('board-count').textContent).toContain('۱');
  });

  it('reports the row identity and board day on select', () => {
    const onSelect = vi.fn();
    mount({ onSelect });
    fireEvent.click(screen.getByText('الف'));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ ins_code: '10' }), 20261028);
  });
});
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/default-columns.spec.ts src/__tests__/board-panel.spec.tsx`
Expected: FAIL (P/E هنوز در پیش‌فرض است؛ `BoardPanel` وجود ندارد)

- [ ] **Step 3: P/E را از پیش‌فرض بردار**

در `columns.ts`، فقط دو سطر را عوض کن:

```ts
  general: {
    label: 'عمومی',
    columns: ['symbol', 'last', 'pct_close', 'close', 'volume', 'value', 'trades', 'patterns', 'eps', 'mcap', 'tech'],
  },
  fundamental: {
    label: 'بنیادی',
    columns: ['symbol', 'last', 'pct_close', 'eps', 'mcap'],
  },
```

- [ ] **Step 4: `BoardPanel` را بساز**

کلِ منطقِ تابلو از `MarketPage` به این فایل منتقل می‌شود. محتوای کامل:

```tsx
// frontend-v2/src/features/market/panels/BoardPanel.tsx
import { useCallback, useMemo, useRef, useState } from 'react';
import clsx from 'clsx';
import { fmtInt } from '@shared/lib/fa';
import { computeFeedStatus } from '@shared/lib/feedFreshness';
import { csvBlobParts, csvFilename, csvTextWithMeta, saveBlob } from '@shared/lib/tableExport';
import type { MarketRow } from '@shared/types/market';
import { useBoard } from '../api/useBoard';
import { BoardTable } from '../components/BoardTable';
import { BoardToolbar } from '../components/BoardToolbar';
import { TapeBar } from '../components/TapeBar';
import { boardExportTable } from '../lib/boardExport';
import { evaluateBoard } from '../lib/boardFilters';
import {
  defaultColumns, PROFILES, SORT_LABEL, sortRows,
  type ProfileKey, type SortDir, type SortKey,
} from '../lib/columns';
import { DEFAULT_TAPE_FILTER_CONFIG } from '../lib/tapeAlgorithms';
import { tapeLabel } from '../lib/tapeFilters';
import { useMarketPrefs } from '../stores/prefs';

export interface BoardPanelProps {
  selectedKey: string | null;
  onSelect: (row: MarketRow, boardDay: number | null) => void;
  onActivate: (row: MarketRow, boardDay: number | null) => void;
}

export function BoardPanel({ selectedKey, onSelect, onActivate }: BoardPanelProps) {
  const pollMs = useMarketPrefs((s) => s.pollMs);
  const board = useBoard(pollMs);
  const rows = useMemo(() => board.data?.data ?? [], [board.data]);
  const boardDay = board.data?.meta?.d_even ?? null;

  const profile = useMarketPrefs((s) => s.profile);
  const density = useMarketPrefs((s) => s.density);
  const quickFilters = useMarketPrefs((s) => s.quickFilters);
  const quickLogic = useMarketPrefs((s) => s.quickLogic);
  const assetTypes = useMarketPrefs((s) => s.assetTypes);
  const filters = useMarketPrefs((s) => s.filters);
  const columns = useMarketPrefs((s) => s.visibleColumns);
  const setProfile = useMarketPrefs((s) => s.setProfile);
  const setDensity = useMarketPrefs((s) => s.setDensity);
  const toggleColumn = useMarketPrefs((s) => s.toggleColumn);
  const toggleQuickFilter = useMarketPrefs((s) => s.toggleQuickFilter);
  const clearQuickFilters = useMarketPrefs((s) => s.clearQuickFilters);
  const setQuickLogic = useMarketPrefs((s) => s.setQuickLogic);
  const setAssetTypes = useMarketPrefs((s) => s.setAssetTypes);
  const setFilters = useMarketPrefs((s) => s.setFilters);
  const setPollMs = useMarketPrefs((s) => s.setPollMs);
  const savedViews = useMarketPrefs((s) => s.savedViews);
  const saveNamedView = useMarketPrefs((s) => s.saveView);
  const restoreNamedView = useMarketPrefs((s) => s.restoreView);
  const deleteNamedView = useMarketPrefs((s) => s.deleteView);

  const [query, setQuery] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('value');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const searchRef = useRef<HTMLInputElement>(null);

  const sectors = useMemo(() => [...new Set(
    rows.map((row) => row.sector_name).filter((sector): sector is string => typeof sector === 'string' && sector.length > 0),
  )].sort((a, b) => a.localeCompare(b, 'fa')), [rows]);

  const evaluation = useMemo(() => evaluateBoard(rows, {
    query, assetTypes, quickFilters, quickLogic, ...filters,
    filterConfig: DEFAULT_TAPE_FILTER_CONFIG,
  }), [rows, query, assetTypes, quickFilters, quickLogic, filters]);

  const visible = useMemo(
    () => sortRows(evaluation.visible, sortKey, sortDir),
    [evaluation.visible, sortKey, sortDir],
  );

  const feedStatus = useMemo(() => computeFeedStatus({
    status: board.status,
    dataUpdatedAt: board.dataUpdatedAt,
    dataChangedAt: board.data?.rev_at,
    liveCount: board.data?.live_count,
    totalCount: board.data?.count,
    now: Date.now(),
  }), [board.status, board.dataUpdatedAt, board.data]);

  const focusSearch = useCallback(() => {
    window.setTimeout(() => searchRef.current?.focus(), 0);
  }, []);

  function pickProfile(next: ProfileKey) {
    setProfile(next);
    const cols = defaultColumns(next);
    if (!(cols as string[]).includes(sortKey)) {
      setSortKey(cols.includes('value') ? 'value' : 'last');
      setSortDir('desc');
    }
  }

  function pickSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((dir) => (dir === 'desc' ? 'asc' : 'desc'));
      return;
    }
    setSortKey(key);
    setSortDir(key === 'symbol' ? 'asc' : 'desc');
  }

  function saveView(name: string) {
    saveNamedView(name, {
      query, sortKey, sortDir, profile, density, quickFilters, quickLogic,
      assetTypes, visibleColumns: columns, filters, pollMs,
    });
  }

  function applyView(name: string) {
    const state = restoreNamedView(name);
    if (!state) return;
    setQuery(state.query);
    setSortKey(state.sortKey);
    setSortDir(state.sortDir);
  }

  function exportBoard() {
    if (!board.data) return;
    const table = boardExportTable(visible, columns, DEFAULT_TAPE_FILTER_CONFIG);
    const meta: [string, string][] = [
      ['منبع', '/api/market'],
      ['روز تابلو', String(board.data.meta?.d_even ?? '—')],
      ['آخرین همگام‌سازی', board.data.meta?.last_sync ?? '—'],
      ['بازبینی', String(board.data.rev ?? '—')],
      ['پروفایل', PROFILES[profile].label],
      ['مرتب‌سازی', `${SORT_LABEL[sortKey]} · ${sortDir === 'desc' ? 'نزولی' : 'صعودی'}`],
      ['جستجو', query.trim() || '—'],
      ['فیلترهای تابلوخوانی', quickFilters.length
        ? `${quickFilters.map(tapeLabel).join('، ')} · ${quickLogic === 'and' ? 'همه' : 'حداقل یکی'}`
        : '—'],
      ['ردیف‌ها', fmtInt(visible.length)],
    ];
    saveBlob(
      new Blob(csvBlobParts(csvTextWithMeta(table, meta)), { type: 'text/csv;charset=utf-8' }),
      csvFilename('تابلوخوانی'),
    );
  }

  if (board.isError && !board.data) {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 bg-bg">
        <span className="t-115 text-text-2">خوراکِ تابلو نمی‌رسد — ‎/api/market</span>
        <span className="max-w-[520px] text-center t-10 text-text-3">
          {String((board.error as Error)?.message ?? 'خطای نامشخص')}
        </span>
        <button type="button" onClick={() => void board.refetch()}
          className="mt-1 h-7 rounded-[var(--radius-sm)] border border-line bg-panel-2 px-3 t-10 text-text hover:border-line-strong">
          تلاشِ دوباره
        </button>
      </div>
    );
  }

  if (board.isLoading || !board.data) {
    return (
      <div className="flex min-h-0 flex-1 flex-col" aria-busy="true" aria-label="در حالِ بارگذاری تابلو">
        <div className="h-[37px] shrink-0 border-b border-line bg-panel" />
        <div className="h-[33px] shrink-0 border-b border-line bg-panel" />
        <div className="flex-1 space-y-1 overflow-hidden bg-bg p-2">
          {Array.from({ length: 16 }, (_, i) => (
            <div key={i} className="h-[30px] animate-pulse rounded-[var(--radius-xs)] bg-panel-2" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div data-density={density} className="flex min-h-0 flex-1 flex-col">
      <BoardToolbar
        query={query}
        onQuery={setQuery}
        profile={profile}
        onProfile={pickProfile}
        density={density}
        onDensity={setDensity}
        columns={columns}
        onToggleColumn={toggleColumn}
        assetTypes={assetTypes}
        onAssetTypes={setAssetTypes}
        filters={filters}
        onFilters={setFilters}
        sectors={sectors}
        pollMs={pollMs}
        onPollMs={setPollMs}
        savedViews={savedViews}
        onSaveView={saveView}
        onApplyView={applyView}
        onDeleteView={deleteNamedView}
        onExport={exportBoard}
        onFocusSearch={focusSearch}
        searchRef={searchRef}
      />
      <TapeBar
        counts={evaluation.counts}
        unevaluated={evaluation.unevaluated}
        hiddenCounts={evaluation.hiddenCounts}
        baseCount={evaluation.baseCount}
        active={quickFilters}
        logic={quickLogic}
        onToggle={toggleQuickFilter}
        onClear={clearQuickFilters}
        onLogic={setQuickLogic}
      />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-panel">
        {visible.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-1 text-text-3">
            <b className="t-115 font-bold text-text-2">ردیفی با این فیلتر نیست</b>
            <span className="t-10">فیلترها، نوع دارایی یا جستجو را تغییر بده.</span>
          </div>
        ) : (
          <BoardTable
            rows={visible}
            columns={columns}
            sortKey={sortKey}
            sortDir={sortDir}
            density={density}
            filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
            selectedKey={selectedKey}
            resetKey={`${profile}|${query}|${quickFilters.join(',')}|${quickLogic}|${assetTypes.join(',')}|${JSON.stringify(filters)}|${sortKey}|${sortDir}`}
            onSort={pickSort}
            onSelect={(row) => onSelect(row, boardDay)}
            onActivate={(row) => onActivate(row, boardDay)}
          />
        )}
      </div>
      <div data-testid="market-footer"
        className="flex h-[26px] shrink-0 items-center gap-3 border-t border-line bg-panel px-3 t-9 text-text-3">
        <span data-testid="feed-state" role="status" title={feedStatus.label}
          className="flex min-w-0 items-center gap-1.5 text-text-2">
          <i className={clsx('h-1.5 w-1.5 flex-none rounded-full', feedStatus.tone)} aria-hidden />
          <span className="max-w-[380px] truncate">{feedStatus.label}</span>
        </span>
        <span dir="ltr">/api/market</span>
        <span>·</span>
        <span>ارزش = میلیارد ریال</span>
        <span className="ms-auto num" data-testid="board-count" aria-live="polite">
          {fmtInt(visible.length)} از {fmtInt(rows.length)}
        </span>
      </div>
    </div>
  );
}
```

اگر `BoardToolbar` پارامترِ `searchRef` ندارد، آن را به همین شکل اضافه کن (prop اختیاری، زیرِ `onFocusSearch`) و ورودیِ جستجو را با همان ref بده؛ در نبودِ `onFocusSearch` رفتارِ فعلی حفظ می‌شود.

اگر `BoardTable` فعلاً `onActivate` ندارد، آن را به‌عنوان prop اختیاری اضافه کن و داخلِ ردیف روی `Enter` صدا بزن:

```tsx
onKeyDown={(event) => {
  if (event.key === 'Enter') { event.preventDefault(); onActivate?.(row); }
}}
```

- [ ] **Step 5: `MarketPage` را موقتاً به پنل وصل کن**

بدنهٔ `MarketPage` تا Task 13 چنین می‌شود (StatusStrip و Drawer موقتاً می‌مانند):

```tsx
import { useState } from 'react';
import type { MarketRow } from '@shared/types/market';
import { useUiStore } from '@shared/stores/uiStore';
import { useBoard } from '../api/useBoard';
import { StatusStrip } from '../components/StatusStrip';
import { QuickDrawer } from '../components/QuickDrawer';
import { DEFAULT_TAPE_FILTER_CONFIG } from '../lib/tapeAlgorithms';
import { useMarketPrefs } from '../stores/prefs';
import { BoardPanel } from '../panels/BoardPanel';

export function MarketPage() {
  const pollMs = useMarketPrefs((s) => s.pollMs);
  const board = useBoard(pollMs);
  const rows = board.data?.data ?? [];
  const statusMode = useUiStore((s) => s.statusMode);
  const setStatusMode = useUiStore((s) => s.setStatusMode);
  const [selectedRow, setSelectedRow] = useState<MarketRow | null>(null);
  const [boardDay, setBoardDay] = useState<number | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const selectedKey = selectedRow ? (selectedRow.ins_code?.trim() || selectedRow.symbol) : null;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {board.data ? <StatusStrip feed={board.data} rows={rows} mode={statusMode} onMode={setStatusMode} /> : null}
      <div className="flex min-h-0 flex-1">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <BoardPanel
            selectedKey={drawerOpen ? selectedKey : null}
            onSelect={(row, day) => { setSelectedRow(row); setBoardDay(day); setDrawerOpen(true); }}
            onActivate={(row, day) => { setSelectedRow(row); setBoardDay(day); setDrawerOpen(true); }}
          />
        </div>
        {drawerOpen && selectedRow ? (
          <div className="min-h-0 w-[380px] flex-none border-s border-line">
            <QuickDrawer row={selectedRow} filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
              boardDay={boardDay ?? undefined} onClose={() => setDrawerOpen(false)} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: كلِ مجموعه را سبز كن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run && npx tsc -b`
Expected: همهٔ تست‌هایِ موجود + دو تستِ تازه PASS؛ `tsc` صفر خطا. اگر تستی به ساختارِ قدیمیِ `MarketPage` وابسته بود، همان تست را با ساختارِ تازه هم‌راست کن، ولی هیچ assertی را حذف نکن.

- [ ] **Step 7: کامیت**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/features/market/panels/BoardPanel.tsx frontend-v2/src/features/market/routes/MarketPage.tsx frontend-v2/src/features/market/lib/columns.ts frontend-v2/src/features/market/components/BoardToolbar.tsx frontend-v2/src/features/market/components/BoardTable.tsx frontend-v2/src/__tests__/board-panel.spec.tsx frontend-v2/src/__tests__/default-columns.spec.ts
git commit -m "$(cat <<'EOF'
refactor(market): پنلِ تابلو جدا شد و P/E از پیش‌فرض رفت

تابلو حالا یک پنلِ مستقل با onSelect/onActivate است و ستون P/E فقط از
منوی ستون‌ها اضافه می‌شود.
EOF
)"
```

---

## Task 7: قراردادِ snapshot در فرانت

**Files:**
- Create: `frontend-v2/src/features/market/api/useMarketSnapshot.ts`
- Test: `frontend-v2/src/__tests__/market-snapshot.spec.ts`

**Interfaces:**
- Produces:
  - `MarketSnapshot` (نوعِ استنتاج‌شده از zod)
  - `parseSnapshot(payload: unknown): MarketSnapshot`
  - `useMarketSnapshot(pollMs?: number)`

- [ ] **Step 1: تستِ ناکام بنویس**

```ts
// frontend-v2/src/__tests__/market-snapshot.spec.ts
import { describe, expect, it } from 'vitest';
import { parseSnapshot } from '@features/market/api/useMarketSnapshot';

const good = {
  status: 'ok',
  asof: { d_even: 20261028 },
  index: { d_even: 20261028, last: 8_069_789, change: 12_000, pct: 1.5,
    ew_last: 2_229_587, ew_change: 500, ew_pct: 0.2 },
  prev: { d_even: 20261027, last: 8_000_000, change: 0, pct: 0,
    ew_last: 2_220_000, ew_change: 0, ew_pct: 0,
    z_tot_tran: 700_000, q_tot_cap: 4e14, q_tot_tran: 9e9 },
  market: { trade_value_hemat: 40.0, volume: 1e10, trades: 800_000, market_value_hemat: 8123.4 },
  retail: { value_hemat: 45.6, state: 'good', label: 'مساعد', good_min: 20,
    bad_max: 10, excellent_min: 50, basis: 'x', cause: null },
};

describe('market snapshot schema', () => {
  it('parses a good payload', () => {
    const snap = parseSnapshot(good);
    expect(snap.index?.last).toBe(8_069_789);
    expect(snap.market?.trades).toBe(800_000);
    expect(snap.retail?.bad_max).toBe(10);
  });

  it('accepts a null previous session', () => {
    expect(parseSnapshot({ ...good, prev: null }).prev).toBeNull();
  });

  it('rejects an error envelope', () => {
    expect(() => parseSnapshot({ status: 'error', message: 'x' })).toThrow();
  });

  it('rejects NaN-ish strings instead of coercing', () => {
    expect(() => parseSnapshot({ ...good, index: { ...good.index, last: '8.0' } })).toThrow();
  });
});
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/market-snapshot.spec.ts`
Expected: FAIL با `Failed to resolve import`

- [ ] **Step 3: پیاده‌سازی**

```ts
// frontend-v2/src/features/market/api/useMarketSnapshot.ts
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { effectivePollMs } from '@shared/lib/marketHours';
import { getJson } from '@shared/api/http';

const num = z.number().nullish();

const IndexSchema = z.looseObject({
  d_even: z.number(),
  last: num, change: num, pct: num,
  ew_last: num, ew_change: num, ew_pct: num,
});

const PrevSchema = IndexSchema.extend({
  z_tot_tran: num, q_tot_cap: num, q_tot_tran: num,
});

export const MarketSnapshotSchema = z.looseObject({
  status: z.literal('ok'),
  asof: z.looseObject({ d_even: num }).optional(),
  index: IndexSchema.nullish(),
  prev: PrevSchema.nullish(),
  market: z.looseObject({
    trade_value_hemat: num, volume: num, trades: num, market_value_hemat: num,
  }).nullish(),
  retail: z.looseObject({
    value_hemat: num, state: z.string().nullish(), label: z.string().nullish(),
    basis: z.string().nullish(), cause: z.string().nullish(),
    good_min: num, bad_max: num, excellent_min: num,
  }).nullish(),
});

export type MarketSnapshot = z.infer<typeof MarketSnapshotSchema>;

export function parseSnapshot(payload: unknown): MarketSnapshot {
  return MarketSnapshotSchema.parse(payload);
}

export function useMarketSnapshot(pollMs = 5_000) {
  return useQuery<MarketSnapshot>({
    queryKey: ['market-snapshot'],
    queryFn: ({ signal }) => getJson('/api/mstat/market-snapshot', MarketSnapshotSchema, signal),
    refetchInterval: () => effectivePollMs(pollMs),
    staleTime: Math.min(Math.max(pollMs - 1_000, 1_000), 4_000),
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}
```

- [ ] **Step 4: تست را سبز کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/market-snapshot.spec.ts`
Expected: PASS (۴ تست)

- [ ] **Step 5: کامیت**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/features/market/api/useMarketSnapshot.ts frontend-v2/src/__tests__/market-snapshot.spec.ts
git commit -m "$(cat <<'EOF'
feat(market): قراردادِ snapshot برای کارت‌های بالای تابلو

پاکتِ خطا رد می‌شود و عددِ رشته‌ای به‌جای عدد پذیرفته نمی‌شود.
EOF
)"
```

---

## Task 8: رجیستریِ کارت‌ها و متریک‌های مشترک

**Files:**
- Create: `frontend-v2/src/features/market/lib/boardMetrics.ts`
- Modify: `frontend-v2/src/features/market/components/StatusStrip.tsx` (استفاده از متریک‌های مشترک)
- Create: `frontend-v2/src/features/market/components/cards/registry.ts`
- Test: `frontend-v2/src/__tests__/card-registry.spec.ts`

**Interfaces:**
- Consumes: `MarketRow`, `MarketFeed`, `MarketSnapshot`, `CardId`
- Produces:
  - `boardSums(rows) -> {value, volume}`
  - `breadthOf(rows) -> Breadth`
  - `compositionOf(rows) -> Array<{type,count}>`
  - `CARD_REGISTRY: Record<CardId, CardDescriptor>`
  - `CARD_ORDER: CardId[]`

- [ ] **Step 1: تستِ ناکام بنویس**

```ts
// frontend-v2/src/__tests__/card-registry.spec.ts
import { describe, expect, it } from 'vitest';
import type { MarketRow } from '@shared/types/market';
import { CARD_ORDER, CARD_REGISTRY } from '@features/market/components/cards/registry';
import type { MarketSnapshot } from '@features/market/api/useMarketSnapshot';

const rows = [
  { symbol: 'الف', ins_code: '10', price_yesterday: 100, p_closing: 110, percent_change: 10,
    q_tot_cap: 6_000_000_000, q_tot_tran: 2_000_000, pe: 7, mcap: 1e12 },
  { symbol: 'ب', ins_code: '20', price_yesterday: 200, p_closing: 180, percent_change: -10,
    q_tot_cap: 4_000_000_000, q_tot_tran: 1_000_000, pe: null, mcap: 2e12 },
] as MarketRow[];

const snapshot = {
  status: 'ok',
  index: { d_even: 20261028, last: 8_000_000, change: 80_000, pct: 1.0,
    ew_last: 2_200_000, ew_change: 4_400, ew_pct: 0.2 },
  prev: { d_even: 20261027, last: 7_920_000, change: 0, pct: 0,
    ew_last: 2_100_000, ew_change: 0, ew_pct: 0,
    z_tot_tran: 600_000, q_tot_cap: 4e14, q_tot_tran: 8e9 },
  market: { trade_value_hemat: 40, volume: 1e10, trades: 800_000, market_value_hemat: 8000 },
  retail: { value_hemat: 45, state: 'good', label: 'مساعد', good_min: 20, bad_max: 10,
    excellent_min: 50, basis: 'b', cause: null },
} as MarketSnapshot;

const ctx = { rows, snapshot };

describe('card registry', () => {
  it('has every card in the order', () => {
    expect(CARD_ORDER.sort()).toEqual(Object.keys(CARD_REGISTRY).sort());
  });

  it('reads the index and withholds delta without a previous session', () => {
    expect(CARD_REGISTRY.tedpix.value(ctx)).toContain('۸');
    const noPrev = { ...ctx, snapshot: { ...snapshot, prev: null } };
    expect(CARD_REGISTRY.tedpix.delta(noPrev)).toBeNull();
    expect(CARD_REGISTRY.tedpix.preview(noPrev)[0].note).toContain('نشست');
  });

  it('marks board cards with the board basis and never mixes retail', () => {
    const value = CARD_REGISTRY.boardValueComposition;
    expect(value.basis).toBe('board');
    expect(value.value(ctx)).not.toBeNull();
    expect(value.preview(ctx).some((row) => row.label === 'سهام')).toBe(true);
  });

  it('shows a dash when the snapshot is missing', () => {
    expect(CARD_REGISTRY.retailValue.value({ rows })).toBeNull();
    expect(CARD_REGISTRY.marketTrades.value({ rows })).toBeNull();
  });

  it('counts breadth from rows', () => {
    expect(CARD_REGISTRY.breadth.value(ctx)).toContain('۱');
  });
});
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/card-registry.spec.ts`
Expected: FAIL با `Failed to resolve import`

- [ ] **Step 3: متریک‌های تخته را جدا کن**

```ts
// frontend-v2/src/features/market/lib/boardMetrics.ts
import { changePct } from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';
import { classifyAssetType, type AssetType } from './assetType';

export interface Breadth {
  up: number; down: number; flat: number; unknown: number; total: number;
  upPct: number; downPct: number; flatPct: number;
}

export function breadthOf(rows: readonly MarketRow[]): Breadth {
  let up = 0; let down = 0; let flat = 0; let unknown = 0;
  for (const row of rows) {
    const pct = changePct(row.percent_change, row.price_change, row.price_yesterday);
    if (pct == null) { unknown += 1; continue; }
    if (pct > 0) up += 1;
    else if (pct < 0) down += 1;
    else flat += 1;
  }
  const known = up + down + flat;
  const pctOf = (n: number) => (known ? Math.round((n / known) * 100) : 0);
  return { up, down, flat, unknown, total: rows.length,
    upPct: pctOf(up), downPct: pctOf(down),
    flatPct: Math.max(0, 100 - pctOf(up) - pctOf(down)) };
}

export function boardSums(rows: readonly MarketRow[]): { value: number; volume: number } {
  let value = 0; let volume = 0;
  for (const row of rows) {
    if (row.q_tot_cap != null && Number.isFinite(row.q_tot_cap)) value += row.q_tot_cap;
    if (row.q_tot_tran != null && Number.isFinite(row.q_tot_tran)) volume += row.q_tot_tran;
  }
  return { value, volume };
}

const COMPOSITION_TYPES: AssetType[] = ['stock', 'payeh', 'right', 'energy', 'fund'];

export const TYPE_LABEL: Record<AssetType | 'other', string> = {
  stock: 'سهام',
  payeh: 'پایه',
  option: 'اختیار',
  fund: 'صندوق',
  bond: 'اوراق',
  right: 'حق تقدم',
  teseh: 'تسه',
  tal: 'TAL',
  ati: 'آتی',
  kala: 'کالا',
  energy: 'انرژی',
  other: 'سایر',
};

export function compositionOf(rows: readonly MarketRow[]): { type: AssetType | 'other'; count: number }[] {
  const counts = new Map<AssetType, number>();
  for (const row of rows) {
    const type = classifyAssetType(row);
    counts.set(type, (counts.get(type) ?? 0) + 1);
  }
  const out = COMPOSITION_TYPES.map((type) => ({ type: type as AssetType | 'other', count: counts.get(type) ?? 0 }));
  let other = 0;
  for (const [type, count] of counts) if (!COMPOSITION_TYPES.includes(type)) other += count;
  if (other > 0) out.push({ type: 'other', count: other });
  return out;
}
```

در `StatusStrip.tsx` سه تابعِ محلی (`breadthOf`, `sumsOf`, `compositionOf`) و نوعِ `Breadth` را حذف کن و از فایلِ تازه ایمپورت کن؛ برای سازگاریِ ایمپورت‌هایِ موجود این سطر را نگه دار:

```ts
export { breadthOf, type Breadth } from '../lib/boardMetrics';
```

- [ ] **Step 4: رجیستری را بنویس**

```ts
// frontend-v2/src/features/market/components/cards/registry.ts
import { faNum, fmtInt, fmtMcap, fmtVolume } from '@shared/lib/fa';
import type { MarketFeed, MarketRow } from '@shared/types/market';
import type { CardId } from '@shared/workspace/store';
import type { MarketSnapshot } from '../../api/useMarketSnapshot';
import { boardSums, breadthOf, compositionOf, TYPE_LABEL } from '../../lib/boardMetrics';

export interface CardContext {
  rows: readonly MarketRow[];
  feed?: MarketFeed;
  snapshot?: MarketSnapshot;
}

export interface PreviewRow {
  label: string;
  value: string;
  basis?: 'board' | 'market';
  note?: string;
}

export interface CardDescriptor {
  id: CardId;
  label: string;
  unit?: string;
  basis: 'board' | 'market';
  value: (ctx: CardContext) => string | null;
  delta: (ctx: CardContext) => number | null;
  preview: (ctx: CardContext) => PreviewRow[];
}

const noPrev = 'نشستِ قبل در دسترس نیست';

function marketDelta(current: number | null | undefined, previous: number | null | undefined): number | null {
  if (current == null || previous == null || previous === 0) return null;
  return ((current - previous) / previous) * 100;
}

export const CARD_REGISTRY: Record<CardId, CardDescriptor> = {
  tedpix: {
    id: 'tedpix', label: 'شاخص کل بورس', basis: 'market',
    value: ({ snapshot }) => (snapshot?.index?.last != null ? fmtInt(snapshot.index.last) : null),
    delta: ({ snapshot }) => snapshot?.index?.pct ?? null,
    preview: ({ snapshot }) => {
      const index = snapshot?.index;
      const market = snapshot?.market;
      if (!index) return [{ label: 'شاخص کل', value: '—', note: 'snapshot نرسیده' }];
      return [
        { label: 'هم‌وزن', value: index.ew_last != null ? `${fmtInt(index.ew_last)} (${faNum(index.ew_pct ?? 0)}٪)` : '—', basis: 'market' },
        { label: 'ارزش', value: market?.trade_value_hemat != null ? `${fmtMcap(market.trade_value_hemat)} همت` : '—', basis: 'market' },
        { label: 'حجم', value: market?.volume != null ? fmtVolume(market.volume) : '—', basis: 'market' },
        { label: 'تعداد معاملات', value: market?.trades != null ? fmtInt(market.trades) : '—', basis: 'market' },
        { label: 'نسبت به نشست قبل', value: snapshot?.prev?.last != null ? `${faNum(Math.round(marketDelta(index.last, snapshot.prev.last) ?? 0))}٪` : '—', basis: 'market', note: snapshot?.prev ? undefined : noPrev },
      ];
    },
  },
  retailValue: {
    id: 'retailValue', label: 'ارزش معاملات خرد', unit: 'همت', basis: 'market',
    value: ({ snapshot }) => (snapshot?.retail?.value_hemat != null ? fmtMcap(snapshot.retail.value_hemat) : null),
    delta: ({ snapshot }) => marketDelta(
      snapshot?.market?.trade_value_hemat ?? null,
      snapshot?.prev?.q_tot_cap != null ? snapshot.prev.q_tot_cap / 1e13 : null,
    ),
    preview: ({ snapshot }) => {
      const retail = snapshot?.retail;
      if (!retail) return [{ label: 'ارزش خرد', value: '—', note: 'snapshot نرسیده' }];
      return [
        { label: 'وضعیت', value: retail.label ?? '—', basis: 'market' },
        { label: 'آستانهٔ مساعد', value: retail.good_min != null ? `${faNum(retail.good_min)} همت` : '—', basis: 'market' },
        { label: 'آستانهٔ نامساعد', value: retail.bad_max != null ? `${faNum(retail.bad_max)} همت` : '—', basis: 'market' },
        { label: 'ارزش بازار', value: snapshot.market?.market_value_hemat != null ? `${fmtMcap(snapshot.market.market_value_hemat)} همت` : '—', basis: 'market' },
      ];
    },
  },
  boardValueComposition: {
    id: 'boardValueComposition', label: 'ارزش و ترکیب تابلو', unit: 'همت', basis: 'board',
    value: ({ rows }) => (rows.length ? fmtMcap(boardSums(rows).value / 1e13) : null),
    delta: () => null,
    preview: ({ rows }) => {
      const sums = boardSums(rows);
      const pieces = compositionOf(rows);
      return [
        { label: 'حجم', value: fmtVolume(sums.volume), basis: 'board' },
        { label: 'ردیف', value: fmtInt(rows.length), basis: 'board' },
        ...pieces.map((piece) => ({
          label: TYPE_LABEL[piece.type],
          value: fmtInt(piece.count), basis: 'board' as const,
        })),
      ];
    },
  },
  breadth: {
    id: 'breadth', label: 'پهنای بازار', basis: 'board',
    value: ({ rows }) => {
      if (!rows.length) return null;
      const b = breadthOf(rows);
      return `${fmtInt(b.up)}▲ / ${fmtInt(b.down)}▼`;
    },
    delta: () => null,
    preview: ({ rows }) => {
      const b = breadthOf(rows);
      return [
        { label: 'مثبت', value: `${fmtInt(b.up)} (${faNum(b.upPct)}٪)`, basis: 'board' },
        { label: 'منفی', value: `${fmtInt(b.down)} (${faNum(b.downPct)}٪)`, basis: 'board' },
        { label: 'بی‌تغییر', value: `${fmtInt(b.flat)} (${faNum(b.flatPct)}٪)`, basis: 'board' },
        { label: 'بدونِ درصدِ خوانا', value: fmtInt(b.unknown), basis: 'board', note: 'در این ردیف‌ها درصد خوانا نیست' },
      ];
    },
  },
  boardVolume: {
    id: 'boardVolume', label: 'حجم تابلو', basis: 'board',
    value: ({ rows }) => (rows.length ? fmtVolume(boardSums(rows).volume) : null),
    delta: () => null,
    preview: ({ rows }) => [
      { label: 'ارزش', value: fmtMcap(boardSums(rows).value / 1e13) + ' همت', basis: 'board' },
      { label: 'ردیف', value: fmtInt(rows.length), basis: 'board' },
    ],
  },
  marketTrades: {
    id: 'marketTrades', label: 'تعداد معاملات بازار', basis: 'market',
    value: ({ snapshot }) => (snapshot?.market?.trades != null ? fmtInt(snapshot.market.trades) : null),
    delta: ({ snapshot }) => marketDelta(
      snapshot?.market?.trades ?? null,
      snapshot?.prev?.z_tot_tran ?? null,
    ),
    preview: ({ snapshot }) => [
      { label: 'حجم', value: snapshot?.market?.volume != null ? fmtVolume(snapshot.market.volume) : '—', basis: 'market' },
      { label: 'ارزش', value: snapshot?.market?.trade_value_hemat != null ? `${fmtMcap(snapshot.market.trade_value_hemat)} همت` : '—', basis: 'market' },
      { label: 'نسبت به نشست قبل', value: snapshot?.prev?.z_tot_tran != null ? `${faNum(Math.round(marketDelta(snapshot.market?.trades ?? null, snapshot.prev.z_tot_tran) ?? 0))}٪` : '—', basis: 'market', note: snapshot?.prev ? undefined : noPrev },
    ],
  },
};

export const CARD_ORDER: CardId[] = [
  'tedpix', 'retailValue', 'breadth', 'boardValueComposition', 'boardVolume', 'marketTrades',
];
```

برچسبِ نوع دارایی در پیش‌نمایش فارسی است. `TYPE_SHORT` در `StatusStrip` حذف و با `TYPE_LABEL` از `boardMetrics.ts` جایگزین می‌شود تا یک منبع داشته باشد.

- [ ] **Step 5: تست را سبز کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/card-registry.spec.ts`
Expected: PASS (۵ تست)

- [ ] **Step 6: کامیت**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/features/market/lib/boardMetrics.ts frontend-v2/src/features/market/components/cards/registry.ts frontend-v2/src/features/market/components/StatusStrip.tsx frontend-v2/src/__tests__/card-registry.spec.ts
git commit -m "$(cat <<'EOF'
feat(market): رجیستریِ کارت‌ها و متریک‌های مشترکِ تابلو

هر کارت مبنا و پیش‌نمایشِ خودش را دارد؛ عددِ بی‌مبنا و دلتای بی‌نشست ساخته نمی‌شود.
EOF
)"
```

---

## Task 9: نوارِ کارت‌ها با پیش‌نمایش و شخصی‌سازی

**Files:**
- Create: `frontend-v2/src/features/market/components/cards/CardTile.tsx`
- Create: `frontend-v2/src/features/market/components/SnapshotStrip.tsx`
- Test: `frontend-v2/src/__tests__/snapshot-strip.spec.tsx`

**Interfaces:**
- Consumes: `CARD_REGISTRY`, `CARD_ORDER`, `useWorkspace` (slots/setSlots), `MarketSnapshot`
- Produces:
  - `<CardTile descriptor context value onMoveLeft onMoveRight onPick />`
  - `<SnapshotStrip rows snapshot />` با `data-testid="snapshot-strip"`

- [ ] **Step 1: تستِ ناکام بنویس**

```tsx
// frontend-v2/src/__tests__/snapshot-strip.spec.tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { MarketRow } from '@shared/types/market';
import type { MarketSnapshot } from '@features/market/api/useMarketSnapshot';
import { SnapshotStrip } from '@features/market/components/SnapshotStrip';
import { DEFAULT_SLOTS, useWorkspace } from '@shared/workspace/store';

const rows = [
  { symbol: 'الف', ins_code: '10', price_yesterday: 100, p_closing: 110, percent_change: 10,
    q_tot_cap: 6e9, q_tot_tran: 2e6 },
] as MarketRow[];

const snapshot = {
  status: 'ok',
  index: { d_even: 20261028, last: 8_000_000, change: 1, pct: 1.2,
    ew_last: 2_200_000, ew_change: 1, ew_pct: 0.2 },
  prev: { d_even: 20261027, last: 7_900_000, change: 0, pct: 0,
    ew_last: 2_100_000, ew_change: 0, ew_pct: 0,
    z_tot_tran: 600_000, q_tot_cap: 4e14, q_tot_tran: 8e9 },
  market: { trade_value_hemat: 40, volume: 1e10, trades: 800_000, market_value_hemat: 8000 },
  retail: { value_hemat: 45, state: 'good', label: 'مساعد', good_min: 20, bad_max: 10,
    excellent_min: 50, basis: 'b', cause: null },
} as MarketSnapshot;

beforeEach(() => {
  localStorage.clear();
  useWorkspace.setState(useWorkspace.getInitialState(), true);
});

afterEach(cleanup);

describe('SnapshotStrip', () => {
  it('renders the four default cards', () => {
    render(<SnapshotStrip rows={rows} snapshot={snapshot} />);
    expect(screen.getByTestId('snapshot-strip')).toBeTruthy();
    expect(screen.getAllByTestId(/^card-/)).toHaveLength(4);
  });

  it('opens the preview on hover and labels the basis', () => {
    render(<SnapshotStrip rows={rows} snapshot={snapshot} />);
    fireEvent.mouseEnter(screen.getByTestId('card-tedpix'));
    const preview = screen.getByTestId('preview-tedpix');
    expect(preview.textContent).toContain('تعداد معاملات');
    expect(preview.textContent).toContain('کل بازار');
  });

  it('shows a dash, not zero, when the snapshot is missing', () => {
    render(<SnapshotStrip rows={rows} />);
    expect(screen.getByTestId('card-retailValue').textContent).toContain('—');
  });

  it('reorders cards and persists the new slots', () => {
    render(<SnapshotStrip rows={rows} snapshot={snapshot} />);
    fireEvent.click(screen.getByTestId('card-move-right-tedpix'));
    expect(useWorkspace.getState().workspaces[0].slots[0]).toBe(DEFAULT_SLOTS[1]);
  });

  it('changes a slot from the catalog', () => {
    render(<SnapshotStrip rows={rows} snapshot={snapshot} />);
    fireEvent.click(screen.getByTestId('card-pick-tedpix'));
    fireEvent.click(screen.getByTestId('card-option-tedpix-marketTrades'));
    expect(useWorkspace.getState().workspaces[0].slots).toContain('marketTrades');
  });
});
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/snapshot-strip.spec.tsx`
Expected: FAIL با `Failed to resolve import`

- [ ] **Step 3: `CardTile` را بنویس**

```tsx
// frontend-v2/src/features/market/components/cards/CardTile.tsx
import { useState } from 'react';
import clsx from 'clsx';
import { faNum } from '@shared/lib/fa';
import type { CardDescriptor, CardContext } from './registry';

interface Props {
  descriptor: CardDescriptor;
  context: CardContext;
  onMoveLeft: () => void;
  onMoveRight: () => void;
  onPick: (id: CardDescriptor['id']) => void;
}

export function CardTile({ descriptor, context, onMoveLeft, onMoveRight, onPick }: Props) {
  const [open, setOpen] = useState(false);
  const [picking, setPicking] = useState(false);
  const value = descriptor.value(context);
  const delta = descriptor.delta(context);
  const rows = descriptor.preview(context);

  return (
    <section
      data-testid={`card-${descriptor.id}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      tabIndex={0}
      className="relative min-w-0 flex-1 rounded-[var(--radius-sm)] border border-line bg-panel px-2 py-1"
    >
      <div className="flex items-baseline justify-between gap-2 t-9 font-bold text-text-2">
        <span className="truncate">{descriptor.label}</span>
        <div className="flex items-center gap-0.5">
          <button type="button" data-testid={`card-move-right-${descriptor.id}`} aria-label="یک خانه به راست"
            className="grid h-4 w-4 place-items-center rounded-[var(--radius-xs)] text-text-3 hover:bg-panel-2"
            onClick={onMoveRight}>›</button>
          <button type="button" data-testid={`card-move-left-${descriptor.id}`} aria-label="یک خانه به چپ"
            className="grid h-4 w-4 place-items-center rounded-[var(--radius-xs)] text-text-3 hover:bg-panel-2"
            onClick={onMoveLeft}>‹</button>
          <button type="button" data-testid={`card-pick-${descriptor.id}`} aria-label="تغییرِ کارت"
            className="grid h-4 w-4 place-items-center rounded-[var(--radius-xs)] text-text-3 hover:bg-panel-2"
            onClick={() => setPicking((value) => !value)}>⋯</button>
        </div>
      </div>

      <div className="mt-0.5 flex items-baseline gap-1.5">
        <b className="num text-[19px] font-extrabold leading-none tracking-tight">{value ?? '—'}</b>
        {descriptor.unit && value != null ? <small className="t-95 text-text-3">{descriptor.unit}</small> : null}
        {delta != null ? (
          <span className={clsx('num t-9', delta > 0 ? 'text-up' : delta < 0 ? 'text-down' : 'text-flat')}>
            {delta > 0 ? '▲' : delta < 0 ? '▼' : '•'} {faNum(Math.abs(Math.round(delta * 10) / 10))}٪
          </span>
        ) : (
          <span className="t-9 text-text-3" title="نشستِ قبلِ هم‌مبنا در دسترس نیست">—</span>
        )}
      </div>

      {picking ? (
        <div className="absolute inset-x-0 top-full z-30 mt-1 rounded-[var(--radius-sm)] border border-line bg-panel p-1 t-9">
          {(['tedpix', 'retailValue', 'breadth', 'boardValueComposition', 'boardVolume', 'marketTrades'] as const)
            .filter((id) => id !== descriptor.id)
            .map((id) => (
              <button key={id} type="button" data-testid={`card-option-${descriptor.id}-${id}`}
                className="block w-full rounded-[var(--radius-xs)] px-2 py-1 text-start hover:bg-panel-2"
                onClick={() => { setPicking(false); onPick(id); }}>
                {id}
              </button>
            ))}
        </div>
      ) : null}

      {open && !picking ? (
        <div data-testid={`preview-${descriptor.id}`}
          className="absolute inset-x-0 top-full z-30 mt-1 rounded-[var(--radius-sm)] border border-line bg-panel p-1.5 t-9 text-text-2">
          <div className="mb-1 flex items-center justify-between text-text-3">
            <span>{descriptor.basis === 'board' ? 'تابلو' : 'کل بازار'}</span>
            <span className="t-85">پیش‌نمایش</span>
          </div>
          {rows.map((row) => (
            <div key={row.label} className="flex items-baseline justify-between gap-2">
              <span className="text-text-3">{row.label}</span>
              <span className="num font-semibold" title={row.note}>{row.value}</span>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
```

نامِ کارت در منوی تغییر باید برچسبِ فارسی باشد، نه id؛ برای این کار از `CARD_REGISTRY[id].label` استفاده کن.

- [ ] **Step 4: `SnapshotStrip` را بنویس**

```tsx
// frontend-v2/src/features/market/components/SnapshotStrip.tsx
import type { MarketRow } from '@shared/types/market';
import { useWorkspace, type CardId } from '@shared/workspace/store';
import type { MarketSnapshot } from '../api/useMarketSnapshot';
import { CARD_REGISTRY } from './cards/registry';
import { CardTile } from './cards/CardTile';

export function SnapshotStrip({ rows, snapshot }: { rows: readonly MarketRow[]; snapshot?: MarketSnapshot }) {
  const slots = useWorkspace((state) => state.workspaces[0].slots);
  const setSlots = useWorkspace((state) => state.setSlots);

  function move(index: number, offset: number) {
    const next = [...slots];
    const target = index + offset;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    setSlots(next);
  }

  function pick(index: number, id: CardId) {
    const next = slots.filter((slot) => slot !== id);
    next.splice(index, 1, id);
    setSlots(next);
  }

  return (
    <div data-testid="snapshot-strip" className="flex shrink-0 items-stretch gap-1.5 border-b border-line bg-panel px-2 py-1.5">
      {slots.map((id, index) => (
        <CardTile
          key={id}
          descriptor={CARD_REGISTRY[id]}
          context={{ rows, snapshot }}
          onMoveLeft={() => move(index, -1)}
          onMoveRight={() => move(index, 1)}
          onPick={(next) => pick(index, next as CardId)}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 5: تست را سبز کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/snapshot-strip.spec.tsx`
Expected: PASS (۵ تست)

- [ ] **Step 6: کامیت**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/features/market/components/cards/CardTile.tsx frontend-v2/src/features/market/components/SnapshotStrip.tsx frontend-v2/src/__tests__/snapshot-strip.spec.tsx
git commit -m "$(cat <<'EOF'
feat(market): نوارِ کارت‌ها با پیش‌نمایش و شخصی‌سازی

هر کارت مبنا و پیش‌نمایشِ خودش را دارد؛ جابه‌جایی و تغییرِ کارت ذخیره می‌شود.
EOF
)"
```

## Task 10: کاشیِ نماد

**Files:**
- Create: `frontend-v2/src/features/market/panels/SymbolPanel.tsx`
- Test: `frontend-v2/src/__tests__/symbol-panel.spec.tsx`

**Interfaces:**
- Consumes: `OrderBookFive({symbol,insCode,boardDay})`, `TapeHistoryPanel({symbol,insCode})`, `WatchlistButton({symbol,name})`, `ChartPanel`
- Produces: `<SymbolPanel row boardDay chartOpen onToggleChart />`

- [ ] **Step 1: تستِ ناکام بنویس**

```tsx
// frontend-v2/src/__tests__/symbol-panel.spec.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/market';
import { SymbolPanel } from '@features/market/panels/SymbolPanel';

vi.mock('@features/chart/ui/ChartPanel', () => ({
  ChartPanel: ({ symbol }: { symbol: string }) => <div data-testid="chart-stub">{symbol}</div>,
}));
vi.mock('@features/market/components/OrderBookFive', () => ({
  OrderBookFive: ({ symbol }: { symbol: string }) => <div data-testid="book-stub">{symbol}</div>,
}));
vi.mock('@features/market/components/TapeHistoryPanel', () => ({
  TapeHistoryPanel: ({ symbol }: { symbol: string }) => <div data-testid="history-stub">{symbol}</div>,
}));
vi.mock('@features/market/components/WatchlistButton', () => ({
  WatchlistButton: () => <button type="button">واچ‌لیست</button>,
}));

const row = {
  symbol: 'الف', ins_code: '10', name: 'شرکت الف',
  p_last: 112, p_closing: 110, percent_change: 10, q_tot_cap: 6e9, q_tot_tran: 2e6,
  pe: 7.4, mcap: 1.2e12, p_min: 100, p_max: 115,
} as MarketRow;

function mount(props: Partial<Parameters<typeof SymbolPanel>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SymbolPanel row={row} boardDay={20261028} chartOpen onToggleChart={() => {}} {...props} />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe('SymbolPanel', () => {
  it('shows an honest empty state', () => {
    mount({ row: null });
    expect(screen.getByTestId('symbol-empty').textContent).toContain('نمادی');
  });

  it('renders the key numbers and the chart', () => {
    mount();
    expect(screen.getByTestId('symbol-title').textContent).toContain('الف');
    expect(screen.getByTestId('symbol-pe').textContent).toContain('۷');
    expect(screen.getByTestId('chart-stub')).toBeTruthy();
  });

  it('hides the chart when collapsed', () => {
    mount({ chartOpen: false });
    expect(screen.queryByTestId('chart-stub')).toBeNull();
    expect(screen.getByTestId('symbol-chart-toggle').textContent).toContain('باز');
  });

  it('switches between depth, history and fundamental tabs', () => {
    mount();
    expect(screen.getByTestId('book-stub')).toBeTruthy();
    fireEvent.click(screen.getByTestId('symbol-tab-history'));
    expect(screen.getByTestId('history-stub')).toBeTruthy();
    fireEvent.click(screen.getByTestId('symbol-tab-fundamental'));
    expect(screen.getByTestId('symbol-fundamental-empty').textContent).toContain('وصل نشده');
  });
});
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/symbol-panel.spec.tsx`
Expected: FAIL با `Failed to resolve import`

- [ ] **Step 3: پیاده‌سازی**

```tsx
// frontend-v2/src/features/market/panels/SymbolPanel.tsx
import { useState } from 'react';
import clsx from 'clsx';
import { faNum, fmtInt, fmtMcap, fmtVolume, toFaDigits } from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';
import { ChartPanel } from '@features/chart/ui/ChartPanel';
import { OrderBookFive } from '../components/OrderBookFive';
import { TapeHistoryPanel } from '../components/TapeHistoryPanel';
import { WatchlistButton } from '../components/WatchlistButton';

type LowerTab = 'book' | 'history' | 'fundamental';

function number(value: number | null | undefined, format: (n: number) => string): string {
  return value == null || !Number.isFinite(value) ? '—' : format(value);
}

export function SymbolPanel({ row, boardDay, chartOpen, onToggleChart }: {
  row: MarketRow | null;
  boardDay: number | null;
  chartOpen: boolean;
  onToggleChart: () => void;
}) {
  const [tab, setTab] = useState<LowerTab>('book');

  if (!row) {
    return (
      <div data-testid="symbol-empty" className="flex h-full flex-col items-center justify-center gap-1 text-text-3">
        <b className="t-115 text-text-2">نمادی انتخاب نشده</b>
        <span className="t-10">روی ردیفِ تابلو کلیک کن.</span>
      </div>
    );
  }

  const pct = row.percent_change;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-none items-baseline gap-2 border-b border-line px-2 py-1">
        <b data-testid="symbol-title" className="t-115 font-extrabold">{row.symbol}</b>
        <span className="min-w-0 truncate t-9 text-text-3">{row.name ?? ''}</span>
        <span className="num ms-auto t-11 font-bold">{number(row.p_last ?? row.p_closing, fmtInt)}</span>
        <span className={clsx('num t-10', pct == null ? 'text-text-3' : pct > 0 ? 'text-up' : pct < 0 ? 'text-down' : 'text-flat')}>
          {pct == null ? '—' : `${pct > 0 ? '▲' : pct < 0 ? '▼' : '•'} ${faNum(Math.abs(pct))}٪`}
        </span>
        <WatchlistButton symbol={row.symbol} name={row.name ?? undefined} />
      </div>

      <div className="flex flex-none items-center justify-between border-b border-line px-2 py-0.5 t-9 text-text-3">
        <span>چارت</span>
        <button type="button" data-testid="symbol-chart-toggle" onClick={onToggleChart}
          className="rounded-[var(--radius-xs)] px-1 hover:bg-panel-2">
          {chartOpen ? 'بستن' : 'باز کردن'}
        </button>
      </div>
      {chartOpen ? (
        <div className="h-[180px] flex-none border-b border-line">
          <ChartPanel symbol={row.symbol} />
        </div>
      ) : null}

      <div className="grid flex-none grid-cols-2 gap-x-3 gap-y-[2px] border-b border-line px-2 py-1 t-95">
        <span className="flex justify-between"><span className="text-text-3">پایانی</span><b className="num">{number(row.p_closing, fmtInt)}</b></span>
        <span className="flex justify-between"><span className="text-text-3">حجم</span><b className="num">{number(row.q_tot_tran, fmtVolume)}</b></span>
        <span className="flex justify-between"><span className="text-text-3">ارزش</span><b className="num">{number(row.q_tot_cap, (n) => `${fmtMcap(n / 1e13)} همت`)}</b></span>
        <span className="flex justify-between"><span className="text-text-3">P/E</span><b data-testid="symbol-pe" className="num">{number(row.pe, (n) => toFaDigits(n.toFixed(1)))}</b></span>
        <span className="flex justify-between"><span className="text-text-3">مارکت‌کپ</span><b className="num">{number(row.mcap, (n) => fmtMcap(n))}</b></span>
        <span className="flex justify-between"><span className="text-text-3">کم/بیشترین</span><b className="num">{number(row.p_min, fmtInt)} / {number(row.p_max, fmtInt)}</b></span>
      </div>

      <div className="flex flex-none items-center gap-1 border-b border-line px-2 py-0.5" role="tablist">
        {([['book', 'عمق'], ['history', 'تاریخچه تابلو'], ['fundamental', 'بنیادی']] as const).map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id}
            data-testid={`symbol-tab-${id}`}
            onClick={() => setTab(id)}
            className={clsx('tape-btn', tab === id && 'is-on')}>
            {label}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {tab === 'book' ? <OrderBookFive symbol={row.symbol} insCode={row.ins_code} boardDay={boardDay} /> : null}
        {tab === 'history' ? <TapeHistoryPanel symbol={row.symbol} insCode={row.ins_code} /> : null}
        {tab === 'fundamental' ? (
          <p data-testid="symbol-fundamental-empty" className="p-2 t-95 text-text-3">
            دادهٔ بنیادی هنوز به این نسخه وصل نشده است.
          </p>
        ) : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: تست را سبز کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/symbol-panel.spec.tsx`
Expected: PASS (۴ تست)

- [ ] **Step 5: کامیت**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/features/market/panels/SymbolPanel.tsx frontend-v2/src/__tests__/symbol-panel.spec.tsx
git commit -m "$(cat <<'EOF'
feat(market): کاشیِ نماد با چارتِ تاشو و تب‌های عمق و تاریخچه

هویت با ins_code می‌ماند و دادهٔ بنیادی تا وصل‌نشدن، صادقانه خالی است.
EOF
)"
```

---

## Task 11: کاشیِ دیده‌بان‌ها

**Files:**
- Create: `frontend-v2/src/features/market/panels/WatchPanel.tsx`
- Test: `frontend-v2/src/__tests__/watch-panel.spec.tsx`

**Interfaces:**
- Consumes: `SuspiciousPanel`, `IndustryScreener`, `TapeFilterConfig`
- Produces: `<WatchPanel rows filterConfig onSelect onPickSector />`

- [ ] **Step 1: تستِ ناکام بنویس**

```tsx
// frontend-v2/src/__tests__/watch-panel.spec.tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/market';
import { WatchPanel } from '@features/market/panels/WatchPanel';

vi.mock('@features/market/components/SuspiciousPanel', () => ({
  SuspiciousPanel: ({ onSelect, sections }: { onSelect: (id: string) => void; sections: string[] }) => (
    <button type="button" data-testid="susp-stub" onClick={() => onSelect('10')}>{sections.join(',')}</button>
  ),
}));
vi.mock('@features/market/components/IndustryScreener', () => ({
  IndustryScreener: ({ onPick }: { onPick: (sector: string) => void }) => (
    <button type="button" data-testid="industry-stub" onClick={() => onPick('فلزات')}>صنایع</button>
  ),
}));

const rows = [{ symbol: 'الف', ins_code: '10' }] as MarketRow[];
const filterConfig = {} as never;

afterEach(cleanup);

describe('WatchPanel', () => {
  it('shows the global scope label', () => {
    render(<WatchPanel rows={rows} filterConfig={filterConfig} onSelect={() => {}} />);
    expect(screen.getByTestId('watch-scope-label').textContent).toContain('کل تابلو');
  });

  it('switches the three tabs', () => {
    render(<WatchPanel rows={rows} filterConfig={filterConfig} onSelect={() => {}} />);
    expect(screen.getByTestId('susp-stub').textContent).toBe('clock');
    fireEvent.click(screen.getByTestId('watch-tab-susp'));
    expect(screen.getByTestId('susp-stub').textContent).toBe('susp,roobi');
    fireEvent.click(screen.getByTestId('watch-tab-industries'));
    expect(screen.getByTestId('industry-stub')).toBeTruthy();
  });

  it('reports the selected ins_code without navigating', () => {
    const onSelect = vi.fn();
    render(<WatchPanel rows={rows} filterConfig={filterConfig} onSelect={onSelect} />);
    fireEvent.click(screen.getByTestId('susp-stub'));
    expect(onSelect).toHaveBeenCalledWith('10');
  });

  it('passes the sector pick upward', () => {
    const onPickSector = vi.fn();
    render(<WatchPanel rows={rows} filterConfig={filterConfig} onSelect={() => {}} onPickSector={onPickSector} />);
    fireEvent.click(screen.getByTestId('watch-tab-industries'));
    fireEvent.click(screen.getByTestId('industry-stub'));
    expect(onPickSector).toHaveBeenCalledWith('فلزات');
  });
});
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/watch-panel.spec.tsx`
Expected: FAIL با `Failed to resolve import`

- [ ] **Step 3: پیاده‌سازی**

```tsx
// frontend-v2/src/features/market/panels/WatchPanel.tsx
import { useState } from 'react';
import type { MarketRow } from '@shared/types/market';
import type { TapeFilterConfig } from '../lib/tapeAlgorithms';
import { IndustryScreener } from '../components/IndustryScreener';
import { SuspiciousPanel, type SuspSection } from '../components/SuspiciousPanel';

type WatchTabId = 'clock' | 'susp' | 'industries';

const TABS: { id: WatchTabId; label: string; sections: SuspSection[] | null }[] = [
  { id: 'clock', label: 'دیده‌بان ساعت', sections: ['clock'] },
  { id: 'susp', label: 'دیده‌بان حجم مشکوک', sections: ['susp', 'roobi'] },
  { id: 'industries', label: 'صنایع داغ', sections: null },
];

export function WatchPanel({ rows, filterConfig, onSelect, onPickSector }: {
  rows: MarketRow[];
  filterConfig: TapeFilterConfig;
  onSelect: (insCode: string) => void;
  onPickSector?: (industry: string) => void;
}) {
  const [tab, setTab] = useState<WatchTabId>('clock');
  const active = TABS.find((item) => item.id === tab) ?? TABS[0];

  return (
    <div data-testid="watch-panel" className="flex h-full min-h-0 flex-col">
      <div className="flex flex-none items-center gap-1 overflow-x-auto border-b border-line px-2 py-0.5" role="tablist" aria-label="دیده‌بان‌ها">
        <span data-testid="watch-scope-label" className="shrink-0 t-9 text-text-3">
          دیده‌بان‌ها <span className="text-text-3/70">· کل تابلو</span>
        </span>
        {TABS.map((item) => (
          <button key={item.id} type="button" role="tab" aria-selected={tab === item.id}
            data-testid={`watch-tab-${item.id}`}
            onClick={() => setTab(item.id)}
            className="tape-btn ms-1 whitespace-nowrap">
            {item.label}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-1">
        {active.sections
          ? <SuspiciousPanel rows={rows} filterConfig={filterConfig} onSelect={onSelect} sections={active.sections} />
          : <IndustryScreener onPick={(sector) => onPickSector?.(sector)} />}
      </div>
    </div>
  );
}
```

`tape-btn` کلاسِ موجود در `index.css` است؛ اگر حالتِ فعال ندارد، `aria-selected` را با کلاسِ `bg-panel-3 text-text` بیارا (نه رنگِ تازه).

- [ ] **Step 4: تست را سبز کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/watch-panel.spec.tsx`
Expected: PASS (۴ تست)

- [ ] **Step 5: کامیت**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/features/market/panels/WatchPanel.tsx frontend-v2/src/__tests__/watch-panel.spec.tsx
git commit -m "$(cat <<'EOF'
feat(market): کاشیِ دیده‌بان‌ها به‌جای داکِ افقی

همان سه تب و همان کامپوننت‌ها، این بار عمودی و با برچسبِ دامنهٔ کل تابلو.
EOF
)"
```

---

## Task 12: چارتِ کندل

**Files:**
- Modify: `frontend-v2/package.json` و `package-lock.json` (افزودنِ `klinecharts@^10.0.3`)
- Create: `frontend-v2/src/features/chart/api/useChart.ts`
- Create: `frontend-v2/src/features/chart/ui/ChartPanel.tsx`
- Test: `frontend-v2/src/__tests__/chart-panel.spec.tsx`

**Interfaces:**
- Produces:
  - `toKlineBars(candles) -> Array<{timestamp,open,high,low,close,volume}>`
  - `useChart(symbol)`
  - `<ChartPanel symbol />` با `data-testid="chart-panel"`

- [ ] **Step 1: وابستگی را نصب کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npm install klinecharts@^10.0.3`
Expected: `package.json` و `package-lock.json` تغییر می‌کنند و `node_modules/klinecharts` وجود دارد.

- [ ] **Step 2: تستِ ناکام بنویس**

```tsx
// frontend-v2/src/__tests__/chart-panel.spec.tsx
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { toKlineBars, useChart } from '@features/chart/api/useChart';
import { ChartPanel } from '@features/chart/ui/ChartPanel';

vi.mock('@features/chart/api/useChart', async (original) => {
  const mod = await original<typeof import('@features/chart/api/useChart')>();
  return { ...mod, useChart: vi.fn() };
});
vi.mock('klinecharts', () => ({
  init: () => ({
    applyNewData: vi.fn(),
    resize: vi.fn(),
    createIndicator: vi.fn(),
  }),
  dispose: vi.fn(),
}));

function query(state: Record<string, unknown>) {
  return { data: undefined, isLoading: false, isError: false, error: null, ...state } as never;
}

beforeEach(() => {
  vi.mocked(useChart).mockReturnValue(query({ data: undefined }));
});

afterEach(cleanup);

describe('chart', () => {
  it('maps candles to kline bars in ascending order', () => {
    const bars = toKlineBars([
      { time: '2026-10-28', open: 10, high: 12, low: 9, close: 11, volume: 100 },
      { time: '2026-10-27', open: 9, high: 10, low: 8, close: 10, volume: 90 },
    ]);
    expect(bars.map((bar) => bar.close)).toEqual([10, 11]);
    expect(bars[1]).toMatchObject({ open: 10, high: 12, low: 9, close: 11, volume: 100 });
  });

  it('shows a loading state', () => {
    vi.mocked(useChart).mockReturnValue(query({ isLoading: true }));
    render(<ChartPanel symbol="الف" />);
    expect(screen.getByTestId('chart-loading')).toBeTruthy();
  });

  it('shows an honest empty state', () => {
    vi.mocked(useChart).mockReturnValue(query({ data: { status: 'success', candles: [] } }));
    render(<ChartPanel symbol="الف" />);
    expect(screen.getByTestId('chart-empty').textContent).toContain('کندلی');
  });

  it('shows the error reason', () => {
    vi.mocked(useChart).mockReturnValue(query({ isError: true, error: new Error('۵۰۲') }));
    render(<ChartPanel symbol="الف" />);
    expect(screen.getByTestId('chart-error').textContent).toContain('۵۰۲');
  });
});
```

- [ ] **Step 3: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/chart-panel.spec.tsx`
Expected: FAIL با `Failed to resolve import`

- [ ] **Step 4: هوک و مبدل را بنویس**

```ts
// frontend-v2/src/features/chart/api/useChart.ts
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const CandleSchema = z.looseObject({
  time: z.union([z.string(), z.number()]),
  open: z.number(), high: z.number(), low: z.number(), close: z.number(),
  volume: z.number().nullish(),
});

export const ChartSchema = z.looseObject({
  status: z.string(),
  candles: z.array(CandleSchema).default([]),
});

export type ChartPayload = z.infer<typeof ChartSchema>;

export function toKlineBars(candles: ChartPayload['candles']) {
  return [...candles]
    .sort((a, b) => String(a.time).localeCompare(String(b.time)))
    .map((candle) => ({
      timestamp: new Date(String(candle.time)).getTime(),
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
      volume: candle.volume ?? 0,
    }));
}

export function useChart(symbol: string, enabled = true) {
  return useQuery<ChartPayload>({
    queryKey: ['chart', symbol],
    queryFn: ({ signal }) => getJson(`/api/chart/${encodeURIComponent(symbol)}`, ChartSchema, signal),
    enabled,
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}
```

- [ ] **Step 5: `ChartPanel` را بنویس**

```tsx
// frontend-v2/src/features/chart/ui/ChartPanel.tsx
import { useEffect, useRef } from 'react';
import { toFaDigits } from '@shared/lib/fa';
import { toKlineBars, useChart } from '../api/useChart';

interface Engine {
  applyNewData: (bars: unknown[]) => void;
  resize: () => void;
}

export function ChartPanel({ symbol }: { symbol: string }) {
  const query = useChart(symbol);
  const host = useRef<HTMLDivElement>(null);
  const engine = useRef<Engine | null>(null);

  useEffect(() => {
    const hostEl = host.current;
    if (!hostEl) return;
    let cancelled = false;
    void (async () => {
      const { init } = await import('klinecharts');
      if (cancelled) return;
      engine.current = (init(hostEl) as unknown as Engine) ?? null;
    })();
    return () => {
      cancelled = true;
      engine.current = null;
      void import('klinecharts').then(({ dispose }) => dispose(hostEl));
    };
  }, [symbol]);

  useEffect(() => {
    if (query.data?.candles?.length) {
      engine.current?.applyNewData(toKlineBars(query.data.candles));
    }
  }, [query.data]);

  return (
    <div className="relative h-full w-full">
      <div data-testid="chart-panel" ref={host} className="h-full w-full" />
      {query.isLoading ? (
        <div data-testid="chart-loading" className="absolute inset-0 grid place-items-center bg-panel t-95 text-text-3">در حالِ بارگذاری چارت…</div>
      ) : null}
      {query.isError ? (
        <div data-testid="chart-error" className="absolute inset-0 grid place-items-center bg-panel t-95 text-down">
          چارت نیامد — {toFaDigits(String((query.error as Error)?.message ?? 'خطا'))}
        </div>
      ) : null}
      {!query.isLoading && !query.isError && !query.data?.candles?.length ? (
        <div data-testid="chart-empty" className="absolute inset-0 grid place-items-center bg-panel t-95 text-text-3">کندلی برای این نماد نیست.</div>
      ) : null}
    </div>
  );
}
```

نکتهٔ اجرا: `init` در klinecharts نسخهٔ ۱۰ یک شیء برمی‌گرداند؛ اگر امضای نسخهٔ نصب‌شده متفاوت بود، همان الگوی `frontend/src/features/technical/engine/klinecharts/KLineChartsEngine.ts` را دنبال کن و فقط همین فایل را عوض کن — نه جای دیگر.

- [ ] **Step 6: تست را سبز کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/chart-panel.spec.tsx && npx tsc -b`
Expected: PASS (۴ تست) و صفر خطای تایپ

- [ ] **Step 7: حجمِ باندل را اندازه بگیر و ثبت کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npm run build`
Expected: بیلد موفق؛ اندازهٔ چانکِ چارت را از خروجی بردار و در پیامِ کامیت بنویس.

- [ ] **Step 8: کامیت**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/package.json frontend-v2/package-lock.json frontend-v2/src/features/chart/api/useChart.ts frontend-v2/src/features/chart/ui/ChartPanel.tsx frontend-v2/src/__tests__/chart-panel.spec.tsx
git commit -m "$(cat <<'EOF'
feat(chart): چارتِ کندلِ حداقلی برای کاشیِ نماد

روزانه، بدونِ اندیکاتور؛ حالت‌های بارگذاری/خالی/خطا صادق‌اند و کتابخانه
تنبل بارگذاری می‌شود.
EOF
)"
```

---

## Task 13: ترکیبِ میزکار و حالتِ عرضِ کم

**Files:**
- Create: `frontend-v2/src/shared/lib/useMediaQuery.ts`
- Modify: `frontend-v2/src/features/market/routes/MarketPage.tsx`
- Delete: `frontend-v2/src/features/market/components/WatchDock.tsx`
- Delete: `frontend-v2/src/features/market/components/StatusStrip.tsx`
- Delete: `frontend-v2/src/features/market/components/QuickDrawer.tsx`
- Test: `frontend-v2/src/__tests__/market-workspace.spec.tsx`

**Interfaces:**
- Consumes: `SnapshotStrip`, `WorkspaceShell`, `useTileKeyboard`, `useWorkspace`, `BoardPanel`, `SymbolPanel`, `WatchPanel`, `ChartPanel`
- Produces: صفحهٔ `/market` که میزکار را رندر می‌کند

- [ ] **Step 1: تستِ ناکام بنویس**

```tsx
// frontend-v2/src/__tests__/market-workspace.spec.tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketPage } from '@features/market/routes/MarketPage';
import { useWorkspace } from '@shared/workspace/store';

vi.mock('@features/market/panels/BoardPanel', () => ({
  BoardPanel: ({ onSelect }: { onSelect: (row: unknown, day: number) => void }) => (
    <button type="button" data-testid="board-stub"
      onClick={() => onSelect({ symbol: 'الف', ins_code: '10', name: 'الف' }, 20261028)}>
      تابلو
    </button>
  ),
}));
vi.mock('@features/market/panels/SymbolPanel', () => ({
  SymbolPanel: ({ row }: { row: { symbol: string } | null }) => (
    <div data-testid="symbol-stub">{row?.symbol ?? 'خالی'}</div>
  ),
}));
vi.mock('@features/market/panels/WatchPanel', () => ({
  WatchPanel: () => <div data-testid="watch-stub">دیده‌بان</div>,
}));
vi.mock('@features/chart/ui/ChartPanel', () => ({ ChartPanel: () => <div data-testid="chart-stub" /> }));
vi.mock('@features/market/components/SnapshotStrip', () => ({
  SnapshotStrip: () => <div data-testid="strip-stub" />,
}));
vi.mock('@features/market/api/useBoard', () => ({
  useBoard: () => ({ data: { data: [], meta: { d_even: 20261028 } }, isLoading: false, isError: false }),
}));
vi.mock('@features/market/api/useMarketSnapshot', () => ({
  useMarketSnapshot: () => ({ data: undefined, isLoading: false, isError: false }),
}));

beforeEach(() => {
  localStorage.clear();
  useWorkspace.setState(useWorkspace.getInitialState(), true);
});

afterEach(cleanup);

describe('market workspace', () => {
  it('renders the default tiles', () => {
    render(<MarketPage />);
    expect(screen.getByTestId('board-stub')).toBeTruthy();
    expect(screen.getByTestId('symbol-stub')).toBeTruthy();
    expect(screen.getByTestId('watch-stub')).toBeTruthy();
    expect(screen.getByTestId('strip-stub')).toBeTruthy();
  });

  it('sets the active symbol from the board without navigating', () => {
    render(<MarketPage />);
    fireEvent.click(screen.getByTestId('board-stub'));
    expect(useWorkspace.getState().activeSymbol).toBe('10');
    expect(screen.getByTestId('symbol-stub').textContent).toBe('الف');
  });

  it('closes the watch tile from its header', () => {
    render(<MarketPage />);
    fireEvent.click(screen.getByTestId('tile-close-t-watch'));
    expect(screen.queryByTestId('watch-stub')).toBeNull();
  });

  it('opens the chart tile from the symbol menu', () => {
    render(<MarketPage />);
    const before = screen.getAllByTestId(/^tile-header-/).length;
    fireEvent.click(screen.getByTestId('tile-menu-t-symbol'));
    fireEvent.click(screen.getByTestId('tile-split-t-symbol-col-chart'));
    expect(screen.getAllByTestId(/^tile-header-/).length).toBe(before + 1);
    expect(screen.getByText('چارت')).toBeTruthy();
  });
});
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/market-workspace.spec.tsx`
Expected: FAIL (صفحهٔ فعلی میزکار را رندر نمی‌کند)

- [ ] **Step 3: `useMediaQuery` را بنویس**

```ts
// frontend-v2/src/shared/lib/useMediaQuery.ts
import { useEffect, useState } from 'react';

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia(query).matches
      : false);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const list = window.matchMedia(query);
    const onChange = () => setMatches(list.matches);
    setMatches(list.matches);
    list.addEventListener?.('change', onChange);
    return () => list.removeEventListener?.('change', onChange);
  }, [query]);

  return matches;
}
```

- [ ] **Step 4: `MarketPage` را بازنویسی کن**

```tsx
// frontend-v2/src/features/market/routes/MarketPage.tsx
import { useMemo, useState } from 'react';
import type { MarketRow } from '@shared/types/market';
import { useMediaQuery } from '@shared/lib/useMediaQuery';
import { useWorkspace } from '@shared/workspace/store';
import { useTileKeyboard } from '@shared/workspace/useTileKeyboard';
import { WorkspaceShell } from '@shared/workspace/WorkspaceShell';
import { findTile, type TilePanel } from '@shared/workspace/layout';
import { useBoard } from '../api/useBoard';
import { useMarketSnapshot } from '../api/useMarketSnapshot';
import { SnapshotStrip } from '../components/SnapshotStrip';
import { BoardPanel } from '../panels/BoardPanel';
import { SymbolPanel } from '../panels/SymbolPanel';
import { WatchPanel } from '../panels/WatchPanel';
import { ChartPanel } from '@features/chart/ui/ChartPanel';
import { DEFAULT_TAPE_FILTER_CONFIG } from '../lib/tapeAlgorithms';
import { useMarketPrefs } from '../stores/prefs';

type Tab = 'symbol' | 'watch';

export function MarketPage() {
  const layout = useWorkspace((state) => state.workspaces[0].layout);
  const chartOpen = useWorkspace((state) => state.workspaces[0].chartOpen);
  const activeSymbol = useWorkspace((state) => state.activeSymbol);
  const setActiveSymbol = useWorkspace((state) => state.setActiveSymbol);
  const setChartOpen = useWorkspace((state) => state.setChartOpen);
  const split = useWorkspace((state) => state.split);
  const close = useWorkspace((state) => state.close);
  const swap = useWorkspace((state) => state.swap);
  const setRatio = useWorkspace((state) => state.setRatio);
  const toggleFollow = useWorkspace((state) => state.toggleFollow);
  const pinned = useWorkspace((state) => state.pinned);

  const pollMs = useMarketPrefs((state) => state.pollMs);
  const board = useBoard(pollMs);
  const snapshot = useMarketSnapshot(pollMs);
  const rows = useMemo(() => board.data?.data ?? [], [board.data]);
  const [selectedRow, setSelectedRow] = useState<MarketRow | null>(null);
  const [boardDay, setBoardDay] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>('symbol');
  const narrow = useMediaQuery('(max-width: 1279px)');

  useTileKeyboard(layout);

  const symbolRow = useMemo(() => {
    if (!activeSymbol) return null;
    return rows.find((row) => (row.ins_code?.trim() || row.symbol) === activeSymbol) ?? null;
  }, [rows, activeSymbol]);

  function symbolFor(tileId: string): MarketRow | null {
    const tile = findTile(layout, tileId);
    const key = tile && !tile.follow ? (pinned[tileId] ?? null) : activeSymbol;
    if (!key) return null;
    return rows.find((row) => (row.ins_code?.trim() || row.symbol) === key) ?? null;
  }

  function selectRow(row: MarketRow, day: number | null) {
    const key = row.ins_code?.trim() || row.symbol;
    setSelectedRow(row);
    setBoardDay(day);
    setActiveSymbol(key);
  }

  function renderPanel(panel: TilePanel, tileId: string) {
    const tileRow = symbolFor(tileId);
    if (panel === 'board') {
      return (
        <BoardPanel
          selectedKey={activeSymbol}
          onSelect={selectRow}
          onActivate={selectRow}
        />
      );
    }
    if (panel === 'symbol') {
      return (
        <SymbolPanel
          row={tileRow ?? selectedRow}
          boardDay={boardDay ?? board.data?.meta?.d_even ?? null}
          chartOpen={chartOpen}
          onToggleChart={() => setChartOpen(!chartOpen)}
        />
      );
    }
    if (panel === 'watch') {
      return (
        <WatchPanel
          rows={rows}
          filterConfig={DEFAULT_TAPE_FILTER_CONFIG}
          onSelect={(insCode) => {
            setActiveSymbol(insCode);
            const row = rows.find((item) => (item.ins_code?.trim() || item.symbol) === insCode);
            if (row) setSelectedRow(row);
          }}
        />
      );
    }
    return tileRow ? <ChartPanel symbol={tileRow.symbol} /> : (
      <div className="grid h-full place-items-center t-95 text-text-3">برای چارت، نمادی انتخاب کن.</div>
    );
  }

  if (narrow) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <SnapshotStrip rows={rows} snapshot={snapshot.data} />
        <div className="flex min-h-0 flex-1">
          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            <BoardPanel selectedKey={activeSymbol} onSelect={selectRow} onActivate={selectRow} />
          </div>
          {activeSymbol ? (
            <div className="flex w-[340px] min-h-0 flex-none flex-col border-s border-line">
              <div className="flex flex-none gap-1 border-b border-line px-2 py-1" role="tablist">
                {([['symbol', 'نماد'], ['watch', 'دیده‌بان‌ها']] as const).map(([id, label]) => (
                  <button key={id} type="button" role="tab" aria-selected={tab === id}
                    data-testid={`narrow-tab-${id}`} onClick={() => setTab(id)} className="tape-btn">
                    {label}
                  </button>
                ))}
              </div>
              <div className="min-h-0 flex-1">
                {tab === 'symbol'
                  ? <SymbolPanel row={symbolRow} boardDay={boardDay} chartOpen={chartOpen} onToggleChart={() => setChartOpen(!chartOpen)} />
                  : <WatchPanel rows={rows} filterConfig={DEFAULT_TAPE_FILTER_CONFIG} onSelect={setActiveSymbol} />}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <SnapshotStrip rows={rows} snapshot={snapshot.data} />
      <div className="min-h-0 flex-1">
        <WorkspaceShell
          layout={layout}
          renderPanel={renderPanel}
          onClose={close}
          onSplit={split}
          onSwap={swap}
          onToggleFollow={toggleFollow}
          onRatio={setRatio}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: `toggleFollow` و نمادِ مستقل را به ذخیره‌گاه اضافه کن**

```ts
  toggleFollow: (tileId: string) => void;
  pinned: Record<string, string | null>;
```

```ts
      pinned: {},
      toggleFollow: (tileId) => {
        const ws = get().workspaces[0];
        const tile = findTile(ws.layout, tileId);
        if (!tile) return;
        const nextFollow = !tile.follow;
        const walk = (node: LayoutNode): LayoutNode => {
          if (node.kind === 'tile') {
            return node.id === tileId ? { ...node, follow: nextFollow } : node;
          }
          return { ...node, first: walk(node.first), second: walk(node.second) };
        };
        const pinned = { ...get().pinned };
        if (nextFollow) delete pinned[tileId];
        else pinned[tileId] = get().activeSymbol;
        set({
          pinned,
          workspaces: [{ ...ws, layout: walk(ws.layout), updatedAt: Date.now() }],
        });
      },
```

`findTile` را به ایمپورت‌های `store.ts` اضافه کن و `pinned` را هم به `partialize` ببر:

```ts
      partialize: (state) => ({
        version: state.version,
        activeWorkspaceId: state.activeWorkspaceId,
        activeSymbol: state.activeSymbol,
        pinned: state.pinned,
        workspaces: state.workspaces,
      }),
```

- [ ] **Step 6: سه فایلِ قدیمی را حذف کن و assertهایشان را منتقل کن**

- `WatchDock.tsx` حذف؛ assertهای `board-watch-symbol.spec.tsx` دربارهٔ داک به `WatchPanel` منتقل شوند.
- `StatusStrip.tsx` حذف؛ تست‌های `status-*` به کارت‌های `SnapshotStrip` منتقل شوند. حالت‌های `full/ribbon/minimal` حذف می‌شوند چون نوارِ کارت‌ها تنها نمایش است و تعدادِ کارت‌ها کنترلِ تراکم را می‌دهد.
- `QuickDrawer.tsx` حذف؛ محتوایش در `SymbolPanel` است.
- `statusMode` از `uiStore` حذف و هر ارجاعی در تست‌ها با assertهای تازه جایگزین می‌شود. هیچ تستی حذف نمی‌شود؛ فقط به ساختارِ تازه منتقل می‌شود.

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && grep -rn "WatchDock\|StatusStrip\|QuickDrawer\|statusMode" src`

هر ارجاعِ باقی‌مانده باید یا حذف شود یا به معادلِ تازه وصل شود. سپس:

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run && npx tsc -b`
Expected: همه PASS، صفر خطای تایپ

- [ ] **Step 7: کامیت**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/shared/lib/useMediaQuery.ts frontend-v2/src/features/market/routes/MarketPage.tsx frontend-v2/src/shared/workspace/store.ts frontend-v2/src/shared/stores/uiStore.ts frontend-v2/src/features/market/components frontend-v2/src/__tests__/market-workspace.spec.tsx
git add -u frontend-v2/src
git commit -m "$(cat <<'EOF'
feat(market): میزکارِ تایلی جای چیدمانِ ثابت را گرفت

تابلو، نماد، دیده‌بان‌ها و چارت کاشی‌اند؛ عرضِ کم به کشوی دوتبی برمی‌گردد
و چیدمانِ ذخیره‌شده دست نمی‌خورد.
EOF
)"
```

## Task 14: سایدبارِ گروه‌بندی‌شده و راهنمای میانبرها

**Files:**
- Create: `frontend-v2/src/app/shell/Sidebar.tsx`
- Create: `frontend-v2/src/app/shell/HelpBlock.tsx`
- Modify: `frontend-v2/src/app/shell/AppShell.tsx`
- Test: `frontend-v2/src/__tests__/sidebar.spec.tsx`

**Interfaces:**
- Consumes: `SHORTCUTS`, `useUiStore`
- Produces: `<Sidebar notificationCount={number} />`، `<HelpBlock collapsed={boolean} />`

- [ ] **Step 1: تستِ ناکام بنویس**

```tsx
// frontend-v2/src/__tests__/sidebar.spec.tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { Sidebar } from '@app/shell/Sidebar';
import { SHORTCUTS } from '@shared/workspace/shortcuts';
import { useUiStore } from '@shared/stores/uiStore';

beforeEach(() => {
  localStorage.clear();
  useUiStore.setState({ collapsed: false });
});

afterEach(cleanup);

function mount(count = 0) {
  return render(<MemoryRouter><Sidebar notificationCount={count} /></MemoryRouter>);
}

describe('Sidebar', () => {
  it('shows the prototype groups and labels', () => {
    mount();
    expect(screen.getByText('فضای تحلیل')).toBeTruthy();
    expect(screen.getByText('کشف فرصت')).toBeTruthy();
    expect(screen.getByText('سرمایه و اجرا')).toBeTruthy();
    expect(screen.getByText('فرصت‌ها')).toBeTruthy();
    expect(screen.getByText('وضعیت بازار')).toBeTruthy();
  });

  it('marks unbuilt destinations as next-stage', () => {
    mount();
    const technical = screen.getByText('تکنیکال').closest('[aria-disabled]');
    expect(technical?.getAttribute('title')).toContain('بعدی');
    expect(screen.getByRole('link', { name: /بازار/ })).toBeTruthy();
  });

  it('shows the unread badge', () => {
    mount(7);
    expect(screen.getByTestId('notif-badge').textContent).toBe('۷');
  });

  it('lists every shortcut in the help block', () => {
    mount();
    for (const shortcut of SHORTCUTS) {
      expect(screen.getByTestId('help-block').textContent).toContain(shortcut.keys);
    }
  });

  it('keeps help reachable when collapsed', () => {
    useUiStore.setState({ collapsed: true });
    mount();
    fireEvent.click(screen.getByTestId('help-toggle'));
    expect(screen.getByTestId('help-block')).toBeTruthy();
  });
});
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/sidebar.spec.tsx`
Expected: FAIL با `Failed to resolve import "@app/shell/Sidebar"`

- [ ] **Step 3: `HelpBlock` را بنویس**

```tsx
// frontend-v2/src/app/shell/HelpBlock.tsx
import { useState } from 'react';
import { SHORTCUTS } from '@shared/workspace/shortcuts';

export function HelpBlock({ collapsed }: { collapsed: boolean }) {
  const [open, setOpen] = useState(false);

  if (collapsed && !open) {
    return (
      <div className="border-t border-line p-1.5">
        <button type="button" data-testid="help-toggle" onClick={() => setOpen(true)}
          aria-label="راهنما"
          className="grid h-7 w-full place-items-center rounded-[var(--radius-sm)] t-10 text-text-3 hover:bg-panel-2 hover:text-text">
          ؟
        </button>
      </div>
    );
  }

  return (
    <div data-testid="help-block" className="border-t border-line p-2">
      <div className="mb-1 flex items-center justify-between t-9 font-bold text-text-3">
        <span>راهنما</span>
        {collapsed ? (
          <button type="button" onClick={() => setOpen(false)} aria-label="بستنِ راهنما" className="text-text-3">×</button>
        ) : null}
      </div>
      <ul className="space-y-0.5 t-9 text-text-3">
        {SHORTCUTS.map((shortcut) => (
          <li key={shortcut.id} className="flex items-baseline justify-between gap-2">
            <span className="truncate">{shortcut.label}</span>
            <kbd dir="ltr" className="num shrink-0 rounded-[var(--radius-xs)] border border-line px-1 text-text-2">
              {shortcut.keys}
            </kbd>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: `Sidebar` را بنویس**

```tsx
// frontend-v2/src/app/shell/Sidebar.tsx
import clsx from 'clsx';
import { NavLink } from 'react-router-dom';
import { toFaDigits } from '@shared/lib/fa';
import { useUiStore, type Theme } from '@shared/stores/uiStore';
import { Icon } from './icons';
import { HelpBlock } from './HelpBlock';

interface Item { path: string; label: string; icon: string; live?: boolean }
interface Group { title: string; items: Item[] }

const GROUPS: Group[] = [
  { title: 'فضای تحلیل', items: [
    { path: '/market', label: 'بازار', icon: 'grid', live: true },
    { path: '/technical', label: 'تکنیکال', icon: 'chart' },
    { path: '/fundamental', label: 'بنیادی', icon: 'file' },
    { path: '/market-status', label: 'وضعیت بازار', icon: 'pulse', live: true },
  ] },
  { title: 'کشف فرصت', items: [
    { path: '/opportunities', label: 'فرصت‌ها', icon: 'compass' },
    { path: '/fts-screen', label: 'غربالگری FTS', icon: 'funnel' },
  ] },
  { title: 'سرمایه و اجرا', items: [
    { path: '/watch', label: 'دیده‌بان', icon: 'eye' },
    { path: '/portfolio', label: 'پرتفوی', icon: 'pie' },
    { path: '/sarkhati', label: 'سرخطی', icon: 'bolt' },
  ] },
];

const THEMES: { key: Theme; label: string; dot: string }[] = [
  { key: 'brass', label: 'برنجی', dot: '#c9a45c' },
  { key: 'warm', label: 'روشنِ گرم', dot: '#efece4' },
  { key: 'terminal', label: 'ترمینال', dot: '#46e08a' },
  { key: 'cool', label: 'روشنِ سرد', dot: '#2f6f9f' },
];

export function Sidebar({ notificationCount = 0 }: { notificationCount?: number }) {
  const collapsed = useUiStore((s) => s.collapsed);
  const theme = useUiStore((s) => s.theme);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const setTheme = useUiStore((s) => s.setTheme);

  return (
    <aside className="flex w-[var(--rail-w)] shrink-0 flex-col border-s border-line bg-panel">
      <div className="flex h-[52px] items-center gap-2.5 border-b border-line px-3">
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-[var(--radius-sm)] text-accent-ink"
          style={{ background: 'var(--accent)' }} aria-hidden>
          <Icon name="bolt" size={15} />
        </span>
        {!collapsed ? (
          <div className="min-w-0 leading-tight">
            <div className="t-125 truncate font-extrabold">بورس‌ترمینال</div>
            <div className="t-9 tracking-[0.16em] text-text-3" dir="ltr">FTS DECISION DESK</div>
          </div>
        ) : null}
      </div>

      <nav className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto p-1.5" aria-label="ناوبری اصلی">
        {GROUPS.map((group) => (
          <div key={group.title} className="mb-1">
            {!collapsed ? <div className="px-2 pb-0.5 t-9 font-bold text-text-3">{group.title}</div> : null}
            {group.items.map((item) => (
              item.live ? (
                <NavLink key={item.path} to={item.path} title={item.label}
                  className={({ isActive }) => clsx(
                    'flex h-[30px] items-center gap-2 rounded-[var(--radius-sm)] px-2 t-11 whitespace-nowrap',
                    isActive ? 'bg-panel-3 text-text' : 'text-text-2 hover:bg-panel-2 hover:text-text',
                  )}>
                  <Icon name={item.icon} />
                  {!collapsed ? <span>{item.label}</span> : null}
                </NavLink>
              ) : (
                <span key={item.path} title={`${item.label} — در مرحلهٔ بعد`} aria-disabled
                  className="flex h-[30px] cursor-not-allowed items-center gap-2 rounded-[var(--radius-sm)] px-2 t-11 whitespace-nowrap text-text-3/70">
                  <Icon name={item.icon} />
                  {!collapsed ? <span>{item.label}</span> : null}
                </span>
              )
            ))}
          </div>
        ))}

        <NavLink to="/notifications" title="اعلان‌ها"
          className={({ isActive }) => clsx(
            'mt-auto flex h-[30px] items-center gap-2 rounded-[var(--radius-sm)] px-2 t-11 whitespace-nowrap',
            isActive ? 'bg-panel-3 text-text' : 'text-text-2 hover:bg-panel-2 hover:text-text',
          )}>
          <Icon name="bell" />
          {!collapsed ? <span>اعلان‌ها</span> : null}
          {notificationCount > 0 ? (
            <span data-testid="notif-badge"
              className="num ms-auto rounded-full bg-accent px-1.5 t-9 font-bold text-accent-ink">
              {toFaDigits(notificationCount)}
            </span>
          ) : null}
        </NavLink>
      </nav>

      <HelpBlock collapsed={collapsed} />

      <div className="border-t border-line p-2">
        {!collapsed ? <div className="t-9 mb-1.5 font-bold text-text-3">پوسته</div> : null}
        <div className={clsx('grid gap-1', collapsed ? 'grid-cols-1' : 'grid-cols-2')}>
          {THEMES.map((item) => (
            <button key={item.key} type="button" data-testid={`theme-${item.key}`}
              onClick={() => setTheme(item.key)} aria-pressed={theme === item.key} title={item.label}
              className={clsx('flex h-6 items-center gap-1.5 rounded-[var(--radius-sm)] px-1.5 t-95',
                theme === item.key ? 'bg-panel-3 text-text' : 'text-text-3 hover:bg-panel-2 hover:text-text')}>
              <span className="h-2.5 w-2.5 shrink-0 rounded-full border border-white/20"
                style={{ background: item.dot }} aria-hidden />
              {!collapsed ? <span className="truncate">{item.label}</span> : null}
            </button>
          ))}
        </div>
      </div>

      <div className="border-t border-line p-1.5">
        <button type="button" onClick={toggleSidebar}
          title={collapsed ? 'باز کردنِ نوار' : 'جمع کردنِ نوار'}
          className="flex h-7 w-full items-center justify-center gap-2 rounded-[var(--radius-sm)] t-10 text-text-3 hover:bg-panel-2 hover:text-text">
          <Icon name="menu" size={15} />
          {!collapsed ? <span>جمع کردن</span> : null}
        </button>
      </div>
    </aside>
  );
}
```

`Icon` و `PATHS` را از `AppShell.tsx` به `frontend-v2/src/app/shell/icons.tsx` منتقل کن و `funnel` را اضافه کن:

```ts
funnel: 'M3 5h18l-7 8v6l-4-2v-4z',
```

- [ ] **Step 5: `AppShell` را به `Sidebar` وصل کن**

```tsx
import { useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { useUiStore } from '@shared/stores/uiStore';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export function AppShell() {
  const collapsed = useUiStore((s) => s.collapsed);
  const theme = useUiStore((s) => s.theme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  return (
    <div data-rail={collapsed ? 'collapsed' : 'open'} className="flex h-full">
      <Sidebar notificationCount={0} />
      <main className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <Outlet />
      </main>
    </div>
  );
}
```

- [ ] **Step 6: تست را سبز کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/sidebar.spec.tsx && npx tsc -b`
Expected: PASS (۵ تست)

- [ ] **Step 7: کامیت**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/app/shell/Sidebar.tsx frontend-v2/src/app/shell/HelpBlock.tsx frontend-v2/src/app/shell/icons.tsx frontend-v2/src/app/shell/AppShell.tsx frontend-v2/src/__tests__/sidebar.spec.tsx
git commit -m "$(cat <<'EOF'
feat(shell): سایدبارِ گروه‌بندی‌شده با راهنمای میانبرها

نام و گروه‌ها از پروتوتایپ؛ راهنما از همان رجیستریِ میانبرها ساخته می‌شود.
EOF
)"
```

---

## Task 15: صفحهٔ وضعیت بازار

**Files:**
- Create: `frontend-v2/src/features/market/api/usePhase.ts`
- Create: `frontend-v2/src/features/market/routes/MarketStatusPage.tsx`
- Modify: `frontend-v2/src/app/App.tsx`
- Test: `frontend-v2/src/__tests__/market-status.spec.tsx`

**Interfaces:**
- Produces: `usePhase()`، `<MarketStatusPage />`، مسیر `/market-status`

- [ ] **Step 1: تستِ ناکام بنویس**

```tsx
// frontend-v2/src/__tests__/market-status.spec.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MarketStatusPage } from '@features/market/routes/MarketStatusPage';
import { usePhase } from '@features/market/api/usePhase';
import { useBoard } from '@features/market/api/useBoard';
import { useMarketSnapshot } from '@features/market/api/useMarketSnapshot';

vi.mock('@features/market/api/usePhase', () => ({ usePhase: vi.fn() }));
vi.mock('@features/market/api/useBoard', () => ({ useBoard: vi.fn() }));
vi.mock('@features/market/api/useMarketSnapshot', () => ({ useMarketSnapshot: vi.fn() }));

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MarketStatusPage />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe('MarketStatusPage', () => {
  it('labels an official phase differently from a calendar guess', () => {
    vi.mocked(usePhase).mockReturnValue({ data: { status: 'ok', phase: 'continuous', label: 'بازار باز', official: true, phase_source: 'tsetmc_marketState', is_live: true }, isLoading: false, isError: false } as never);
    vi.mocked(useBoard).mockReturnValue({ data: { meta: { d_even: 20261028, last_sync: '12:00' }, live_count: 5, fossil_count: 2 }, isLoading: false, isError: false } as never);
    vi.mocked(useMarketSnapshot).mockReturnValue({ data: undefined, isLoading: false, isError: false } as never);
    mount();
    expect(screen.getByTestId('phase-label').textContent).toBe('بازار باز');
    expect(screen.getByTestId('phase-source').textContent).toContain('رسمی');
  });

  it('says unknown instead of guessing when phase is missing', () => {
    vi.mocked(usePhase).mockReturnValue({ data: undefined, isLoading: false, isError: true } as never);
    vi.mocked(useBoard).mockReturnValue({ data: undefined, isLoading: false, isError: true } as never);
    vi.mocked(useMarketSnapshot).mockReturnValue({ data: undefined, isLoading: false, isError: false } as never);
    mount();
    expect(screen.getByTestId('phase-label').textContent).toContain('نامعلوم');
  });
});
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/market-status.spec.tsx`
Expected: FAIL با `Failed to resolve import`

- [ ] **Step 3: هوک و صفحه را بنویس**

```ts
// frontend-v2/src/features/market/api/usePhase.ts
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

export const PhaseSchema = z.looseObject({
  status: z.string(),
  phase: z.string().nullish(),
  label: z.string().nullish(),
  phase_source: z.string().nullish(),
  official: z.boolean().nullish(),
  is_live: z.boolean().nullish(),
  session_day: z.number().nullish(),
  verdict_allowed: z.boolean().nullish(),
});

export type Phase = z.infer<typeof PhaseSchema>;

export function usePhase() {
  return useQuery<Phase>({
    queryKey: ['market-phase'],
    queryFn: ({ signal }) => getJson('/api/mstat/phase', PhaseSchema, signal),
    refetchInterval: 30_000,
    staleTime: 10_000,
    refetchOnWindowFocus: false,
  });
}
```

```tsx
// frontend-v2/src/features/market/routes/MarketStatusPage.tsx
import { faNum, fmtInt, fmtMcap, toFaDigits } from '@shared/lib/fa';
import { useBoard } from '../api/useBoard';
import { useMarketSnapshot } from '../api/useMarketSnapshot';
import { usePhase } from '../api/usePhase';

function Row({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-line/60 py-1">
      <span className="t-95 text-text-3">{label}</span>
      <b className="num t-95 text-text-2" title={note}>{value}</b>
    </div>
  );
}

export function MarketStatusPage() {
  const phase = usePhase();
  const board = useBoard();
  const snapshot = useMarketSnapshot();
  const data = phase.data;

  const phaseLabel = data?.label ?? (phase.isError ? 'نامعلوم' : '—');
  const source = data?.official ? 'رسمی — از خودِ بورس' : 'تقویمی — رأیِ رسمی در دست نیست';
  const meta = board.data?.meta;

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-3">
      <h1 className="mb-2 t-125 font-extrabold">وضعیت بازار</h1>

      <section className="mb-3 rounded-[var(--radius-sm)] border border-line bg-panel p-2">
        <div className="flex items-baseline gap-2">
          <b data-testid="phase-label" className="t-115">{phaseLabel}</b>
          <span data-testid="phase-source" className="t-9 text-text-3">{source}</span>
        </div>
        <Row label="روزِ داده" value={meta?.d_even != null ? toFaDigits(String(meta.d_even)) : '—'} />
        <Row label="آخرین همگام‌سازی" value={meta?.last_sync ?? '—'} />
        <Row label="زنده / کهنه" value={`${fmtInt(board.data?.live_count)} / ${fmtInt(board.data?.fossil_count)}`} />
      </section>

      <section className="mb-3 rounded-[var(--radius-sm)] border border-line bg-panel p-2">
        <div className="mb-1 t-10 font-bold text-text-2">شاخص و ارزش</div>
        <Row label="شاخص کل" value={snapshot.data?.index?.last != null ? fmtInt(snapshot.data.index.last) : '—'} />
        <Row label="هم‌وزن" value={snapshot.data?.index?.ew_last != null ? fmtInt(snapshot.data.index.ew_last) : '—'} />
        <Row label="ارزش کل بازار" value={snapshot.data?.market?.trade_value_hemat != null ? `${fmtMcap(snapshot.data.market.trade_value_hemat)} همت` : '—'} />
        <Row label="تعداد معاملات" value={snapshot.data?.market?.trades != null ? fmtInt(snapshot.data.market.trades) : '—'} />
        <Row label="ارزش معاملات خرد"
          value={snapshot.data?.retail?.value_hemat != null ? `${fmtMcap(snapshot.data.retail.value_hemat)} همت` : '—'}
          note={snapshot.data?.retail?.basis ?? undefined} />
        <Row label="آستانهٔ مساعد / نامساعد"
          value={snapshot.data?.retail?.good_min != null
            ? `${faNum(snapshot.data.retail.good_min)} / ${faNum(snapshot.data.retail.bad_max ?? 0)} همت`
            : '—'} />
      </section>

      <p className="t-9 text-text-3">
        این صفحه فقط‌خواندنی است؛ عددِ کهنه با برچسبِ زنده نمایش داده نمی‌شود.
      </p>
    </div>
  );
}
```

در `App.tsx` مسیر را اضافه کن:

```tsx
<Route path="/market-status" element={<MarketStatusPage />} />
```

- [ ] **Step 4: تست را سبز کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/market-status.spec.tsx`
Expected: PASS (۲ تست)

- [ ] **Step 5: کامیت**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/features/market/api/usePhase.ts frontend-v2/src/features/market/routes/MarketStatusPage.tsx frontend-v2/src/app/App.tsx frontend-v2/src/__tests__/market-status.spec.tsx
git commit -m "$(cat <<'EOF'
feat(market): صفحهٔ وضعیت بازار با مرحلهٔ رسمی و تازگیِ داده

مرحلهٔ تقویمی از رسمی جدا نوشته می‌شود و عددِ کهنه زنده خوانده نمی‌شود.
EOF
)"
```

---

## Task 16: مرکزِ اعلان‌های واقعی

**Files:**
- Create: `frontend-v2/src/features/notifications/api/useNotifications.ts`
- Create: `frontend-v2/src/features/notifications/lib/unread.ts`
- Create: `frontend-v2/src/features/notifications/ui/NotificationsPage.tsx`
- Modify: `frontend-v2/src/app/App.tsx`
- Modify: `frontend-v2/src/app/shell/AppShell.tsx` (نشانِ تعداد)
- Test: `frontend-v2/src/__tests__/notifications.spec.tsx`

**Interfaces:**
- Produces:
  - `useNotificationsFeed()` و `useNotificationSources()`
  - `unreadCount(items, readIds) -> number`
  - `LEVEL_LABEL`, `LEVEL_ORDER`
  - `<NotificationsPage />` و مسیر `/notifications`

- [ ] **Step 1: تستِ ناکام بنویس**

```tsx
// frontend-v2/src/__tests__/notifications.spec.tsx
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LEVEL_LABEL, unreadCount } from '@features/notifications/lib/unread';
import { NotificationsPage } from '@features/notifications/ui/NotificationsPage';
import { useNotificationSources, useNotificationsFeed } from '@features/notifications/api/useNotifications';

vi.mock('@features/notifications/api/useNotifications', () => ({
  useNotificationsFeed: vi.fn(),
  useNotificationSources: vi.fn(),
}));

const items = [
  { id: '1', level: 'high', title: 'صورت مالی', symbol: 'الف', publish_date: '1405/08/06', kind: 'statements' },
  { id: '2', level: 'medium', title: 'مجمع', symbol: 'ب', publish_date: '1405/08/06', kind: 'assembly' },
  { id: '3', level: 'low', title: 'یادآوری', symbol: null, publish_date: '1405/08/05', kind: 'other' },
  { id: '4', level: 'unclassified', title: 'ناشناخته', symbol: null, publish_date: null, kind: 'other' },
];

afterEach(cleanup);

describe('notifications', () => {
  it('counts unread high and medium only', () => {
    expect(unreadCount(items as never, new Set())).toBe(2);
    expect(unreadCount(items as never, new Set(['1']))).toBe(1);
  });

  it('uses the backend level vocabulary', () => {
    expect(LEVEL_LABEL.high).toBe('بالا');
    expect(LEVEL_LABEL.unclassified).toBe('بی‌طبقه');
  });

  it('distinguishes an empty feed from an unreachable source', () => {
    vi.mocked(useNotificationsFeed).mockReturnValue({ data: { status: 'ok', items: [] }, isLoading: false, isError: false } as never);
    vi.mocked(useNotificationSources).mockReturnValue({ data: { status: 'ok', sources: [{ source: 'codal', state: 'ok', rows: 10 }] }, isLoading: false, isError: false } as never);
    render(<NotificationsPage />);
    expect(screen.getByTestId('notif-empty').textContent).toContain('تازه‌ای نیست');

    cleanup();
    vi.mocked(useNotificationSources).mockReturnValue({ data: { status: 'ok', sources: [{ source: 'codal', state: 'unavailable', rows: 0, message: 'جدول نیست' }] }, isLoading: false, isError: false } as never);
    render(<NotificationsPage />);
    expect(screen.getByTestId('notif-source-warning').textContent).toContain('در دسترس نیست');
  });

  it('filters by level', () => {
    vi.mocked(useNotificationsFeed).mockImplementation(((level?: string) => ({
      data: { status: 'ok', items: level ? items.filter((item) => item.level === level) : items },
      isLoading: false,
      isError: false,
    })) as never);
    vi.mocked(useNotificationSources).mockReturnValue({ data: { status: 'ok', sources: [{ source: 'codal', state: 'ok', rows: 10 }] }, isLoading: false, isError: false } as never);
    render(<NotificationsPage />);
    expect(screen.getAllByTestId(/^notif-item-/)).toHaveLength(4);
    fireEvent.click(screen.getByTestId('notif-level-high'));
    expect(screen.getAllByTestId(/^notif-item-/)).toHaveLength(1);
  });
});
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/notifications.spec.tsx`
Expected: FAIL با `Failed to resolve import`

- [ ] **Step 3: لایهٔ خالص و هوک‌ها را بنویس**

```ts
// frontend-v2/src/features/notifications/lib/unread.ts
export type Level = 'high' | 'medium' | 'low' | 'unclassified';

export const LEVEL_LABEL: Record<Level, string> = {
  high: 'بالا',
  medium: 'متوسط',
  low: 'پایین',
  unclassified: 'بی‌طبقه',
};

export const LEVEL_ORDER: Level[] = ['high', 'medium', 'low', 'unclassified'];

export interface Notice {
  id: string | null;
  level: Level;
  title: string;
  symbol?: string | null;
  company?: string | null;
  publish_date?: string | null;
  url?: string | null;
  kind?: string | null;
  occurrences?: number;
}

export function unreadCount(items: readonly Notice[], readIds: ReadonlySet<string>): number {
  let count = 0;
  for (const item of items) {
    if (item.level !== 'high' && item.level !== 'medium') continue;
    if (item.id && readIds.has(item.id)) continue;
    count += 1;
  }
  return count;
}

const KEY = 'bors-notif-read-v1';

export function readState(): Set<string> {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]');
    const list = Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : [];
    return new Set<string>(list);
  } catch {
    return new Set();
  }
}

export function markRead(id: string): void {
  const next = readState();
  next.add(id);
  localStorage.setItem(KEY, JSON.stringify([...next]));
}
```

```ts
// frontend-v2/src/features/notifications/api/useNotifications.ts
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const NoticeSchema = z.looseObject({
  id: z.string().nullish(),
  level: z.enum(['high', 'medium', 'low', 'unclassified']),
  title: z.string(),
  symbol: z.string().nullish(),
  company: z.string().nullish(),
  publish_date: z.string().nullish(),
  url: z.string().nullish(),
  kind: z.string().nullish(),
  occurrences: z.number().nullish(),
});

export const FeedSchema = z.looseObject({
  status: z.literal('ok'),
  items: z.array(NoticeSchema),
});

export const SourcesSchema = z.looseObject({
  status: z.literal('ok'),
  sources: z.array(z.looseObject({
    source: z.string(),
    label: z.string().nullish(),
    rows: z.number().nullish(),
    state: z.string(),
    message: z.string().nullish(),
    newest_publish: z.string().nullish(),
    last_fetch: z.string().nullish(),
  })),
});

export function useNotificationsFeed(level?: string) {
  const suffix = level ? `?levels=${encodeURIComponent(level)}` : '';
  return useQuery({
    queryKey: ['notifications', level ?? 'all'],
    queryFn: ({ signal }) => getJson(`/api/notifications/feed${suffix}`, FeedSchema, signal),
    refetchInterval: 60_000,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}

export function useNotificationSources() {
  return useQuery({
    queryKey: ['notification-sources'],
    queryFn: ({ signal }) => getJson('/api/notifications/sources', SourcesSchema, signal),
    refetchInterval: 60_000,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}
```

- [ ] **Step 4: صفحه را بنویس**

```tsx
// frontend-v2/src/features/notifications/ui/NotificationsPage.tsx
import { useMemo, useState } from 'react';
import clsx from 'clsx';
import { toFaDigits } from '@shared/lib/fa';
import { useNotificationSources, useNotificationsFeed } from '../api/useNotifications';
import { LEVEL_LABEL, LEVEL_ORDER, markRead, readState, type Level } from '../lib/unread';

const TONE: Record<Level, string> = {
  high: 'text-down',
  medium: 'text-warn',
  low: 'text-text-3',
  unclassified: 'text-text-3',
};

export function NotificationsPage() {
  const [level, setLevel] = useState<Level | 'all'>('all');
  const feed = useNotificationsFeed(level === 'all' ? undefined : level);
  const sources = useNotificationSources();
  const [read, setRead] = useState<Set<string>>(() => readState());

  const source = sources.data?.sources?.[0];
  const items = feed.data?.items ?? [];
  const unavailable = source?.state === 'unavailable' || sources.isError;

  const title = useMemo(() => {
    if (unavailable) return 'منبعِ اعلان در دسترس نیست';
    return null;
  }, [unavailable]);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-3">
      <h1 className="mb-2 t-125 font-extrabold">اعلان‌ها</h1>

      {title ? (
        <div data-testid="notif-source-warning" className="mb-2 rounded-[var(--radius-sm)] border border-line bg-panel p-2 t-95 text-warn">
          {title} — {source?.message ?? 'دلیل اعلام نشده'}
        </div>
      ) : null}

      <div className="mb-2 flex items-center gap-1" role="tablist">
        <button type="button" data-testid="notif-level-all" onClick={() => setLevel('all')}
          className={clsx('tape-btn', level === 'all' && 'bg-panel-3 text-text')}>همه</button>
        {LEVEL_ORDER.map((item) => (
          <button key={item} type="button" data-testid={`notif-level-${item}`} onClick={() => setLevel(item)}
            className={clsx('tape-btn', level === item && 'bg-panel-3 text-text')}>
            {LEVEL_LABEL[item]}
          </button>
        ))}
      </div>

      {feed.isLoading ? <p className="t-95 text-text-3">در حالِ خواندن…</p> : null}

      {!feed.isLoading && items.length === 0 && !unavailable ? (
        <p data-testid="notif-empty" className="t-95 text-text-3">اعلانِ تازه‌ای نیست.</p>
      ) : null}

      <ul className="space-y-1">
        {items.map((item, index) => {
          const id = item.id ?? `row-${index}`;
          const isRead = item.id ? read.has(item.id) : false;
          return (
            <li key={id} data-testid={`notif-item-${id}`}
              className={clsx('rounded-[var(--radius-sm)] border border-line bg-panel p-2',
                isRead && 'opacity-60')}>
              <div className="flex items-baseline gap-2">
                <span className={clsx('t-9 font-bold', TONE[item.level])}>{LEVEL_LABEL[item.level]}</span>
                <b className="min-w-0 truncate t-10">{item.title}</b>
                {item.symbol ? <span className="t-9 text-text-3">{item.symbol}</span> : null}
                <span className="num ms-auto t-9 text-text-3">{item.publish_date ?? '—'}</span>
              </div>
              <div className="mt-1 flex items-center gap-2 t-9 text-text-3">
                <span>{item.company ?? '—'}</span>
                {item.occurrences && item.occurrences > 1 ? <span>· {toFaDigits(item.occurrences)} بار</span> : null}
                {item.url ? (
                  <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-accent">کدال</a>
                ) : null}
                {item.id ? (
                  <button type="button" className="ms-auto text-text-3 hover:text-text"
                    onClick={() => { markRead(item.id!); setRead(readState()); }}>
                    خوانده شد
                  </button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
```

- [ ] **Step 5: مسیر و نشان را وصل کن**

در `App.tsx`:

```tsx
<Route path="/notifications" element={<NotificationsPage />} />
```

در `AppShell.tsx` نشانِ واقعی را بده:

```tsx
import { useNotificationsFeed } from '@features/notifications/api/useNotifications';
import { readState, unreadCount } from '@features/notifications/lib/unread';

const feed = useNotificationsFeed();
const badge = unreadCount(feed.data?.items ?? [], readState());
...
<Sidebar notificationCount={badge} />
```

`AppShell` در لایهٔ `app` می‌تواند از `@features` بخواند؛ اگر مرزِ `boundaries` اجازه نداد، نشان را به یک `NotificationsBadge` در `app/shell` با همان هوک منتقل کن.

- [ ] **Step 6: تست را سبز کن**

Run: `cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run src/__tests__/notifications.spec.tsx && npx tsc -b`
Expected: PASS (۴ تست)

- [ ] **Step 7: کامیت**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add frontend-v2/src/features/notifications frontend-v2/src/app/App.tsx frontend-v2/src/app/shell/AppShell.tsx frontend-v2/src/__tests__/notifications.spec.tsx
git commit -m "$(cat <<'EOF'
feat(notifications): مرکزِ اعلان از خوراکِ واقعیِ کدال

سطوح از خودِ بک‌اند می‌آیند، «چیزی نیست» از «نرسیده» جدا است و خوانده‌شده
در همین دستگاه می‌ماند.
EOF
)"
```

---

## Task 17: سنجشِ زنده و شواهد

**Files:**
- Modify: `_audit/live-board-v2-20261028/live-check.mjs` (افزودنِ بررسی‌های میزکار)
- Create: `_audit/live-board-v2-20261028/workspace-check.json` (خروجیِ اجرا)

**Interfaces:**
- Consumes: بک‌اندِ آرشیویِ آفلاین روی `8101`، Vite روی `5180`

- [ ] **Step 1: بک‌اندِ سنجش را جدا بالا بیاور**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
BORS_NO_FETCH_LOOPS=1 BORS_CODAL_OFFLINE=1 BORS_CODAL_AUTO=0 \
  python -m uvicorn app:app --host 127.0.0.1 --port 8101 --log-level warning
```

اگر پورتِ `8101` در اختیارِ اجرایِ دیگری بود، آن را نکُش؛ نسخهٔ آزمون را روی پورتِ دیگر بگذار و `BORS_BACKEND` را همان کن. هیچ نوشتنی روی `market.db` عملیاتی مجاز نیست.

- [ ] **Step 2: بیلدِ تازه بساز و Vite را بالا بیاور**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npm run build
cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npm run dev
```

- [ ] **Step 3: بررسی‌های تازه را به هارنس اضافه کن**

به `live-check.mjs` این موارد را اضافه کن (هر مورد با `page.locator` و assert):

1. `snapshot-strip` با چهار کارت دیده شود.
2. hover روی `card-tedpix` → `preview-tedpix` شامل «تعداد معاملات» و برچسب «کل بازار».
3. کارتِ `card-retailValue` عدد یا `—` بدهد، هرگز `۰`.
4. کلیک روی `tile-header-t-symbol` سپس `ArrowDown` → پنلِ نماد با پنلِ دیده‌بان‌ها جابه‌جا شود.
5. `tile-close-t-watch` پنل را ببندد و `Ctrl+Z` برگرداند.
6. `Alt+2` فوکوس را به پنلِ دوم ببرد.
7. کشیدنِ مرز تغییرِ اندازه بدهد و پس از reload همان نسبت بماند.
8. `symbol-tab-history` تاریخچه را باز کند؛ `symbol-chart-toggle` چارت را ببندد/باز کند.
9. `watch-tab-industries` صنایع را نشان دهد.
10. در عرضِ `1279` کشوی دوتبی دیده شود و پنل‌های تایلی نباشند؛ پس از بازگشت به عرضِ بزرگ، چیدمانِ ذخیره‌شده برگردد.
11. `/market-status` مرحله و منبع را نشان دهد.
12. `/notifications` حالتِ خالی یا خوراکِ واقعی را نشان دهد.
13. کنسول بدونِ خطا و بدونِ درخواستِ اضافه در hover.

- [ ] **Step 4: در سه اندازه اجرا کن**

```bash
MSYS_NO_PATHCONV=1 node _audit/live-board-v2-20261028/live-check.mjs
```

Expected: خروجیِ JSON با `failures: []` در `1366×768`، `1920×1080` و `2560×1440`؛ اسکرین‌شات‌های `workspace-1366.png`, `workspace-1920.png`, `workspace-2560.png`, `workspace-narrow.png`, `workspace-preview.png`.

- [ ] **Step 5: دروازهٔ نهایی**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal/frontend-v2 && npx vitest run && npx tsc -b && npm run build
cd /c/Users/PCMOD/Desktop/BorsTerminal && PYTHONIOENCODING=utf-8 python dev/test_market_index_series.py
python dev/persian_glyph_guard.py
```

Expected: همه سبز. عددهای تست را در گزارش بیاور، نه صفت.

- [ ] **Step 6: گزارش به مالک**

فقط اسکرین‌شات‌ها، اعدادِ تست، اندازهٔ چانکِ چارت، و هر چیزی که راستی‌آزمایی نشده. PASS بصری اعلام نمی‌شود.

- [ ] **Step 7: کامیتِ شواهد**

```bash
cd /c/Users/PCMOD/Desktop/BorsTerminal
git add _audit/live-board-v2-20261028/live-check.mjs _audit/live-board-v2-20261028/workspace-check.json
git commit -m "$(cat <<'EOF'
test(migration): سنجشِ زندهٔ میزکار چندپنلی

سیزده بررسی در سه اندازه؛ شواهد در JSON می‌ماند و حکمِ بصری با مالک است.
EOF
)"
```

---

## خودبازبینیِ نقشه

- پوششِ سند: چیدمان (۲–۴)، کارت‌ها (۷–۹)، snapshot (۱)، نماد/چارت (۱۰، ۱۲)، دیده‌بان‌ها (۱۱)، سایدبار و وضعیت (۱۴، ۱۵)، اعلان‌ها (۱۶)، P/E (۶)، کیبورد و راهنما (۵، ۱۴)، عرضِ کم (۱۳)، پذیرش (۱۷).
- نام‌ها یکدست‌اند: `LayoutNode`/`TilePanel`/`MoveDir`، `useWorkspace`، `CARD_REGISTRY`، `parseSnapshot`، `unreadCount`.
- هیچ `TBD` یا «مشابهِ تسکِ قبل» در نقشه نیست؛ هر تسک کد و تستِ خودش را دارد.




---

## Task 18: سایدبارِ نماد — انتخابِ چارت و پنج کارت بنیادی (دستورِ مالک، ۱۴۰۵-۰۸-۰۶)

**دستورِ مالک، عیناً:** «توی سایدبار سمت‌چپ وقتی رو نماد می‌زنی هم چارت بتونه نشون داده بشه و بره یعنی کولپس بشه، هم ۵ تا کارت بنیادی همین‌طور تو یه جای جدا» + «توی سایدبار چپ انتخابشون اونجا باشه».

**Files:**
- Create: `frontend-v2/src/app/shell/SidebarSymbol.tsx`
- Create: `frontend-v2/src/features/fundamental/api/useFtsCard.ts`
- Create: `frontend-v2/src/features/fundamental/ui/FundamentalCards.tsx`
- Modify: `frontend-v2/src/features/chart/ui/ChartPanel.tsx` (میزبانِ سوم: `compact`)
- Modify: `frontend-v2/src/app/shell/Sidebar.tsx` (جای‌گذاریِ بخشِ نماد بینِ ناوبری و بلوکِ راهنما)
- Test: `frontend-v2/src/__tests__/sidebar-symbol.spec.tsx`

**Interfaces:**
- Consumes: `useWorkspace().activeSymbol`, `useChart(symbol)`, `useFtsCard(symbol)`, `CARD_REGISTRY` نیست (این پنج کارت بنیادی جدا از کارت‌های snapshot اند).
- Produces:
  - `useFtsCard(symbol)` → `{ status, symbol, passes, indicators, profile }` از `GET /api/fundamental/{symbol}` (پاسخِ canonical؛ هیچ محاسبهٔ دومی در فرانت).
  - `<FundamentalCards symbol />` — پنج کارتِ محورِ ۱ تا ۵ با مقدار، حکمِ سه‌حالته و یک خط علت.
  - `<SidebarSymbol />` — سرِ نماد + دو کلیدِ انتخابِ «چارت» و «بنیادی» + بدنهٔ تاشو.

**رفتار:**
- بخش فقط وقتی `activeSymbol` هست دیده می‌شود؛ در حالتِ جمع‌شدهٔ سایدبار فقط آیکنِ نماد می‌ماند.
- دو کلیدِ «چارت» و «بنیادی» همان «انتخاب»اند: هر کدام بلوکِ خودش را باز/بسته می‌کند (`aria-expanded`)، پیش‌فرض هر دو باز؛ وضعیت در localStorageِ همین بخش (`bors-sidebar-symbol-v1`) می‌ماند، نه در layout.
- چارت در سایدبار با همان `ChartPanel` و همان `useChart` رندر می‌شود (`compact`، فقط کندلِ روزانه)؛ دکمهٔ «باز کردن در کاشی» کاشیِ چارت را باز می‌کند.
- پنج کارت: محورهای ۱ رشد ریالی، ۲ روند EPS، ۳ حاشیهٔ ناخالص، ۴ فروش÷ارزش بازار، ۵ صنعت/نرخ‌گذاری — همان ترتیبِ جزوه، مقدار از پاسخِ سرور، حکم `pass === null` ⇒ `—` با علتِ `gap`؛ هیچ صفر یا قرمزِ ساختگی.
- شکستِ `/api/fundamental/{symbol}` یا نبودِ داده ⇒ پیامِ صادق «بنیادیِ این نماد در دسترس نیست» زیرِ همان کلید؛ چارت و جدول سالم می‌مانند.

**Steps:**
- [ ] تستِ ناکام: سایدبار بدونِ نماد بخش را نشان نمی‌دهد؛ با نماد، سرِ نماد و دو کلید را نشان می‌دهد؛ کلیکِ «چارت» `aria-expanded` را برمی‌گرداند و بدنه را برمی‌دارد؛ پنج کارت با fixture رندر می‌شوند و `pass: null` عددِ `—` می‌گیرد؛ خطای API پیامِ صادق می‌دهد.
- [ ] `useFtsCard` با zod: `passes` ناشناخته‌کلید، `indicators` فقط فیلدهای لازم؛ پاکتِ خطا رد می‌شود.
- [ ] `FundamentalCards` با `qualityFrom` سه‌حالته و برچسب‌های فارسیِ جزوه.
- [ ] `SidebarSymbol` و جای‌گذاری در `Sidebar`.
- [ ] `ChartPanel` میزبانِ `compact`.
- [ ] کلِ مجموعه سبز + `tsc -b`؛ کامیت فقط همین فایل‌ها.

