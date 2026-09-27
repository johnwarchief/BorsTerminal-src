// features/technical/engine/ChartEngine.ts -- تنها چیزی که یک موتور باید جواب
// بدهد. نامِ هیچ کتابخانه‌ای اینجا نیست. این رابط از شمارشِ تماس‌هایِ واقعیِ
// چارتِ زنده ساخته شده، نه از آرزو: init/dispose، داده، بارگذاری، پنل‌ها،
// استایلِ نیت‌محور، اورلی، اندیکاتور، ابزارِ ترسیمی، نما، رویدادها، سلامت.
//
// قراردادِ کلی: هیچ متدی خطا نمی‌دهد که صفحه را بیندازد؛ شکست به `health()`
// و `onError` می‌نشیند. دلیلش رأیِ مالک است: اولویتِ اول «بی‌باگ و بی‌کرش».
import type {
  BarRequest,
  CandleStyleMode,
  ChartCapabilities,
  ChartEngineId,
  ChartIndicatorSpec,
  ChartOverlaySpec,
  ChartPalette,
  EngineBar,
  EngineError,
  EngineHealth,
} from './types';

export type CrosshairInfo = {
  timestamp: number | null;
  price: number | null;
  pane: string | null;
};

export type DrawnShape = {
  id: string;
  /** نامِ ابزار آن‌طور که موتور آن را می‌شناسد (برایِ بازیابیِ ترسیمِ ذخیره‌شده) */
  tool: string;
  group: string;
  points: { timestamp: number | null; value: number }[];
  locked?: boolean;
  hidden?: boolean;
};

export type EngineMountOptions = {
  /** تعدادِ کندلی که اولِ کار درِ دید می‌ماند */
  visibleBars: number;
  palette: ChartPalette;
  candleStyle: CandleStyleMode;
  /** برچسبِ محورِ زمان را خودِ اپ می‌سازد (تقویمِ جلالی) */
  formatTime: (timestamp: number, spanMs: number) => string;
  formatPrice: (value: number) => string;
};

export interface ChartEngine {
  readonly id: ChartEngineId;
  readonly capabilities: ChartCapabilities;

  mount(host: HTMLElement, opts: EngineMountOptions): Promise<void> | void;
  destroy(): void;
  /** پس ازِ mount شدنِ واقعی؛ مصرف‌کننده قبل ازِ این هیچ متدِ دیگری صدا نزند */
  ready(): Promise<void>;

  // ---- داده -------------------------------------------------------------
  setBars(bars: EngineBar[]): void;
  /** موتورِ داده‌خواه (KLineCharts) از این استفاده می‌کند؛ بقیه نادیده می‌گیرند */
  setBarRequester?(req: (r: BarRequest) => EngineBar[]): void;
  /** حجمِ کلِ پنجره عوض شده (مثلاً تجمیعِ تایم‌فریم) — نما دست‌نخورده بماند */
  reloadData(): void;

  // ---- نما --------------------------------------------------------------
  resize(): void;
  scrollToLast(): void;
  setScrollEnabled(enabled: boolean): void;
  setVisibleRange?(fromTs: number, toTs: number): void;
  getVisibleRange(): { from: number | null; to: number | null };
  setLogScale(on: boolean): void;

  // ---- ظاهر -------------------------------------------------------------
  setPalette(palette: ChartPalette): void;
  setCandleStyle(mode: CandleStyleMode): void;
  setGridVisible(on: boolean): void;
  setCrosshairVisible(on: boolean): void;

  // ---- لایه‌ها -----------------------------------------------------------
  /** جایگزینِ کاملِ یک گروه: چیزی که درِ فهرست جدید نیست پاک می‌شود */
  applyOverlays(group: string, specs: ChartOverlaySpec[]): void;
  clearOverlays(group?: string): void;

  // ---- اندیکاتورها ------------------------------------------------------
  addIndicator(spec: ChartIndicatorSpec): void;
  updateIndicator(spec: ChartIndicatorSpec): void;
  removeIndicator(id: string): void;
  /** موتورِ بی‌قابلیتِ اندیکاتورِ سفارشی باید false بدهد و صدا نکند */
  registerIndicatorDef?(def: unknown): boolean;
  /** شکلِ اورلیِ خودِ اپ (باندها و خطوطِ FTS) — همین‌جا ثبت می‌شود، نه درِ کامپوننت */
  registerOverlayDef?(def: unknown): boolean;

  // ---- ابزارِ ترسیمی ----------------------------------------------------
  /** حالتِ ترسیم: `tool` نامِ ابزارِ موتور است؛ null یعنی «از حالتِ ترسیم بیا بیرون» */
  beginDrawing(tool: string | null, opts?: { group?: string; locked?: boolean }): void;
  listDrawings(group?: string): DrawnShape[];
  removeDrawing(id: string): void;
  updateDrawing(id: string, patch: Partial<DrawnShape>): void;
  clearDrawings(group?: string): void;
  onDrawingsChanged(cb: () => void): () => void;

  // ---- رویدادها ----------------------------------------------------------
  onCrosshair(cb: (info: CrosshairInfo) => void): () => void;

  // ---- صادق‌گویی ---------------------------------------------------------
  health(): EngineHealth;
  snapshotImage?(): string | null;
  onError(cb: (e: EngineError) => void): () => void;
}

/** سازنده‌ای که رجیستری صدا می‌زند؛ هر موتور همین را export می‌کند */
export type ChartEngineFactory = () => ChartEngine;
