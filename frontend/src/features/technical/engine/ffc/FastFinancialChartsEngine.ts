// features/technical/engine/ffc/FastFinancialChartsEngine.ts -- موتورِ دوم.
//
// تفاوتِ بنیادی با KLineCharts: این موتور **اعلانی** است. یک آبجکتِ props دارد
// و هر تغییر با updateProps(partial) فرستاده می‌شود؛ چیزی به اسمِ
// createOverlay/removeOverlay وجود ندارد. پس این آداپتور یک propsِ داخلی نگه
// می‌دارد و همان «نیتِ فرمانیِ» رابط را به «وضعیتِ اعلانی» ترجمه می‌کند.
//
// دو حقیقت که از نوع‌هایِ خودِ بسته خوانده شده و اگر روزی عوض شد، اینجا
// می‌سوزد:
//   · کلاسِ داخلیِ بسته خودش `ChartEngine` نام دارد -- با importِ aliased
//     جدا می‌شود، وگرنه اسمِ رابطِ ما را می‌بلعد.
//   · هندسۀ کندل فقط WebGL2 است (برایِ همین requiresWebGL: true). لایه‌های
//     متن/کراس‌هیر Canvas2D‌اند ولی serie اصلی نه؛ رویِ GPU بدونِ WebGL2
//     چارتِ خالی می‌ماند، پس آزمایشگاه همان اول می‌گوید «نصب نمی‌شود».
import {
  ChartEngine as FfcEngine,
  type FastFinancialChartProps,
} from '@pairlens/fast-financial-charts/financial-chart';

import type { ChartEngine, CrosshairInfo, DrawnShape, EngineMountOptions } from '../ChartEngine';
import type {
  CandleStyleMode,
  ChartCapabilities,
  ChartIndicatorSpec,
  ChartOverlaySpec,
  ChartPalette,
  EngineBar,
  EngineError,
  EngineHealth,
} from '../types';

const SERIES_ID = 'primary';
/** واحدِ زمانیِ خودِ بسته میلی‌ثانیۀِ UTC است (README‌اش: `ts: Date.now()` و
 *  `ts: 1739990400000`) -- همان واحدِ کندل‌هایِ ما، پس تبدیلِ مقیاس لازم نیست.
 *  پیش‌تر اینجا بر ۱۰۰۰ تقسیم می‌شد؛ سنجشِ زنده نشان داد محورِ زمان به‌جایِ
 *  ۱۸۰ روز، چهار ساعت نشان می‌دهد و کندل‌ها روی هم می‌افتند. */

function ffcChartType(mode: CandleStyleMode): FastFinancialChartProps['chartType'] {
  switch (mode) {
    case 'line':
      return 'line';
    case 'area':
      return 'area';
    case 'bars':
      return 'bar';
    case 'heikin':
      return 'heikinAshi';
    case 'candles':
    default:
      return 'candles';
  }
}

function themeFromPalette(p: ChartPalette): Record<string, unknown> {
  return {
    background: p.background,
    grid: p.grid,
    axisText: p.axisText,
    upColor: p.up,
    downColor: p.down,
    crosshair: p.crosshair,
  };
}

/** اورلیِ مشترک → DrawingObjectِ خودِ بسته (اسم‌ها از نوع‌هایِ بسته برداشته شد) */
function toFfcDrawing(spec: ChartOverlaySpec): Record<string, unknown> | null {
  const base = {
    id: spec.id,
    color: spec.color,
    lineWidth: spec.width ?? 1,
    visible: true,
    lineStyle: spec.dashed === false ? 'solid' : 'dashed',
    seriesId: SERIES_ID,
  };
  const pt = (p: ChartOverlaySpec['points'][number]) => ({
    ts: p.timestamp ?? 0,
    price: p.value,
  });
  switch (spec.kind) {
    case 'level':
      return { ...base, type: 'hline', price: spec.points[0]?.value ?? 0 };
    case 'marker':
      return {
        ...base,
        type: 'text',
        point: pt(spec.points[0] ?? { timestamp: 0, value: 0 }),
        content: spec.label ?? '',
        fontSize: 11,
      };
    case 'segment':
      if (spec.points.length < 2) return null;
      return { ...base, type: 'line', points: [pt(spec.points[0]), pt(spec.points[1])] };
    case 'band':
    default:
      if (spec.points.length < 2) return null;
      return {
        ...base,
        type: 'rectangle',
        points: [pt(spec.points[0]), pt(spec.points[1])],
        fillColor: spec.fill ?? spec.color,
        fillOpacity: 0.14,
      };
  }
}

type FfcDrawingRow = { id?: string; type?: string; seriesId?: string };

export class FastFinancialChartsEngine implements ChartEngine {
  readonly id = 'ffc' as const;

  readonly capabilities: ChartCapabilities = {
    label: 'Fast Financial Charts 2.2',
    panes: 6,
    overlay: { level: true, band: true, segment: true, marker: true },
    customIndicator: true,
    builtinDrawTools: true,
    minuteBarRendering: true,
    logScale: true,
    // محورِ زمان را خودِ بسته با Intl می‌سازد؛ جلالی فقط با formatterِ ما ممکن
    // است و آن هم فقط «متن» را عوض می‌کند، نه نامِ ماه‌هایِ میلادیِ پیش‌فرض.
    jalaliAxis: false,
    crosshairEvents: true,
    exportImage: true,
    requiresWebGL: true,
  };

  private engine: FfcEngine | null = null;
  private props: Partial<FastFinancialChartProps> = {};
  private bars: EngineBar[] = [];
  private overlaysByGroup = new Map<string, ChartOverlaySpec[]>();
  private errors: EngineError[] = [];
  private crosshairCbs = new Set<(i: CrosshairInfo) => void>();
  private drawCbs = new Set<() => void>();
  private errorCbs = new Set<(e: EngineError) => void>();
  private observer: ResizeObserver | null = null;
  private mountHost: HTMLElement | null = null;

  async mount(host: HTMLElement, opts: EngineMountOptions): Promise<void> {
    if (typeof WebGL2RenderingContext !== 'undefined' && !this.hasWebGL2()) {
      this.fail('no-webgl2', 'این مرورگر/GPU WebGL2 ندارد؛ موتورِ دوم بالا نمی‌آید');
      return;
    }
    const el = this.buildElements(host);
    if (!el) return;
    this.props = {
      series: [{ id: SERIES_ID, label: '', bars: [], pricePrecision: 0 }],
      timeframe: '1d',
      chartType: ffcChartType(opts.candleStyle),
      theme: themeFromPalette(opts.palette) as never,
      panes: [{ id: 'volume', stretchFactor: 0.28, minHeight: 80 }],
      indicators: [{ type: 'VOLUME', seriesId: SERIES_ID, pane: 'volume' }] as never,
      drawings: [],
      // `updateProps` در خودِ بسته آرایهٔ `drawings` را فقط وقتی به store می‌دهد
      // که `controlled.drawings` روشن باشد (پیش‌فرض خاموش). بدون این، هر
      // patchِ لایه بی‌صدا دور ریخته می‌شد — همان چیزی که سنجشِ زنده نشان داد.
      controlled: { drawings: true },
      localization: {
        priceFormatter: (v: number) => opts.formatPrice(v),
        timeFormatter: (ts: number) => opts.formatTime(ts, 86_400_000),
      } as never,
      defaultViewport: { type: 'last-bars', bars: opts.visibleBars ?? 120 },
      onCrosshairMove: (p: unknown) => this.onMove(p),
      onDrawingsChange: () => this.drawCbs.forEach((cb) => cb()),
    };
    try {
      this.engine = new FfcEngine({
        elements: el as never,
        props: this.props as FastFinancialChartProps,
      });
    } catch (e) {
      this.fail('construct', String((e as Error)?.message ?? e));
      return;
    }
    const ro = new ResizeObserver(() => this.resize());
    ro.observe(host);
    this.observer = ro;
  }

  /**
   * خودِ بسته DOM نمی‌سازد (headless)؛ هفت عنصری که انتظار دارد را ما
   * می‌سازیم. اگر ترتیبِ stack یا pointer-events اشتباه باشد چارت خالی
   * می‌ماند — همان چیزی که آزمایشگاهِ موتورها جلویِ چشم نشان می‌دهد.
   */
  private buildElements(host: HTMLElement) {
    this.mountHost = host;
    const mk = (name: string, z: number, interactive: boolean): HTMLCanvasElement | null => {
      const c = document.createElement('canvas');
      c.dataset.engine = `ffc-${name}`;
      Object.assign(c.style, {
        position: 'absolute',
        inset: '0',
        width: '100%',
        height: '100%',
        zIndex: String(z),
        pointerEvents: interactive ? 'auto' : 'none',
      } satisfies Partial<CSSStyleDeclaration>);
      host.appendChild(c);
      return c;
    };
    if (getComputedStyle(host).position === 'static') host.style.position = 'relative';
    const ind = document.createElement('div');
    ind.dataset.engine = 'ffc-indicator-container';
    Object.assign(ind.style, { position: 'absolute', inset: '0', pointerEvents: 'none' } satisfies Partial<CSSStyleDeclaration>);
    host.appendChild(ind);
    const grid = mk('grid', 1, false);
    const main = mk('main', 2, false);
    const indicator = mk('indicator', 3, false);
    const indicatorUi = mk('indicator-ui', 4, false);
    const overlay = mk('overlay', 5, false);
    const ui = mk('ui', 6, true);
    if (!grid || !main || !indicator || !indicatorUi || !overlay || !ui) {
      this.fail('elements', 'ظرفِ چارت ساخته نشد');
      return null;
    }
    return {
      container: host,
      gridCanvas: grid,
      mainCanvas: main,
      overlayCanvas: overlay,
      uiCanvas: ui,
      indicatorCanvas: indicator,
      indicatorUiCanvas: indicatorUi,
      indicatorContainer: ind,
    };
  }

  private hasWebGL2(): boolean {
    try {
      const c = document.createElement('canvas');
      return !!c.getContext('webgl2');
    } catch {
      return false;
    }
  }

  ready(): Promise<void> {
    if (this.engine) return Promise.resolve();
    // دلیلِ بالا نیامدن را خودِ mount ثبت کرده (no-webgl2 / construct / elements)؛
    // «not mounted» تنها چیزی است که مصرف‌کننده نباید بشنود.
    const last = this.errors[this.errors.length - 1];
    return Promise.reject(new Error(last ? `${last.code}: ${last.message}` : 'not mounted'));
  }

  destroy(): void {
    this.observer?.disconnect();
    this.observer = null;
    // بسته dispose عمومی export نکرده؛ المان‌ها را خودمان از DOM بیرون می‌کنیم
    // تا رندرِ بعدی canvas یتیم نداشته باشد.
    if (this.mountHost) this.mountHost.replaceChildren();
    this.engine = null;
    this.crosshairCbs.clear();
    this.drawCbs.clear();
    this.overlaysByGroup.clear();
  }

  // ---- داده -------------------------------------------------------------
  setBars(bars: EngineBar[]): void {
    this.bars = bars;
    this.patch({
      series: [
        {
          id: SERIES_ID,
          bars: bars.map((b) => ({
            ts: b.timestamp,
            open: b.open,
            high: b.high,
            low: b.low,
            close: b.close,
            volume: b.volume,
          })),
        },
      ],
    });
  }

  reloadData(): void {
    this.setBars(this.bars);
  }

  // ---- نما --------------------------------------------------------------
  resize(): void {
    // بسته با ResizeObserverِ خودش size را می‌گیرد؛ فقط force re-render می‌دهیم
    this.patch({});
  }

  scrollToLast(): void {
    this.patch({ defaultViewport: { type: 'last-bars', bars: 120 } });
  }

  setScrollEnabled(enabled: boolean): void {
    this.patch({ interaction: { scrollEnabled: enabled } as never });
  }

  getVisibleRange(): { from: number | null; to: number | null } {
    if (!this.bars.length) return { from: null, to: null };
    return { from: this.bars[0].timestamp, to: this.bars[this.bars.length - 1].timestamp };
  }

  setLogScale(on: boolean): void {
    this.patch({ priceScaleMode: on ? 'logarithmic' : 'normal' });
  }

  // ---- ظاهر -------------------------------------------------------------
  setPalette(palette: ChartPalette): void {
    this.patch({ theme: themeFromPalette(palette) as never });
  }

  setCandleStyle(mode: CandleStyleMode): void {
    this.patch({ chartType: ffcChartType(mode) });
  }

  setGridVisible(on: boolean): void {
    this.patch({ theme: { showGrid: on } as never });
  }

  setCrosshairVisible(on: boolean): void {
    this.patch({ crosshairConfig: { visible: on } as never });
  }

  // ---- لایه‌ها -----------------------------------------------------------
  applyOverlays(group: string, specs: ChartOverlaySpec[]): void {
    this.overlaysByGroup.set(group, specs);
    const all: Record<string, unknown>[] = [];
    this.overlaysByGroup.forEach((list) => {
      for (const s of list) {
        const d = toFfcDrawing(s);
        if (d) all.push(d);
      }
    });
    this.patch({ drawings: all as never });
    this.drawCbs.forEach((cb) => cb());
  }

  clearOverlays(group?: string): void {
    if (group) this.overlaysByGroup.delete(group);
    else this.overlaysByGroup.clear();
    const all: Record<string, unknown>[] = [];
    this.overlaysByGroup.forEach((list) => {
      for (const s of list) {
        const d = toFfcDrawing(s);
        if (d) all.push(d);
      }
    });
    this.patch({ drawings: all as never });
  }

  // ---- اندیکاتورها ------------------------------------------------------
  addIndicator(spec: ChartIndicatorSpec): void {
    const list = [...((this.props.indicators ?? []) as unknown[])];
    list.push({
      type: spec.name,
      seriesId: SERIES_ID,
      pane: spec.pane === 'volume' ? 'volume' : 'overlay',
      ...this.ffcParams(spec),
    } as never);
    this.patch({ indicators: list as never });
  }

  updateIndicator(spec: ChartIndicatorSpec): void {
    const list = ((this.props.indicators ?? []) as { type?: string }[]).map((i) =>
      i.type === spec.name ? ({ ...i, ...this.ffcParams(spec) } as never) : i,
    );
    this.patch({ indicators: list as never });
  }

  removeIndicator(id: string): void {
    const list = ((this.props.indicators ?? []) as { type?: string }[]).filter((i) => i.type !== id);
    this.patch({ indicators: list as never });
  }

  registerIndicatorDef(def: unknown): boolean {
    try {
      const plugins = (this.props.plugins ?? {}) as Record<string, unknown[]>;
      plugins.indicators = [...(plugins.indicators ?? []), def as never];
      this.patch({ plugins: plugins as never });
      return true;
    } catch {
      return false;
    }
  }

  registerOverlayDef(): boolean {
    // شکلِ ترسیمیِ دلخواه درِ این موتور با DrawingShapeDefinition ممکن است،
    // ولی رابطِ ما آن را از اورلیِ مشترک جدا نگه داشته؛ درِ آزمایشگاه لازم نشد.
    return false;
  }

  // ---- ابزارِ ترسیمی ----------------------------------------------------
  beginDrawing(tool: string | null): void {
    this.patch({ activeTool: tool as never });
  }

  listDrawings(group?: string): DrawnShape[] {
    const specs = group ? (this.overlaysByGroup.get(group) ?? []) : [...this.overlaysByGroup.values()].flat();
    return specs.map((s) => ({
      id: s.id,
      tool: s.kind,
      group: s.group,
      points: s.points.map((p) => ({ timestamp: p.timestamp, value: p.value })),
      locked: true,
    }));
  }

  removeDrawing(id: string): void {
    let changed = false;
    this.overlaysByGroup.forEach((list, key) => {
      const next = list.filter((s) => s.id !== id);
      if (next.length !== list.length) changed = true;
      this.overlaysByGroup.set(key, next);
    });
    if (changed) this.applyOverlaysFromState();
  }

  updateDrawing(id: string, patchWith: Partial<DrawnShape>): void {
    this.overlaysByGroup.forEach((list, key) => {
      this.overlaysByGroup.set(
        key,
        list.map((s) => (s.id === id ? { ...s, points: patchWith.points ?? s.points } : s)),
      );
    });
    this.applyOverlaysFromState();
  }

  clearDrawings(group?: string): void {
    this.clearOverlays(group);
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
      renderer: this.hasWebGL2() ? 'webgl2 + canvas2d' : 'unavailable (no webgl2)',
      canvasCount: this.mountHost?.querySelectorAll('canvas').length ?? 0,
      barCount: this.bars.length,
      overlayCount: [...this.overlaysByGroup.values()].flat().length,
      errors: [...this.errors],
    };
  }

  snapshotImage(): string | null {
    try {
      const shot = (this.engine as unknown as { takeScreenshot?: (o: unknown) => { dataUrl: string } })
        ?.takeScreenshot?.({ includeUi: false });
      return shot?.dataUrl ?? null;
    } catch {
      return null;
    }
  }

  onError(cb: (e: EngineError) => void): () => void {
    this.errorCbs.add(cb);
    return () => this.errorCbs.delete(cb);
  }

  // ---- کمکي --------------------------------------------------------------
  private applyOverlaysFromState(): void {
    const all: Record<string, unknown>[] = [];
    this.overlaysByGroup.forEach((list) => {
      for (const s of list) {
        const d = toFfcDrawing(s);
        if (d) all.push(d);
      }
    });
    this.patch({ drawings: all as never });
  }

  private patch(next: Partial<FastFinancialChartProps>): void {
    this.props = { ...this.props, ...next };
    try {
      this.engine?.updateProps(next);
    } catch (e) {
      this.fail('updateProps', String((e as Error)?.message ?? e));
    }
  }

  private onMove(p: unknown): void {
    const d = (p ?? {}) as { ts?: number; price?: number; point?: { ts?: number; price?: number } };
    const ts = d.ts ?? d.point?.ts;
    const price = d.price ?? d.point?.price;
    const info: CrosshairInfo = {
      timestamp: typeof ts === 'number' ? ts : null,
      price: typeof price === 'number' ? price : null,
      pane: null,
    };
    this.crosshairCbs.forEach((cb) => cb(info));
  }

  /** klinecharts دوره‌ها را *ترتیبی* می‌خواهد (calcParams) و FFC *نام‌دار*.
   *  تبدیلِ حدسی نمی‌کنیم: یک پارامترِ عددی تنها موردی است که نامش «period»
   *  قطعی است؛ هر چیزِ دیگر بی‌ارسال می‌ماند و صادقانه گزارش می‌شود تا درِ
   *  آزمایشگاه «اندیکاتور با پیش‌فرض» را «اندیکاتورِ تنظیم‌شده» نخوانیم. */
  private ffcParams(spec: ChartIndicatorSpec): { params?: Record<string, number> } {
    const p = spec.params;
    if (!p || p.length === 0) return {};
    if (p.length === 1 && typeof p[0] === 'number') return { params: { period: p[0] } };
    this.fail('indicator-params',
      `${spec.name}: ${p.length} پارامتر ترتیبی؛ FFC نام می‌خواهد و پیش‌فرضِ خودش را نگه می‌دارد`);
    return {};
  }

  private fail(code: string, message: string): void {
    const e = { code, message };
    this.errors.push(e);
    this.errorCbs.forEach((cb) => cb(e));
  }
}

/** نامِ ابزارهایی که برایِ مقایسهٔ قابلیت‌ها فهرست می‌شوند */
export const FFC_DRAW_TOOLS: readonly string[] = [
  'line', 'ray', 'segment', 'hline', 'vline', 'rectangle', 'circle', 'text', 'fibonacci',
];

export type { FfcDrawingRow };
