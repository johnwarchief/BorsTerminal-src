// features/technical/engine/klinecharts/KLineChartsEngine.ts -- تنها جایی که
// نامِ klinecharts درِ اپلیکیشنِ زنده شنیده می‌شود.
//
// چرا این کلاس هست: تا پیش از این، کامپوننتِ چارت خودش init/overlay/indicator
// را صدا می‌زد و «دو نسخه از یک موتور» (باندلِ npm و کپیِ window درِ
// public/vendor) هم‌زمان درِ صفحه بودند؛ registerOverlay رویِ یکی ثبت می‌شد و
// Chartِ دیگری آن نام را نمی‌شناخت. اینجا یک ورودیِ واحد است و همان ورودی
// صادق است که موتور چه چیزی را پشتیبانی می‌کند.
//
// سه واقعیتِ v10 که درِ این فایل عمداً ثبت شده‌اند (اگر کسی «ساده‌سازی» کرد،
// همین سطرها را بخواند):
//   ۱) `applyNewData` حذف شده؛ داده فقط از `setDataLoader` + `resetData` می‌آید.
//   ۲) `getVisibleRange()` اندیس می‌دهد نه timestamp؛ ترجمه اینجا انجام می‌شود.
//   ۳) کلیدهایِ استایلِ تغییرکرده بی‌صدا نادیده گرفته می‌شوند (fillColor در برابر
//      backgroundColor)؛ پس نگاشتِ استایل فقط از همین‌جا نوشته می‌شود.
import { init, dispose, registerOverlay, registerIndicator, type Chart, type KLineData } from 'klinecharts';

import type { ChartEngine, CrosshairInfo, DrawnShape, EngineMountOptions } from '../ChartEngine';
import type {
  BarRequest,
  CandleStyleMode,
  ChartCapabilities,
  ChartIndicatorSpec,
  ChartOverlaySpec,
  ChartPalette,
  EngineBar,
  EngineError,
  EngineHealth,
} from '../types';

/** واژه‌هایِ مشترکِ لایه‌ها؛ همان گروه‌هایی که کامپوننتِ چارت به کار می‌برد */
const CANDLE_PANE = 'candle_pane';
const VOL_PANE = 'sub_pane_vol';

/** اندیکاتور/اورلیِ موتور را لایهٔ اپ نمی‌شمارد — فهرستِ سفیدِ ترسیمِ کاربر */
const BUILT_IN_NAMES = new Set([
  'VOL', 'MA', 'EMA', 'RSI', 'MACD', 'BOLL',
  'fts_strategy_overlays', 'fts_pattern_overlays', 'fts_corp_actions',
]);

/** اورلیِ «کمربند»: v10 هیچ اورلیِ آمادهٔ مستطیل ندارد — `rect` و `circle` فقط
 *  *نوعِ شکل* (figure)‌اند، پس createOverlay('rect') بی‌صدا هیچی می‌سازد. لایه
 *  باید خودش اورلیِ دو‌نقطه‌ای‌ای ثبت کند که شکلش rect باشد. */
const BAND_OVERLAY = 'btsBand';
let bandOverlayRegistered = false;

function ensureBandOverlay(): void {
  if (bandOverlayRegistered) return;
  bandOverlayRegistered = true;
  registerOverlay({
    name: BAND_OVERLAY,
    totalStep: 3,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    createXAxisFigures: () => [],
    createYAxisFigures: () => [],
    createPointFigures: ({ coordinates, overlay }: {
      coordinates: { x: number; y: number }[];
      overlay: { extendData?: unknown };
    }) => {
      const [a, b] = coordinates ?? [];
      if (!a || !b) return [];
      const d = (overlay.extendData ?? {}) as Record<string, unknown>;
      const color = typeof d.color === 'string' ? d.color : '#38bdf8';
      return [{
        type: 'rect',
        attrs: {
          x: Math.min(a.x, b.x),
          y: Math.min(a.y, b.y),
          width: Math.abs(b.x - a.x),
          height: Math.max(2, Math.abs(b.y - a.y)),
        },
        styles: {
          color: typeof d.fill === 'string' ? d.fill : `${color}22`,
          borderColor: color,
          borderSize: typeof d.width === 'number' ? d.width : 1,
          borderStyle: d.dashed === false ? 'solid' : 'dashed',
        },
        ignoreEvent: true,
      }];
    },
  } as never);
}

function candleStyleType(mode: CandleStyleMode): string {
  switch (mode) {
    case 'line':
      return 'line';
    case 'area':
      return 'area';
    case 'bars':
      return 'ohlc';
    case 'heikin':
      return 'candle_solid';
    case 'candles':
    default:
      return 'candle_solid';
  }
}

/**
 * پالت → استایل. عمداً سبک‌نویسیِ کاملِ تمِ نهایات‌نگر اینجا تکرار نمی‌شود؛
 * این نگاشت «نیتِ رنگی» را می‌سازد و تمِ کامل به‌عنوان patch داده می‌شود.
 */
function paletteStyles(p: ChartPalette, mode: CandleStyleMode): Record<string, unknown> {
  return {
    paper: { background: p.background },
    grid: {
      horizontal: { show: true, color: p.grid, style: 'dashed' },
      vertical: { show: true, color: p.grid, style: 'dashed' },
    },
    candle: {
      type: candleStyleType(mode),
      bar: {
        candle: {
          upColor: p.up,
          downColor: p.down,
          noChangeColor: p.axisText,
          upBorderColor: p.up,
          downBorderColor: p.down,
          noChangeBorderColor: p.axisText,
          upWickColor: p.up,
          downWickColor: p.down,
          noChangeWickColor: p.axisText,
        },
      },
      priceLine: { last: { line: { color: p.lastLine } } },
      tooltip: { text: { color: p.axisText } },
    },
    xAxis: {
      axisLine: { color: p.grid },
      tickText: { color: p.axisText },
    },
    yAxis: {
      axisLine: { color: p.grid },
      tickText: { color: p.axisText },
    },
    crosshair: {
      horizontal: { line: { color: p.crosshair }, text: { backgroundColor: p.crosshair } },
      vertical: { line: { color: p.crosshair }, text: { backgroundColor: p.crosshair } },
    },
  };
}

/** kind → اورلیِ آمادهٔ v10. بی‌این نگاشت، لایه مجبور است نامِ موتور بداند */
function overlayName(kind: ChartOverlaySpec['kind']): string {
  switch (kind) {
    case 'band':
      return BAND_OVERLAY;
    case 'segment':
      return 'segment';
    case 'marker':
      return 'simpleAnnotation';
    case 'level':
    default:
      return 'horizontalStraightLine';
  }
}

function overlayStyles(spec: ChartOverlaySpec): Record<string, unknown> {
  const size = spec.width ?? 1;
  const style = spec.dashed === false ? 'solid' : 'dashed';
  switch (spec.kind) {
    case 'band':
      // رنگِ کمربند از `extendData` می‌آید (اورلیِ سفارشیِ خودش می‌سازدش)؛
      // کلیدِ polygon اینجا نقشی ندارد و گذاشتنش فقط دروغِ استایل است.
      return {};
    case 'marker':
      return {
        text: {
          color: '#ffffff',
          size: 10.5,
          family: 'Vazirmatn, sans-serif',
          weight: 'bold',
          backgroundColor: spec.color,
          paddingLeft: 6,
          paddingRight: 6,
          paddingTop: 2,
          paddingBottom: 2,
        },
      };
    default:
      return { line: { color: spec.color, size, style } };
  }
}

type OverlayRow = {
  id?: string;
  name?: string;
  groupId?: string;
  points?: { timestamp?: number; value?: number }[];
  lock?: boolean;
  styles?: unknown;
  extendData?: unknown;
};

export class KLineChartsEngine implements ChartEngine {
  readonly id = 'klinecharts' as const;

  readonly capabilities: ChartCapabilities = {
    label: 'KLineCharts v10',
    panes: 4,
    overlay: { level: true, band: true, segment: true, marker: true },
    customIndicator: true,
    builtinDrawTools: true,
    minuteTimeframes: true,
    logScale: true,
    jalaliAxis: true,
    crosshairEvents: true,
    exportImage: true,
    requiresWebGL: false,
  };

  private chart: Chart | null = null;
  private bars: KLineData[] = [];
  private requester: ((r: BarRequest) => EngineBar[]) | null = null;
  private errors: EngineError[] = [];
  private crosshairCbs = new Set<(i: CrosshairInfo) => void>();
  private drawCbs = new Set<() => void>();
  private errorCbs = new Set<(e: EngineError) => void>();
  /** گروه‌هایی که این لایه ساخته تا applyOverlays «جایگزین» کند نه انباشته */
  private ownedGroups = new Set<string>();

  async mount(host: HTMLElement, opts: EngineMountOptions): Promise<void> {
    const chart = init(host, {
      layout: { barSpaceLimit: { min: 2, max: 40 }, yAxis: { position: 'right', inside: false } },
      thousandsSeparator: { sign: ',' },
      formatter: { formatDate: ({ timestamp, type }) => opts.formatTime(timestamp, type === 'crosshair' ? 60_000 : 86_400_000) },
      timezone: 'Asia/Tehran',
      styles: paletteStyles(opts.palette, opts.candleStyle) as never,
    });
    if (!chart) {
      this.fail('init-failed', 'KLineCharts نتوانست در این ظرف رندر کند');
      return;
    }
    this.chart = chart;
    this.hostEl = host;
    chart.setDataLoader({
      getBars: ({ callback }) => {
        callback(this.bars, { forward: false, backward: false });
      },
    });
    // v10 لودر را بی‌«سمبل و دوره» هرگز صدا نمی‌زند؛ این سه‌گانه (setSymbol →
    // setPeriod → resetData) همان ترتیبِ ثابت‌شده در رپرِ زنده است. بی‌آن،
    // چارتِ آزمایشگاه پرِ بوم می‌ماند در حالی که barCount عدد می‌دهد.
    chart.setSymbol({ ticker: 'bors', pricePrecision: 0, volumePrecision: 0 } as never);
    chart.setPeriod({ type: 'day', span: 1 } as never);
    chart.resetData();
    chart.setOffsetRightDistance(Math.max(0, (opts.visibleBars ?? 120) - 60) * 8);
    try {
      chart.createIndicator({ name: 'VOL', id: VOL_PANE, paneId: VOL_PANE }, false);
      chart.setPaneOptions({ id: VOL_PANE, height: 110, minHeight: 90 } as never);
    } catch (e) {
      this.fail('volume-pane', String((e as Error)?.message ?? e));
    }
    try {
      chart.subscribeAction?.('onCrosshairChange', (data?: unknown) => {
        const d = (data ?? {}) as { x?: number; y?: number; timestamp?: number; value?: number; paneId?: string };
        const info: CrosshairInfo = {
          timestamp: typeof d.timestamp === 'number' ? d.timestamp : null,
          price: typeof d.value === 'number' ? d.value : null,
          pane: typeof d.paneId === 'string' ? d.paneId : null,
        };
        this.crosshairCbs.forEach((cb) => cb(info));
      });
    } catch {
      /* موتورِ بی‌رویداد: capabilities.crosshairEvents باید false شود، نه کرش */
    }
    const ro = new ResizeObserver(() => this.resize());
    ro.observe(host);
    this.hostObserver = ro;
  }

  private hostObserver: ResizeObserver | null = null;
  /** ظرفی که چارت در آن ساخته شد — شمارشِ بوم از همین‌جا است، نه از Chart */
  private hostEl: HTMLElement | null = null;

  ready(): Promise<void> {
    return this.chart ? Promise.resolve() : Promise.reject(new Error('not mounted'));
  }

  destroy(): void {
    this.hostObserver?.disconnect();
    this.hostObserver = null;
    if (this.chart) {
      try {
        dispose(this.chart);
      } catch (e) {
        this.fail('dispose', String((e as Error)?.message ?? e));
      }
    }
    this.chart = null;
    this.hostEl = null;
    this.crosshairCbs.clear();
    this.drawCbs.clear();
    this.ownedGroups.clear();
  }

  // ---- داده -------------------------------------------------------------
  setBars(bars: EngineBar[]): void {
    this.bars = bars.map((b) => ({
      timestamp: b.timestamp,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
      volume: b.volume,
      turnover: b.turnover ?? null,
    })) as unknown as KLineData[];
    this.reload();
  }

  setBarRequester(req: (r: BarRequest) => EngineBar[]): void {
    this.requester = req;
  }

  reloadData(): void {
    this.reload();
  }

  private reload(): void {
    if (!this.chart) return;
    if (this.requester) this.setBars(this.requester({ from: null, to: null, span: this.bars.length }));
    try {
      this.chart.resetData();
      // بی‌این، دید سمتِ راستِ خالیِ بوم می‌ماند (همان چیزی که درِ
      // آزمایشگاه ثابت شد: barCount پر، بوم خالی).
      this.chart.scrollToRealTime();
    } catch (e) {
      this.fail('resetData', String((e as Error)?.message ?? e));
    }
  }

  // ---- نما --------------------------------------------------------------
  resize(): void {
    try {
      this.chart?.resize();
    } catch {
      /* ظرف از DOM رفته؛ خطا نبودنِ کار است */
    }
  }

  scrollToLast(): void {
    this.chart?.scrollToRealTime();
  }

  setScrollEnabled(enabled: boolean): void {
    this.chart?.setScrollEnabled(enabled);
  }

  getVisibleRange(): { from: number | null; to: number | null } {
    if (!this.chart) return { from: null, to: null };
    // v10 اندیس می‌دهد؛ بی‌این ترجمه مصرف‌کننده timestampِ جعلی می‌گیرد
    const { from, to } = this.chart.getVisibleRange();
    const at = (i: number) => this.bars[Math.max(0, Math.min(this.bars.length - 1, i))]?.timestamp ?? null;
    return { from: at(from), to: at(to) };
  }

  setLogScale(on: boolean): void {
    try {
      (this.chart as unknown as { overrideYAxis?: (o: unknown) => void })?.overrideYAxis?.({
        paneId: CANDLE_PANE,
        name: on ? 'log' : 'normal',
      });
    } catch (e) {
      this.fail('log-scale', String((e as Error)?.message ?? e));
    }
  }

  // ---- ظاهر -------------------------------------------------------------
  setPalette(palette: ChartPalette): void {
    this.chart?.setStyles(paletteStyles(palette, this.candleMode) as never);
  }

  private candleMode: CandleStyleMode = 'candles';

  setCandleStyle(mode: CandleStyleMode): void {
    this.candleMode = mode;
    this.chart?.setStyles({ candle: { type: candleStyleType(mode) } } as never);
  }

  setGridVisible(on: boolean): void {
    this.chart?.setStyles({
      grid: { horizontal: { show: on }, vertical: { show: on } },
    } as never);
  }

  setCrosshairVisible(on: boolean): void {
    this.chart?.setStyles({
      crosshair: { horizontal: { show: on }, vertical: { show: on } },
    } as never);
  }

  // ---- لایه‌ها -----------------------------------------------------------
  applyOverlays(group: string, specs: ChartOverlaySpec[]): void {
    const chart = this.chart;
    if (!chart) return;
    const keep = new Set(specs.map((s) => s.id));
    // جایگزینیِ واقعی: هر چه از این گروه هست و درِ فهرستِ تازه نیست پاک می‌شود
    this.rows(group)
      .filter((r) => typeof r.id === 'string' && !keep.has(r.id as string))
      .forEach((r) => {
        try {
          chart.removeOverlay({ id: r.id } as never);
        } catch {
          /* ردیفِ از پیش رفته */
        }
      });
    for (const spec of specs) {
      if (!spec.points.length) continue;
      try {
        if (spec.kind === 'band') ensureBandOverlay();
        chart.createOverlay({
          name: overlayName(spec.kind),
          groupId: group,
          lock: true,
          points: spec.points.map((p) => ({ timestamp: p.timestamp ?? undefined, value: p.value })) as never,
          styles: overlayStyles(spec) as never,
          ...(spec.kind === 'marker' ? { extendData: spec.label ?? '' } : {}),
          ...(spec.kind === 'band'
            ? { extendData: { color: spec.color, fill: spec.fill, width: spec.width, dashed: spec.dashed } }
            : {}),
        } as never);
      } catch (e) {
        this.fail('overlay', `${spec.id}: ${String((e as Error)?.message ?? e)}`);
      }
    }
    this.ownedGroups.add(group);
    this.emitDraw();
  }

  clearOverlays(group?: string): void {
    if (!this.chart) return;
    try {
      this.chart.removeOverlay(group ? ({ groupId: group } as never) : (undefined as never));
    } catch (e) {
      this.fail('clear-overlays', String((e as Error)?.message ?? e));
    }
    if (group) this.ownedGroups.delete(group);
    else this.ownedGroups.clear();
    this.emitDraw();
  }

  // ---- اندیکاتورها ------------------------------------------------------
  addIndicator(spec: ChartIndicatorSpec): void {
    try {
      this.chart?.createIndicator(
        {
          id: spec.id,
          name: spec.name,
          calcParams: spec.params ? [...spec.params] : undefined,
          paneId: spec.pane === 'volume' ? VOL_PANE : spec.pane === 'price' ? CANDLE_PANE : undefined,
          styles: spec.colors ? { lines: spec.colors.map((color) => ({ color })) } : undefined,
        } as never,
        true,
      );
    } catch (e) {
      this.fail('indicator', `${spec.name}: ${String((e as Error)?.message ?? e)}`);
    }
  }

  updateIndicator(spec: ChartIndicatorSpec): void {
    try {
      this.chart?.overrideIndicator({
        id: spec.id,
        name: spec.name,
        calcParams: spec.params ? [...spec.params] : undefined,
      } as never);
    } catch (e) {
      this.fail('indicator-override', String((e as Error)?.message ?? e));
    }
  }

  removeIndicator(id: string): void {
    try {
      this.chart?.removeIndicator({ id } as never);
    } catch (e) {
      this.fail('remove-indicator', String((e as Error)?.message ?? e));
    }
  }

  /** ثبتِ اندیکاتورِ سفارشی رویِ همان باندلی که چارت مصرف می‌کند */
  registerIndicatorDef(def: unknown): boolean {
    try {
      registerIndicator(def as never);
      return true;
    } catch {
      return false;
    }
  }

  registerOverlayDef(def: unknown): boolean {
    try {
      registerOverlay(def as never);
      return true;
    } catch {
      return false;
    }
  }

  // ---- ابزارِ ترسیمی ----------------------------------------------------
  beginDrawing(tool: string | null): void {
    if (!this.chart) return;
    try {
      this.chart.createOverlay(tool ?? null as never);
    } catch (e) {
      this.fail('draw', String((e as Error)?.message ?? e));
    }
  }

  listDrawings(group?: string): DrawnShape[] {
    return this.rows(group).map((r) => ({
      id: String(r.id ?? ''),
      tool: String(r.name ?? ''),
      group: String(r.groupId ?? 'fts-draw'),
      points: (r.points ?? []).map((p) => ({
        timestamp: typeof p.timestamp === 'number' ? p.timestamp : null,
        value: typeof p.value === 'number' ? p.value : 0,
      })),
      locked: r.lock,
    }));
  }

  removeDrawing(id: string): void {
    try {
      this.chart?.removeOverlay({ id } as never);
    } catch {
      /* رفته */
    }
    this.emitDraw();
  }

  updateDrawing(id: string, patch: Partial<DrawnShape>): void {
    try {
      this.chart?.overrideOverlay({
        id,
        points: patch.points as never,
        lock: patch.locked,
        styles: patch.hidden ? { line: { style: 'dotted' } } : undefined,
      } as never);
    } catch (e) {
      this.fail('draw-override', String((e as Error)?.message ?? e));
    }
    this.emitDraw();
  }

  clearDrawings(group?: string): void {
    this.clearOverlays(group ?? 'fts-draw');
  }

  onDrawingsChanged(cb: () => void): () => void {
    this.drawCbs.add(cb);
    return () => this.drawCbs.delete(cb);
  }

  onCrosshair(cb: (info: CrosshairInfo) => void): () => void {
    this.crosshairCbs.add(cb);
    return () => this.crosshairCbs.delete(cb);
  }

  // ---- صادق‌گویی ---------------------------------------------------------
  health(): EngineHealth {
    return {
      renderer: 'canvas2d',
      canvasCount: this.chart ? this.countCanvases() : 0,
      barCount: this.bars.length,
      overlayCount: this.rows().length,
      errors: [...this.errors],
    };
  }

  snapshotImage(): string | null {
    try {
      // امضای v10 سه موقعیتی است: (includeOverlay, type, backgroundColor)
      return this.chart?.getConvertPictureUrl(true, 'png') ?? null;
    } catch {
      return null;
    }
  }

  onError(cb: (e: EngineError) => void): () => void {
    this.errorCbs.add(cb);
    return () => this.errorCbs.delete(cb);
  }

  // ---- کمکي --------------------------------------------------------------
  private rows(group?: string): OverlayRow[] {
    const chart = this.chart as unknown as { getOverlays?: (o?: unknown) => OverlayRow[] };
    let all: OverlayRow[] = [];
    try {
      all = chart?.getOverlays?.() ?? [];
    } catch {
      return [];
    }
    if (!group) return all.filter((r) => r.name && !BUILT_IN_NAMES.has(r.name));
    return all.filter((r) => r.groupId === group);
  }

  private countCanvases(): number {
    return this.hostEl?.querySelectorAll('canvas').length ?? 0;
  }

  private emitDraw(): void {
    this.drawCbs.forEach((cb) => cb());
  }

  private fail(code: string, message: string): void {
    const e = { code, message };
    this.errors.push(e);
    this.errorCbs.forEach((cb) => cb(e));
  }
}
