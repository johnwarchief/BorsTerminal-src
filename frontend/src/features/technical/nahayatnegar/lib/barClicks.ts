// features/technical/nahayatnegar/lib/barClicks.ts -- قراردادِ رویدادِ کلیک رویِ چارت
// این فایل چیزی را «تشخیص» نمی‌دهد: نه ستاپ، نه فیبو، نه CHoCH. فقط نتیجه‌هایی را
// که موتورِ سرور (`fts.setups`) و مارکرهایِ رسم‌شده (`chart.getOverlays()`) از پیش
// ساخته‌اند به میله‌ای که کاربر زد می‌چسباند، تا لاگِ کلیک همان چیزی باشد که پنل
// می‌گوید — نه قاعدۀ دومی درِ فرانت.
//
// چرا مارکر «کلیدنی» نیست: هر مارکرِ FTS با `lock: true` و از قالبِ آمادهٔ
// `simpleAnnotation` رسم می‌شود که هر سه شکلش `ignoreEvent: true` دارد
// (`node_modules/klinecharts/dist/index.esm.js`، `var simpleAnnotation`) و اورلی‌هایِ
// سفارشیِ خودِ برنامه هم درِ `lib/ftsOverlays.ts` همان پرچم را دارند. پس کلیک روی
// خودِ نگاره هیچ رویدادی تولید نمی‌کند و تنها راۀ صادق کلیکِ میله است: میله‌ای که
// موتور رویش برچسب گذاشته ⇒ رویدادِ `marker` با همان برچسب. `lock` و `ignoreEvent`
// را برایِ این کار برنمی‌داریم، چون کشیدنِ مارکر و پنِ چارت را عوض می‌کند.
import type { KLineData } from 'klinecharts';

import { epochToJalali } from '../../lib/jalaliDate';
import type { Timeframe } from './timeframe';

/** ستاپِ موتورِ FTS، همان‌طور که درِ `/api/fts` و `/api/chart-db` می‌آید */
export type EngineSetupRef = { kind: string; label: string; price: number };

export type ChartBarClick = {
  /** کلیدِ پایدار: نماد|بازه|timestampِ میله. هویتِ ردیف از رشتهٔ تاریخِ دیدنی
   *  («YYYY/MM/DD») ساخته نمی‌شود، تا تغییرِ قالبِ نمایشِ تاریخ ردیف‌ها را نشکند. */
  key: string;
  symbol: string;
  timeframe: Timeframe;
  /** timestampِ میله‌ای که کاربر دید (میلی‌ثانیه UTC، همان واحدِ چارت) */
  barTs: number;
  /** تاریخِ جلالیِ همان میله — همان چیزی که رویِ محور خوانده می‌شود */
  barDate: string;
  /** candle: میلهٔ بی‌برچسب؛ marker: میله‌ای که موتور رویش برچسب گذاشته است */
  kind: 'candle' | 'marker';
  /** برچسبِ مارکرِ رسم‌شده رویِ همان میله؛ null یعنی مارکری آن‌جا نبود */
  marker: string | null;
  /** نتیجهٔ موتور برایِ همان میله — کپیِ خام، نه بازسازیِ قاعده درِ فرانت */
  engineSetups: EngineSetupRef[];
  /** نسبتِ تعدیلِ همان روز، خام؛ null یعنی رویدادی نبود (عدد را UI قالب می‌کند) */
  adjustRatio: number | null;
  /** بستۀ همان میله، گردِ دو رقم — مبنایِ متنیِ لاگ */
  close: number;
  /** لحظۀ کلیک (ساعتِ دستگاه) */
  atMs: number;
};

/** ردیفِ اورلیِ خوانده‌شده از چارت (`chart.getOverlays()`) — فقط چیزی که لازم است */
export type OverlayRef = {
  name?: string;
  groupId?: string;
  points?: { timestamp?: number }[];
  extendData?: unknown;
};

export type ClickInput = {
  symbol: string;
  timeframe: Timeframe;
  bar: KLineData | null | undefined;
  /** `ftsAnalysis.setups`ِ سرور — همان فهرستِ تاریخ‌دارِ `[{date,kind,label,price,side}]` */
  setups?: { date: string; kind: string; label: string; price: number; side?: string | null }[] | null;
  /** رویدادهایِ تعدیل (`CorporateAction`) — تطبیق با timestampِ خودِ رویداد، نه رشتهٔ تاریخ */
  adjustments?: { timestamp: number; ratio: number }[] | null;
  /** اورلی‌هایِ رسم‌شده، برایِ فهمیدنِ اینکه میله برچسب داشت یا نه */
  overlays?: OverlayRef[] | null;
  atMs?: number;
};

/** برچسبِ خواناِ یک اورلی؛ `extendData` درِ مارکرهایِ FTS همان رشتهٔ موتور است */
function overlayLabel(o: OverlayRef): string | null {
  const e = o.extendData;
  if (typeof e === 'string' && e.trim()) return e.trim();
  if (e && typeof e === 'object') {
    const t = (e as { text?: unknown }).text;
    if (typeof t === 'string' && t.trim()) return t.trim();
  }
  return null;
}

/**
 * رویدادِ کلیک را می‌سازد. بی‌میله یا بی‌نماد ⇒ null: کلیکِ بی‌هدف رویِ فضایِ خالی
 * نباید درِ لاگ عددِ صفر یا تاریخِ جعلی بسازد.
 */
export function buildBarClick(input: ClickInput): ChartBarClick | null {
  const { symbol, timeframe, bar } = input;
  if (!bar || !Number.isFinite(bar.timestamp) || bar.timestamp <= 0) return null;
  if (!symbol) return null;

  const barDate = epochToJalali(bar.timestamp);
  // موتور ستاپ‌ها را با تاریخِ میلادیِ 'YYYY-MM-DD' می‌فرستد؛ همان تاریخ به جلالی
  // ترجمه می‌شود — تطبیقِ تقریبیِ ساعت درِ کار نیست.
  const jOf = (isoLike: string) => epochToJalali(Date.parse(`${isoLike}T00:00:00Z`));
  const engineSetups: EngineSetupRef[] = (input.setups ?? [])
    .filter((s) => typeof s.date === 'string' && jOf(s.date) === barDate)
    .map((s) => ({ kind: s.kind, label: s.label, price: s.price }));

  const hits = (input.overlays ?? []).filter((o) =>
    (o.points ?? []).some(
      (p) => typeof p.timestamp === 'number' && epochToJalali(p.timestamp) === barDate,
    ),
  );
  const marker = hits.length > 0 ? overlayLabel(hits[0]) ?? hits[0].name ?? null : null;
  const adj = (input.adjustments ?? []).find(
    (a) => Number.isFinite(a.timestamp) && epochToJalali(a.timestamp) === barDate,
  );

  return {
    key: `${symbol}|${timeframe}|${bar.timestamp}`,
    symbol,
    timeframe,
    barTs: bar.timestamp,
    barDate,
    kind: marker ? 'marker' : 'candle',
    marker,
    engineSetups,
    adjustRatio: adj ? adj.ratio : null,
    close: Math.round(bar.close * 100) / 100,
    atMs: input.atMs ?? Date.now(),
  };
}

/** یک خطِ خوانا برایِ UI — ارقامِ فارسی همین‌جا ساخته می‌شوند تا متنِ عدد ندرزد */
export function describeClick(e: ChartBarClick): string {
  const bits = [e.barDate];
  if (e.marker) bits.push(e.marker);
  for (const s of e.engineSetups) if (!bits.includes(s.label)) bits.push(s.label);
  if (e.adjustRatio != null) {
    bits.push(`تعدیلِ پایه ×${e.adjustRatio.toLocaleString('fa-IR', { maximumFractionDigits: 4 })}`);
  }
  return bits.join(' · ');
}
