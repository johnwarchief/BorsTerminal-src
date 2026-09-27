// vendor/klinecharts.d.ts -- تایپِ تنگِ KLineCharts v10، پروب‌شده از باندلِ npm
// این فایل هیچ باندلِ دومی را توصیف نمی‌کند: نسخهٔ وندورشدهٔ
// `public/vendor/klinecharts.min.js` (که با <script> روی `window.klinecharts`
// می‌نشست) از برنامه بیرون رفت و چارتِ یکتا از `npm/klinecharts` می‌آید.
// نگه‌داشتنش به‌جای اتکای مستقیم به اعلانِ خودِ پکیج به‌خاطرِ دو چیز است:
// امضاهایِ registerOverlay/registerIndicator که در .d.tsِ پکیج ناقص‌اند، و
// متدهایی که روی Store هستند نه Chart (guard: dev/chart_single_bundle_v1038.py).
// امضاها فقط چیزهایی است که واقعا در باندل استفاده می شود (پروب شده).
export type KLineData = {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  turnover?: number;
};

export type BarSpace = { bar: number; halfBar: number; gapBar: number; halfGapBar: number };

export type VisibleRange = { from: number; to: number; realFrom: number; realTo: number };

export type Crosshair = {
  dataIndex?: number;
  kLineData?: KLineData;
  x?: number;
  y?: number;
  paneId?: string;
};

export type ActionData = {
  type: string;
  chart: KLineChart;
  data?: Record<string, unknown>;
};

export type GetBarsReq = {
  type: 'init' | 'update' | 'forward' | 'backward';
  symbol: string;
  period: string;
  timestamp: number | null;
  /** more=boolean یا {forward,backward} — طبق باندل واقعی v10 */
  callback: (dataList: KLineData[], more?: boolean | { forward?: boolean; backward?: boolean }) => void;
};

export type DataLoader = {
  getBars: (req: GetBarsReq) => void;
  subscribeBar?: (info: { symbol: string; period: string; callback: (data: KLineData) => void }) => void;
  unsubscribeBar?: (info: { symbol: string; period: string }) => void;
};

/** اورلی سفارشی ثبت‌شده با registerOverlay */
export type OverlayFigureAttr = Record<string, unknown>;

export type RegisterOverlayDef = {
  name: string;
  totalStep?: number;
  needDefaultPointFigure?: boolean;
  needDefaultXAxisFigure?: boolean;
  needDefaultYAxisFigure?: boolean;
  ignoreEvent?: boolean;
  styles?: unknown;
  createPointFigures?: (ctx: OverlayFigureCtx) => OverlayFigure[];
  /** در v10 هر دو محور callbackِ جدا دارند (npm: createXAxisFigures روی Overlay) */
  createXAxisFigures?: (ctx: OverlayFigureCtx) => OverlayFigure[];
  createYAxisFigures?: (ctx: OverlayFigureCtx) => OverlayFigure[];
};

export type OverlayFigureCtx = {
  chart: KLineChart;
  overlay: Record<string, unknown>;
  coordinates: { x: number; y: number }[];
  bounding: { width: number; height: number };
  yAxis?: { isFromZero: () => boolean };
  barSpace: BarSpace;
  defaultStyles?: unknown;
};

export type OverlayFigure = {
  type: string;
  attrs: Record<string, unknown>;
  styles?: Record<string, unknown>;
  ignoreEvent?: boolean;
};

export type KLineChart = {
  // data
  setDataLoader: (loader: DataLoader) => void;
  setSymbol: (symbol: string) => void;
  setPeriod: (period: string) => void;
  getDataList: () => KLineData[];
  getVisibleRangeDataList: () => KLineData[];
  getVisibleRange: () => VisibleRange;
  resetData: (cb?: () => void) => void;
  // look
  setStyles: (styles: unknown) => void;
  getStyles: () => unknown;
  setFormatter: (formatter: unknown) => void;
  setLocale: (locale: string) => void;
  setTimezone: (tz: string) => void;
  setThousandsSeparator: (sep: unknown) => void;
  // layout
  setOffsetRightDistance: (d: number) => void;
  setMaxOffsetRightDistance: (d: number) => void;
  setPaneOptions: (opts: { id?: string; height?: number }) => void;
  layout: () => void;
  resize: () => void;
  getSize: () => { width: number; height: number };
  // zoom/pan
  zoom: (scale: number) => void;
  zoomAtCoordinate: (scale: number, coordinate?: unknown) => void;
  zoomAtDataIndex: (scale: number, dataIndex: number) => void;
  zoomAtTimestamp: (scale: number, timestamp: number) => void;
  setZoomEnabled: (enabled: boolean) => void;
  isZoomEnabled: () => boolean;
  setScrollEnabled: (enabled: boolean) => void;
  isScrollEnabled: () => boolean;
  scrollToTimestamp: (ts: number) => void;
  scrollToDataIndex: (i: number) => void;
  scrollToRealTime: () => void;
  scrollByDistance: (d: number) => void;
  scroll: (d: number) => void;
  setBarSpace: (space: number) => void;
  // crosshair
  setCrosshair: (crosshair?: Crosshair, notKeep?: boolean) => void;
  getCrosshair: () => Crosshair | null;
  // indicators
  createIndicator: (options: unknown, isStack?: boolean, paneId?: string) => string | null;
  removeIndicator: (filter?: unknown) => void;
  overrideIndicator: (override: unknown) => void;
  getIndicators: (filter?: unknown) => { setStyles: (s: unknown) => void }[];
  setPaneOptions2?: unknown;
  // overlays
  createOverlay: (overlay: Record<string, unknown>) => unknown;
  removeOverlay: (filter?: Record<string, unknown> | string) => void;
  getOverlays: (filter?: unknown) => unknown[];
  overrideOverlay: (override: Record<string, unknown>) => void;
  // actions
  subscribeAction: (type: string, cb: (data: ActionData) => void) => void;
  unsubscribeAction: (type: string, cb: (data: ActionData) => void) => void;
  executeAction: (type: string) => void;
  // screenshot
  getConvertPictureUrl: (opts?: { includeOverlay?: boolean; type?: string; backgroundColor?: string }) => string;
};

export type KLineChartsApi = {
  version: () => string;
  init: (container: HTMLElement | string, options?: Record<string, unknown>) => KLineChart | null;
  dispose: (container: HTMLElement | string) => void;
  registerLocale: (locale: string, localization: Record<string, unknown>) => void;
  registerOverlay: (overlay: RegisterOverlayDef) => void;
  registerIndicator: (indicator: Record<string, unknown>) => void;
  getSupportedOverlays: () => string[];
  utils: unknown;
};

export {};
