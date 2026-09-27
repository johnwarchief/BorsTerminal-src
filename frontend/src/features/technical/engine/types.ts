// features/technical/engine/types.ts -- واژه‌هایِ مشترکی که هیچ موتوری درِ آن‌ها
// نیست. هر چیزی که درِ این فایل شکلِ «KLineCharts» دارد آلودگی است: لایه باید
// بتواند موتورِ دوم را بدونِ تغییرِ مصرف‌کننده کنارِ اولی بگذارد.
//
// چرا این‌قدر کم: سطحِ تماسِ واقعیِ چارتِ زنده سنجیده شد (۲۳ متد، پرتکرارترینِ
// آن‌ها overlay/indicator/styles). چیزی که مصرف‌کننده نخواهد، رابط هم نمی‌گیرد.

export type ChartEngineId = 'klinecharts' | 'ffc';

/** یک کندلِ مستقل از موتور. timestamp میلی‌ثانیۀِ UTC است (نه روزِ جلالی) */
export type EngineBar = {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  /** گردشِ ریالیِ همان نشست — هر موتوری پنلِ ارزش ندارد؛ اختیاری است، نه صفر */
  turnover?: number | null;
};

/** نوعِ ظاهریِ کندل؛ واژه‌هایِ خودِ موتور اینجا ترجمه می‌شوند */
export type CandleStyleMode = 'candles' | 'bars' | 'line' | 'area' | 'heikin';

/**
 * نیتِ رنگیِ چارت، نه آبجکتِ استایلِ موتور. آداپتور هر موتور همین را به
 * setStyles/تمِ خودش ترجمه می‌کند؛ برایِ همین درِ آزمایشگاهِ موتورها دو طرف
 * «همان رنگ» را نشان می‌دهند نه «همان JSON».
 */
export type ChartPalette = {
  background: string;
  grid: string;
  axisText: string;
  up: string;
  down: string;
  lastLine: string;
  crosshair: string;
  dark: boolean;
};

/**
 * اورلیِ موتور-مستقل. یک نکت = خطِ سطح، دو نکت = ناحیه یا پاره‌خط، و
 * marker یک نکت با برچسب است. `id` پایدار است تا به‌روزرسانی «جایگزین»
 * شود نه «انباشته» — همان چیزی که #193 درِ نگاشتِ الگوها لازم داشت.
 */
export type ChartOverlayKind = 'level' | 'band' | 'segment' | 'marker';

export type ChartOverlaySpec = {
  id: string;
  kind: ChartOverlayKind;
  /** گروهِ منطقی؛ پاک‌کردنِ یک لایه با یک کلید انجام می‌شود */
  group: string;
  points: { timestamp: number | null; value: number }[];
  color: string;
  /** فقط برایِ band؛ بی‌آن خطی است (برایِ کمربندهایِ بلندِ #193) */
  fill?: string | null;
  label?: string | null;
  width?: number;
  dashed?: boolean;
  pane?: 'price' | 'volume';
};

/** اندیکاتورِ آماده یا ثبت‌شده توسط خودِ اپ؛ `name` برایِ موتور معنی دارد */
export type ChartIndicatorSpec = {
  id: string;
  name: string;
  pane?: 'price' | 'volume';
  /** دوره‌ها به همان ترتیبی که موتور سلسلةِ محاسبه می‌خواهد
   *  (klinecharts: `calcParams`). موتورِ دوم پارامتر را *نام‌دار* می‌خواهد و
   *  این آداپتر فعلاً تبدیلِ حدسی نمی‌کند؛ بی‌تبدیل رد نمی‌شود، هشدار می‌دهد. */
  params?: readonly (number | string | boolean)[];
  /** رنگِ خطوطِ اندیکاتور، به همان ترتیبی که موتور سلسلةِ داده می‌سازد */
  colors?: string[];
};

/** چیزی که رابطِ موتور باید دربارهٔ توانایی‌هایش صادق باشد */
export type ChartCapabilities = {
  label: string;
  /** موتور چند پنلِ مستقل می‌پذیرد (۱ یعنی قیمت و حجم قفل‌اند) */
  panes: number;
  overlay: Record<ChartOverlayKind, boolean>;
  customIndicator: boolean;
  builtinDrawTools: boolean;
  minuteTimeframes: boolean;
  logScale: boolean;
  jalaliAxis: boolean;
  crosshairEvents: boolean;
  exportImage: boolean;
  /** WebGL لازم دارد؟ اگر false باشد رویِ GPU قدیمی هم بالا می‌آید */
  requiresWebGL: boolean;
};

export type EngineError = { code: string; message: string };

/** گزارشِ زندۀِ موتور برایِ آزمایشگاه: با این‌ها مقایسه معنا پیدا می‌کند */
export type EngineHealth = {
  renderer: string;
  canvasCount: number;
  barCount: number;
  overlayCount: number;
  errors: EngineError[];
};

/** درخواستِ بارگذاریِ داده از دستِ موتور؛ آداپتور باید صادق باشد که چند تا خواست */
export type BarRequest = {
  from: number | null;
  to: number | null;
  span: number;
};
