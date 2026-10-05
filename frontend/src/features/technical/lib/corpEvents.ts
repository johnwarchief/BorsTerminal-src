// features/technical/lib/corpEvents.ts -- نگاشتِ واحدِ «رویدادِ شرکتیِ مبدأ» به نشانگر
// هر دو موتورِ چارت (klinecharts و FFC) همین تابع را می‌خوانند: نوع، حرف، رنگ و
// متنِ تولتیپ از payloadِ سرور درمی‌آید و هیچ‌جا دوباره نوشته نمی‌شود.
// اینجا هیچ ضریبِ تعدیلِ تازه‌ای حساب نمی‌شود — نمایشِ محض. ضریبِ همان جدولِ مبدأ
// («تعدیل‌شده ÷ خامِ همان روز») با ضریبِ زنجیرۀ کشف‌شدۀ پیشین («پایۀ امروز ÷
// پایانیِ دیروز») دو تعریفِ متفاوت است و هرگز در هم نمی‌ریزد: این نشانگر وارد
// `applyAdjustmentToCandles` نمی‌شود.
import type { ChartOverlaySpec } from '../engine/types';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';

export type CorpEventType = 'priceAdjust' | 'shareChange';

/** همان شکلی که `/api/chart*` درِ `corporateEvents` می‌فرستد (canonicalِ TSETMC) */
export type RawCorporateEvent = {
  date?: string | null;
  type?: string | null;
  from?: number | null;
  to?: number | null;
  source?: string | null;
};

export const CORP_EVENT_GROUP = 'fts-corp-events';

/** دو نوع، دو نشانِ روشن — کاربر با یک نگاه تفکیکشان کند.
 *  رنگ‌ها از پالتِ خودِ چارت (کهرباییِ #f59e0b/#fbbf24، فیروزه‌ایِ #22d3ee،
 *  سبزِ #10b981، قرمزِ #ff3860) دوری می‌کنند: هم با نشانگرِ زنجیرۀ تعدیل
 *  قاطی نشود، هم سنجشِ پیکسلی بتواند هر نوع را جدا بشمارد. */
const VISUAL: Record<CorpEventType, { letter: string; color: string; name: string }> = {
  priceAdjust: { letter: 'ت', color: '#a855f7', name: 'تعدیلِ پایانی' },
  shareChange: { letter: 'س', color: '#2dd4bf', name: 'تغییرِ سهام' },
};

/** واحدِ «چند سهم» — سهامِ میلیاردی با fmtInt خوانده نمی‌شود (گرد می‌شود) */
function shares(n: number): string {
  if (Math.abs(n) >= 1e9) return `${toFaDigits((n / 1e9).toFixed(1))} میلیارد`;
  if (Math.abs(n) >= 1e6) return `${toFaDigits((n / 1e6).toFixed(1))} میلیون`;
  return fmtInt(n);
}

export function corpEventType(ev: RawCorporateEvent): CorpEventType | null {
  return ev.type === 'priceAdjust' || ev.type === 'shareChange' ? ev.type : null;
}

/** متنِ تولتیپ: رویداد چه بود، از چه به چه، و مبدأ کدام است */
export function corpEventText(ev: RawCorporateEvent): string {
  const kind = corpEventType(ev);
  if (!kind) return '';
  const v = VISUAL[kind];
  const from = typeof ev.from === 'number' && Number.isFinite(ev.from) ? ev.from : null;
  const to = typeof ev.to === 'number' && Number.isFinite(ev.to) ? ev.to : null;
  if (from == null || to == null) return `${v.name} · مبدأ: TSETMC`;
  const shown = kind === 'shareChange' ? shares : (n: number) => fmtInt(n);
  return `${v.name} · ${shown(from)} ← ${shown(to)}`;
}

export function corpEventLetter(kind: CorpEventType): string {
  return VISUAL[kind].letter;
}

export function corpEventColor(kind: CorpEventType): string {
  return VISUAL[kind].color;
}

/** برچسبِ یک رویدادِ اخیر برایِ سایدبار/مستر — همان نگاشتِ نشانگر، بی‌نقشهٔ دوم */
export function corpEventChipLabel(ev: RawCorporateEvent): string | null {
  const kind = corpEventType(ev);
  return kind ? `${VISUAL[kind].name} (${toFaDigits(ev.date ?? '')})` : null;
}

export type CorpMarkerInput = {
  events: readonly RawCorporateEvent[];
  /** «YYYY-MM-DD» → timestampِ کندل، یا null اگر آن روز درِ سری نیست */
  tsForDate: (date: string) => number | null;
  /** جایِ عمودیِ نشانگر رویِ همان کندل (کفِ کندل)، یا null اگر نیست */
  valueForDate: (date: string) => number | null;
};

/** رویدادهایِ *نشست‌هایِ پیشِ رو* — تازه‌ترینِ هر نوع. بیشتر از دو تا نمی‌شود
 *  وگرنه «زمینه» به فهرستِ بلندِ تاریخ تبدیل می‌شود. */
export function recentCorpEvents(events: readonly RawCorporateEvent[], days = 45): RawCorporateEvent[] {
  const cutoff = new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10);
  const byType = new Map<string, RawCorporateEvent>();
  for (const ev of events) {
    const kind = corpEventType(ev);
    const date = typeof ev.date === 'string' ? ev.date.slice(0, 10) : null;
    if (!kind || !date || date < cutoff) continue;
    const seen = byType.get(kind);
    if (!seen || String(seen.date) < date) byType.set(kind, ev);
  }
  return [...byType.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

export type CorpMarker = ChartOverlaySpec & {
  /** حرفِ نشانگر (ت/س) — موتورِ klinecharts دورِ دایره می‌نویسدش */
  letter: string;
};

/** تنها نگاشتِ مجاز: payloadِ canonical → نشانه‌ها (بی‌محاسبهٔ دوم) */
export function corpEventMarkers(i: CorpMarkerInput): CorpMarker[] {
  const out: CorpMarker[] = [];
  for (const ev of i.events) {
    const kind = corpEventType(ev);
    const date = typeof ev.date === 'string' ? ev.date.slice(0, 10) : null;
    if (!kind || !date) continue;
    const ts = i.tsForDate(date);
    const value = i.valueForDate(date);
    if (ts == null || value == null) continue;
    out.push({
      id: `corp-${kind}-${date}`,
      kind: 'marker',
      group: CORP_EVENT_GROUP,
      points: [{ timestamp: ts, value }],
      color: corpEventColor(kind),
      label: corpEventText(ev),
      letter: corpEventLetter(kind),
    });
  }
  return out;
}
