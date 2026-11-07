# Workspace 2.0 + Pattern Spotlight 3D + Kronos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking. Each task is owned by one subagent; do not edit files outside your task's ownership.

**Goal:** Ship E1 (modes + 4-pane docking + saved layouts), E2 (p12-faithful 3D spotlight for all tier-1 patterns + p19/p21 ports), and the Kronos CPU benchmark without regressing the Phase C/D gates.

**Architecture:** E1 extends the existing shared split-tree into a technical layout store with three mode presets and a panel registry. E2 introduces a pure `SpotlightModel` adapter over `DoubleTapPattern` and `ChartPattern`, a p12-faithful SVG spotlight layer, and extends the unified event engine with p19/p21. Kronos runs as an isolated Python benchmark; its F integration follows only after real inference is proven.

**Tech Stack:** React 18 + TypeScript + Vite + Zustand + klinecharts + Vitest + CSS/SVG; Python for Kronos.

**Spec:** `docs/superpowers/specs/2026-11-06-workspace2-telegram-pattern-spotlight-kronos-design.md`

## Global Constraints

- Adjusted functional series only for chart calculations; other adjustment modes require an explicit label.
- Phase D gate must stay green: 39/39 tier-1, zero fake, 15×2 audit.
- No parallel engine: p19/p21 live inside `patterns/` and `events/`; no duplicate overlay logic.
- All thresholds live in `PATTERN_CONFIG` / `EVENT_CONFIG`.
- unslop: 12px text floor, 4px grid, one UI accent, no glow/halo/infinite pulse; p12 saturated colors only in the chart pattern layer, no glow filter.
- No WebGL/3D engine; 3D is SVG extrusion/offset/shadow.
- Persian RTL UI, `toFaDigits`, `prefers-reduced-motion`.
- Never port MT4/MT5 binaries; text source + attribution only.
- Evidence at 1366×768 and 1920×1080, reduced-motion, live interaction.
- **Do not commit or push; the owner has not authorized commits.**

---

## Track A — E1 Workspace 2.0

### Task A1: Genericize the split-tree and add a 4-tile technical limit

**Files:**
- Modify: `frontend-v2/src/shared/workspace/types.ts`
- Modify: `frontend-v2/src/shared/workspace/layout.ts`
- Modify: `frontend-v2/src/shared/workspace/store.ts` (market close call uses the new protected-panel arg)
- Test: `frontend-v2/src/__tests__/workspace-layout.test.ts`

**Interfaces:**
- Produces: `export interface LayoutLimits { maxDepth: number; maxTiles: number }`
- Produces: `export const MARKET_LIMITS: LayoutLimits = { maxDepth: 3, maxTiles: 2 }`
- Produces: `export const TECHNICAL_LIMITS: LayoutLimits = { maxDepth: 4, maxTiles: 4 }`
- Genericizes `LayoutNode<P extends string = TilePanel>`, `panelsInOrder<P>`, `findTile<P>`, `depthOf<P>`, `swapWithNeighbor<P>`.
- New signatures: `splitTile<P>(root, tileId, dir, newPanel: P, limits: LayoutLimits = MARKET_LIMITS, makeId?)` and `closeTile<P>(root, tileId, protectedPanel?: P)`.
- Market store passes `'board'` to `closeTile`; market behavior/key unchanged.

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from 'vitest';
import { panelsInOrder, splitTile } from '../shared/workspace/layout';
import { TECHNICAL_LIMITS, type LayoutNode } from '../shared/workspace/types';

type TP = 'chart' | 'inspector' | 'feed' | 'scanner' | 'fundamental';
const leaf = (id: string, panel: TP): LayoutNode<TP> => ({ kind: 'tile', id, panel, follow: false });

describe('layout limits', () => {
  it('allows four technical panes and rejects a fifth', () => {
    let root = leaf('t-chart', 'chart');
    root = splitTile(root, 't-chart', 'row', 'inspector', TECHNICAL_LIMITS)!;
    root = splitTile(root, 't-chart', 'col', 'feed', TECHNICAL_LIMITS)!;
    root = splitTile(root, 't-chart', 'col', 'scanner', TECHNICAL_LIMITS)!;
    expect(panelsInOrder(root)).toHaveLength(4);
    expect(splitTile(root, 't-chart', 'col', 'fundamental', TECHNICAL_LIMITS)).toBeNull();
  });
});
```

- [ ] **Step 2: Run it and confirm it fails** — `cd frontend-v2 && npx vitest run src/__tests__/workspace-layout.test.ts` → fails on the generic limit arg.
- [ ] **Step 3: Implement** — genericize the types/functions, add `MARKET_LIMITS`/`TECHNICAL_LIMITS`, thread the optional limits, make `closeTile` take an optional protected panel, and update the market store's `close` call with `'board'`. Keep `bors-workspace-v1` and two-tile market behavior.
- [ ] **Step 4: Run the new test and all market workspace tests** — `npx vitest run src/__tests__/workspace-layout.test.ts src/__tests__/workspace-store.test.ts src/__tests__/workspace-shell.test.ts src/__tests__/workspace-keyboard.test.ts`.
- [ ] **Step 5: Type-check** — `npx tsc -b` (or `npm run typecheck`). Do not commit.

### Task A2: Technical layout store with modes and named layouts

**Files:**
- Create: `frontend-v2/src/features/technical/workspace/technicalWorkspaceStore.ts`
- Create: `frontend-v2/src/features/technical/workspace/presets.ts`
- Test: `frontend-v2/src/features/technical/workspace/__tests__/technicalWorkspaceStore.test.ts`

**Interfaces:**
- Produces: `type WorkspaceMode = 'analysis' | 'scan' | 'research'`
- Produces: `interface NamedLayout { id: string; name: string; mode: WorkspaceMode; root: LayoutNode; panelKinds: Record<string, TechnicalPanelKind> }`
- Produces: store fields `{ mode, layouts: Record<WorkspaceMode, NamedLayout[]>, activeLayoutId, setMode, saveLayout, loadLayout, undo, redo }`
- Persist key: `bors-technical-workspace-v2`; do not touch `bors-workspace-v1`.
- Presets: analysis = chart + inspector + feed (chart ≥60% at 1366); scan = scanner + chart + feed (chart ≥55%); research = chart + fundamental + feed + inspector (chart ≥50%). Every preset has a stable layout id.

- [ ] **Step 1: Write the failing test**

```ts
import { beforeEach, describe, expect, it } from 'vitest';
import { useTechnicalWorkspaceStore } from '../technicalWorkspaceStore';

describe('technical workspace store', () => {
  beforeEach(() => useTechnicalWorkspaceStore.getState().reset());

  it('seeds three modes and restores a saved layout', () => {
    const s = useTechnicalWorkspaceStore.getState();
    expect(s.layouts.analysis.length).toBeGreaterThan(0);
    expect(s.layouts.scan.length).toBeGreaterThan(0);
    expect(s.layouts.research.length).toBeGreaterThan(0);
    const before = s.layouts.analysis[0]!.root;
    s.setMode('scan');
    s.setMode('analysis');
    s.saveLayout('My analysis');
    expect(useTechnicalWorkspaceStore.getState().layouts.analysis.some((l) => l.name === 'My analysis')).toBe(true);
    s.loadLayout(useTechnicalWorkspaceStore.getState().layouts.analysis[0]!.id);
    expect(useTechnicalWorkspaceStore.getState().layouts.analysis[0]!.root).toEqual(before);
  });
});
```

- [ ] **Step 2: Run it and confirm it fails** — `npx vitest run src/features/technical/workspace/__tests__/technicalWorkspaceStore.test.ts`.
- [ ] **Step 3: Implement** — Zustand + `persist`, immutable layout ops reusing Task A1, undo/redo stack per mode; no component imports in the store.
- [ ] **Step 4: Run the test + `npx tsc -b`**. Do not commit.

### Task A3: Panel registry and panel host

**Files:**
- Create: `frontend-v2/src/features/technical/workspace/panelRegistry.tsx`
- Create: `frontend-v2/src/features/technical/workspace/WorkspacePanelHost.tsx`
- Create: `frontend-v2/src/features/technical/workspace/WorkspaceChartPane.tsx`
- Test: `frontend-v2/src/features/technical/workspace/__tests__/panelRegistry.test.tsx`

**Interfaces:**
- Produces: `type TechnicalPanelKind = 'chart' | 'inspector' | 'feed' | 'scanner' | 'fundamental' | 'indicators'`
- Produces: `PANEL_REGISTRY: Record<TechnicalPanelKind, React.ComponentType>`; chart renders `WorkspaceChartPane` (which imports `KLineChartWrapper` and must not modify it).
- `fundamental` reuses `FundamentalSummary` with the current symbol; if its props require a different shape, wrap it in `WorkspaceFundamentalPane` instead of editing the fundamental feature.
- `scanner` reuses `Top50Panel`.
- Produces: `WorkspacePanelHost({ kind })` with a stable `data-testid="panel-<kind>"`.

- [ ] **Step 1: Write the failing test** — render `WorkspacePanelHost` for `inspector`, `feed`, `scanner`; assert the testids and that the chart pane contains `KLineChartWrapper`'s testid.
- [ ] **Step 2: Run it → fail** — `npx vitest run src/features/technical/workspace/__tests__/panelRegistry.test.tsx`.
- [ ] **Step 3: Implement** the registry/host/chart pane; no edits to `KLineChartWrapper.tsx`.
- [ ] **Step 4: Run the test + `npx tsc -b`**. Do not commit.

### Task A4: WorkspaceShell redesign with mode presets, docking and command palette

**Files:**
- Modify: `frontend-v2/src/features/technical/ui/workspace/WorkspaceShell.tsx`
- Modify: `frontend-v2/src/features/technical/ui/workspace/WorkspaceTopbar.tsx` (mode switcher + Ctrl+K button)
- Create: `frontend-v2/src/features/technical/ui/workspace/CommandPalette.tsx`
- Test: `frontend-v2/src/features/technical/ui/workspace/__tests__/WorkspaceShellModes.test.tsx`
- Test: `frontend-v2/src/features/technical/ui/workspace/__tests__/WorkspaceVisual.test.tsx` (extend)

**Interfaces:**
- Consumes Task A2 store and Task A3 registry.
- Renders the split tree recursively; each leaf is a `WorkspacePanelHost`; splitters resize; drag/swap/close per shared layout actions.
- `Ctrl+K` opens the palette with actions: symbol search, mode change, layout save/load, panel toggle.
- Do not edit `KLineChartWrapper.tsx`, `InspectorRail.tsx`, `EventFeed.tsx` internals; use the existing components.

- [ ] **Step 1: Write the failing test** — switch to scan/research and assert the mode label + the expected panel testids; press Ctrl+K and assert the palette; assert every visible text node is ≥12px (reuse the existing visual helper).
- [ ] **Step 2: Run → fail**.
- [ ] **Step 3: Implement** — keep the existing topbar/activity bar actions; add modes and palette; use CSS Grid only for the outer shell, split-tree inside.
- [ ] **Step 4: Run** `npx vitest run src/features/technical/ui/workspace/__tests__` + `npx tsc -b` + `npm run build`. Do not commit.

### Task A5: Save/restore UI and keyboard shortcuts

**Files:**
- Create: `frontend-v2/src/features/technical/ui/workspace/LayoutMenu.tsx`
- Modify: `WorkspaceTopbar.tsx` (mount LayoutMenu)
- Test: `frontend-v2/src/features/technical/ui/workspace/__tests__/LayoutMenu.test.tsx`

- [ ] **Step 1: Failing test** — save a named layout, switch mode, restore it, assert panel composition; undo/redo restores the previous root.
- [ ] **Step 2: Run → fail**.
- [ ] **Step 3: Implement** the menu + shortcuts (`Ctrl+Z` undo, `Ctrl+Shift+Z` redo); no new dependencies.
- [ ] **Step 4: Run the test + full workspace suite**. Do not commit.

### Task A6: Live E1 evidence (main agent)

- [ ] Start/verify Vite + backend; open the technical workspace at 1366×768 and 1920×1080.
- [ ] Switch all three modes, resize/split to 4 panes, save and restore a named layout, reload and verify persistence.
- [ ] Capture screenshots to `_audit/rebuild/workspace2/2026-11-06/`; include the chart-width measurement and a reduced-motion screenshot.
- [ ] Run `unslop` checks and the existing `WorkspaceVisual` tests; report any red target instead of hiding it.

---

## Track B — E2 Pattern Spotlight + p12/p19/p21

### Task B1: SpotlightModel adapter and primary selector

**Files:**
- Create: `frontend-v2/src/features/technical/model/spotlight/types.ts`
- Create: `frontend-v2/src/features/technical/model/spotlight/adapter.ts`
- Create: `frontend-v2/src/features/technical/model/spotlight/select.ts`
- Test: `frontend-v2/src/features/technical/model/spotlight/__tests__/adapter.test.ts`
- Test: `frontend-v2/src/features/technical/model/spotlight/__tests__/select.test.ts`

**Interfaces:**
- Produces: `SpotlightModel { id; source: 'doubleTap'|'classic'; kind; kindLabel; direction; status; grade?; score?; quality; anchorIndex; points; upper; lower; neckline?; target; stop; breakoutIndex?; tp1?; tp2?; legs?; scoreBreakdown?; notes? }`
- `doubleTapToSpotlight(p: DoubleTapPattern): SpotlightModel`
- `classicToSpotlight(p: ChartPattern): SpotlightModel`
- `selectSpotlightPattern(models: SpotlightModel[], lastIndex: number, visibleRange?: [number, number]): SpotlightModel | null` — rule from spec §3.1: candidates anchor within 250 bars/visible range; forming within 60, confirmed within 120, then quality/recency.

- [ ] **Step 1: Failing tests** — adapters preserve kind/status/levels; selector prefers a recent forming W/M over an older confirmed triangle; returns null for an empty pool; W/M source is `doubleTap`.
- [ ] **Step 2: Run → fail** — `npx vitest run src/features/technical/model/spotlight`.
- [ ] **Step 3: Implement** pure functions; no React/klinecharts imports.
- [ ] **Step 4: Run tests + `npx tsc -b`**. Do not commit.

### Task B2: p12 score, grade and lifecycle in the W/M engine

**Files:**
- Modify: `frontend-v2/src/features/technical/model/types.ts` (DoubleTapPattern fields/status)
- Modify: `frontend-v2/src/features/technical/model/doubleTapEngine.ts`
- Create: `frontend-v2/src/features/technical/model/doubleTapScore.ts`
- Test: `frontend-v2/src/features/technical/model/__tests__/doubleTapScore.test.ts`
- Test: `frontend-v2/src/features/technical/model/__tests__/doubleTapEngine.test.ts` (extend)

**Interfaces:**
- `scoreDoubleTap({ matchPct, rsiDivergence, volumeDivergence, volumeKnown, heightAtr, symmetry, priorTrendRatio }): { score; grade: 'A'|'B'|'C'; breakdown: { match; rsi; volume; height; symmetry; trend } }` — exact p12 weights 25/20/15/15/10/15, volume unknown = 7.5, grade A≥75/B≥55.
- Extend `DoubleTapPattern['status']` with `'failed' | 'timed_out'`; map p12 lifecycle:
  - invalid before break → `invalidated`
  - stop after break before TP1 → `failed`
  - TP1/TP2 → `tp1_hit`/`tp2_hit`
  - expiry after break → `timed_out`
- `p12Score`, `grade`, `scoreBreakdown` on `DoubleTapPattern`.
- Do not change `DEFAULT_PRECISION_PARAMS` in this task.

- [ ] **Step 1: Failing test** — p12 score example: match 1, RSI true, volume unknown, height≥3 ATR, symmetry 1, prior 1 → 100 → grade A; match 0, no RSI, volume known no divergence, height 0, symmetry 0, prior 0 → 0 → grade C; volume unknown adds 7.5.
- [ ] **Step 2: Run → fail**.
- [ ] **Step 3: Implement** the pure scorer and wire it into `buildPattern`; extend status transitions in the lifecycle loop.
- [ ] **Step 4: Run** `npx vitest run src/features/technical/model/__tests__/doubleTapScore.test.ts src/features/technical/model/__tests__/doubleTapEngine.test.ts` + `npx tsc -b`. Do not commit.

### Task B3: PatternSpotlightLayer (SVG 3D grammar + animation)

**Files:**
- Create: `frontend-v2/src/features/technical/ui/PatternSpotlightLayer.tsx`
- Create: `frontend-v2/src/features/technical/ui/patternSpotlight.css` (imported by the layer)
- Modify: `frontend-v2/src/features/technical/ui/KLineChartWrapper.tsx` (mount only)
- Test: `frontend-v2/src/features/technical/ui/__tests__/PatternSpotlightLayer.test.tsx`

**Interfaces:**
- Props: `{ chart: Chart | null; primary: SpotlightModel | null; isLight?: boolean }`
- Renders: extruded neckline/trigger slab (front/top/side polygons), shadowed leg polyline, main label (kind/status/grade/score), BREAK and LONG/SHORT tags, TP1/TP2/SL rails (W/M only), all with `data-testid` hooks.
- Animation classes: 700ms path draw, 200ms slab/tag stagger, 150ms label; one-shot; reduced-motion static.
- W/M uses `doubleTapToSpotlight`; other tier-1 uses `classicToSpotlight`; one primary only.

- [ ] **Step 1: Failing test** — render with a mock chart and a W/M model; assert the label contains `Grade A`, `BREAK`, `TP1`, `SL`; assert the extrusion polygons exist; assert no `animation-iteration-count: infinite`; reduced-motion test.
- [ ] **Step 2: Run → fail**.
- [ ] **Step 3: Implement** the layer and mount it in `KLineChartWrapper`; remove the old `PatternStoryOverlay` mount only after the new layer passes; keep the old component file until tests pass (then delete it).
- [ ] **Step 4: Run** the new test + `KLineChartWrapper.test.tsx` + `npx tsc -b`. Do not commit.

### Task B4: Single ownership of W/M and compact secondary labels

**Files:**
- Modify: `frontend-v2/src/features/technical/overlays/patternOverlay.ts`
- Modify: `frontend-v2/src/features/technical/model/patterns/registry.ts` (if needed)
- Test: `frontend-v2/src/features/technical/overlays/__tests__/patternOverlay.test.ts`

- [ ] **Step 1: Failing test** — a `DOUBLE_BOTTOM` ChartPattern is not drawn by `patternFigures`; a `FLAG_BULL` still is; a W/M DoubleTap pattern yields exactly one spotlight label.
- [ ] **Step 2: Run → fail**.
- [ ] **Step 3: Implement** the filter; ensure the event feed still shows W/M from the DoubleTap source.
- [ ] **Step 4: Run tests + `npx tsc -b`**. Do not commit.

### Task B5: p19 pivot-channel detector (pure) and config

**Files:**
- Create: `frontend-v2/src/features/technical/model/patterns/detectChannelPivot.ts`
- Modify: `frontend-v2/src/features/technical/model/patterns/config.ts` (`channelPivot` block)
- Test: `frontend-v2/src/features/technical/model/patterns/__tests__/channelPivot.test.ts`

**Interfaces:**
- `detectPivotChannel(candles, atrSeries, config): ChannelCandidate[]`
- `ChannelCandidate { kind: 'PIVOT_CHANNEL'|'CONVERGING_WEDGE'|'SYMMETRIC_TRIANGLE'|'ASCENDING_TRIANGLE'|'DESCENDING_TRIANGLE'|'EXPANDING_STRUCTURE'; upper; lower; points; score; grade; touches; violations; apexIndex?; barsToApex?; convergencePct?; lateStage; lifecycle: 'active'|'late'|'broken'|'expired'; metrics }`
- Config fields: all p19 params from spec §2.3, including `pivotLen=20`, `autoPivotCount=5`, `autoLookbackBars=250`, `minAnchorSpacing=10`, `breakoutAtr=0.30`, `breakoutConfirmBars=2`, `expireAfterBreakBars=10`, `reclaimBars=2`, `lateStageWidthAtr=1.5`, `lateStageApexBars=15`, `touchTolAtr=0.20`, `violationTolAtr=0.35`, `minTouchSpacing=5`, `minWidthAtr=1`, `maxWidthAtr=20`, `balancePenaltyStart=1.5`.

- [ ] **Step 1: Failing tests** — (a) score components equal p12 formulas to 1e-9 and caps; (b) parallel classification at 10% slope difference; (c) lateStage at width≤1.5 ATR or ≤15 bars to apex; (d) no-look-ahead: appending candles does not change a past candidate; (e) per-bar ATR tolerance.
- [ ] **Step 2: Run → fail**.
- [ ] **Step 3: Implement** the pure detector; reuse `pivots.ts`, `geometry.ts`; no React imports.
- [ ] **Step 4: Run the test + `npx tsc -b`**. Do not commit.

### Task B6: p21 S/R retest zone (pure) and state machine

**Files:**
- Create: `frontend-v2/src/features/technical/model/events/zone.ts`
- Modify: `frontend-v2/src/features/technical/model/events/config.ts` (`srRetest` block)
- Test: `frontend-v2/src/features/technical/model/events/__tests__/zone.test.ts`

**Interfaces:**
- `detectSrRetest(candles, config): SrRetestZone[]`
- `SrRetestZone { upper; lower; fromIndex; toIndex; state: 0|1|2|3|-1|-2|-3; volumeBalanceAvailable: false; breakoutIndex?; retestIndex?; direction: 'bullish'|'bearish' }`
- Config: `pivotLen=7`, `stdevLen=40`, `toleranceStdevMult=1.0`, `maxZones=150`, `expiryBars=500`, `closeConfirm=true`.
- Two-swing zone, o/h/l/c thickness, price/time overlap rejection, state machine 0→±1→±2→±3, failed break reverts.

- [ ] **Step 1: Failing tests** — expected zone bounds; overlapping zone rejected; exactly one bullish retest at the expected bar; expiry; volume flag false.
- [ ] **Step 2: Run → fail**.
- [ ] **Step 3: Implement** the pure detector; use candle direction as volume proxy but keep `volumeBalanceAvailable:false`.
- [ ] **Step 4: Run tests + `npx tsc -b`**. Do not commit.

### Task B7: Integrate p19/p21 into the event scan and overlay

**Files:**
- Modify: `frontend-v2/src/features/technical/model/events/types.ts`
- Modify: `frontend-v2/src/features/technical/model/events/scan.ts`
- Modify: `frontend-v2/src/features/technical/overlays/eventOverlay.ts`
- Test: `frontend-v2/src/features/technical/model/events/__tests__/engine.test.ts` (extend)
- Test: `frontend-v2/src/features/technical/overlays/__tests__/eventOverlay.test.ts`

**Interfaces:**
- Add event kinds `PIVOT_CHANNEL`/`CHANNEL_STRUCTURE` and `SR_RETEST`; keep families `channel`/`breakout`.
- `scanChart` includes p19/p21 events; `primary.channel` uses the highest-quality p19; `primary.breakout` uses the newest p21 retest or the existing breakout.
- `eventOverlay` draws the primary channel band/zone box with the same compact grammar (no 3D W/M zigzag).
- No duplicate drawing with `MultiModeChannel`/`BreakoutRetestPro`/`ftsSupportResistance`: only the event scan's primary is overlaid.

- [ ] **Step 1: Failing test** — scan a fixture with a parallel channel and a retest; assert `primary.channel`/`primary.breakout` and that only one channel figure is produced; assert no duplicate W/M.
- [ ] **Step 2: Run → fail**.
- [ ] **Step 3: Implement** integration; keep the 50ms scan budget.
- [ ] **Step 4: Run** the event engine/overlay tests + `npx tsc -b`. Do not commit.

### Task B8: InspectorRail compact p12 stats + auto-scan dependency fix

**Files:**
- Modify: `frontend-v2/src/features/technical/ui/workspace/InspectorRail.tsx` (owned by E2; E1 must not edit)
- Create: `frontend-v2/src/features/technical/ui/workspace/PatternStatsPanel.tsx`
- Modify: `frontend-v2/src/features/technical/ui/KLineChartWrapper.tsx` (scan effect deps)
- Test: `frontend-v2/src/features/technical/ui/workspace/__tests__/PatternStatsPanel.test.tsx`
- Test: `frontend-v2/src/features/technical/ui/__tests__/KLineChartWrapper.test.tsx` (extend)

- [ ] **Step 1: Failing test** — stats panel shows TOPS/BOTTOMS/Detected/Breaks/Wins/TP2/Losses/Win Rate/Live Setup from a fixture; changing `adjustmentMode` re-runs the scan (spy on `scanChart`).
- [ ] **Step 2: Run → fail**.
- [ ] **Step 3: Implement** the compact panel (12px, no big chart table) and add `adjustmentMode` to the effect dependencies.
- [ ] **Step 4: Run tests + `npx tsc -b`**. Do not commit.

### Task B9: E2 evidence — Phase D re-audit and live visuals (main agent)

- [ ] Re-run the 15×2 export + render + tier-1 labels; gate: 39/39, zero fake.
- [ ] Run the full frontend suite and build.
- [ ] Live browser: load a W/M symbol and a triangle/flag symbol at 1366×768 and 1920×1080; capture the primary spotlight, BREAK/LONG tag, TP/SL rails, stats panel; verify reduced-motion; verify no duplicate W/M.
- [ ] Record the evidence under `_audit/rebuild/workspace2/2026-11-06/` and update the Phase D evidence only if the detector set changed (it should not).

---

## Track C — Kronos background (parallel, after E0)

### Task C1: Download and verify Kronos-mini + tokenizer

**Files:**
- Modify/Use: `tools/download_kronos_models.py`
- Create: `models/kronos/README.md` (download source, date, hashes; do not commit weights if large)
- Test: `python -c` presence/size/hash checks.

- [ ] Run the download script; verify the mini model (4.1M) and tokenizer files exist with expected sizes/hashes; record the exact URLs and date.
- [ ] If download is blocked, stop and report the exact HTTP/DNS error; do not fabricate a model.

### Task C2: CPU inference benchmark

- [ ] Run `tools/kronos_inference.py` on a fixed synthetic/real series for horizons 3/6/12; measure cold/warm latency, RSS memory, output shape.
- [ ] Write `_audit/rebuild/kronos/2026-11-06/benchmark.json` with model id, hashes, device, latency, memory, horizons, input length.
- [ ] If the script needs a dependency install, use a local venv; do not modify the system Python. Report the exact commands.

### Task C3: Readiness report and F handoff

- [ ] Write `_audit/rebuild/kronos/2026-11-06/report.md`: real inference proven/blocked, latency vs the 30ms budget, model choice, and the exact F integration steps (Go prediction + forecast API + UI labels).
- [ ] Do not wire the forecast UI until the benchmark proves real inference.

---

## Integration and gates

### Task I1: Merge/verify E1+E2

- [ ] Ensure no file outside the ownership table changed; resolve shared `KLineChartWrapper` edits only through E2.
- [ ] Run `npx tsc -b`, `npx vitest run` (full), `npm run build`.
- [ ] Run the Phase D 15×2 audit; gate 39/39 zero fake.
- [ ] Run the E1/E2 visual evidence from Tasks A6/B9.

### Task I2: Code review and completion

- [ ] Use `superpowers:requesting-code-review` on the diff; fix only verified findings.
- [ ] Use `superpowers:verification-before-completion`: every claim backed by a command output/screenshot; leave unmet targets red.
- [ ] Report: what shipped, what is blocked, evidence paths, next phase (Kronos F if benchmark succeeds; E3 Telegram ports otherwise).

## Self-Review (author)

- Spec coverage: E0 audit (done, `_audit/rebuild/telegram-e0/audit.md`), E1 A1–A6, E2 B1–B9, Kronos C1–C3, gates I1–I2.
- No placeholders: all tasks list files, interfaces, test intent, and commands.
- Type consistency: `SpotlightModel`, `LayoutLimits`, `ChannelCandidate`, `SrRetestZone` are defined in their producing tasks and consumed later by exact name.
- No commit steps: owner has not authorized commits; all tasks end with tests/type-check only.
