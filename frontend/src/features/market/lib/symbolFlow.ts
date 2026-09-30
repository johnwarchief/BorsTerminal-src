// features/market/lib/symbolFlow.ts -- سری درون‌روزِ حجمِ یک نماد، از دلتای تابلو
// بانک بازار فقط «آخرین لحظهٔ» هر نماد را نگه می‌دارد (market_watch کلیدش ins_code
// است و تاریخچهٔ دقیقه‌ای ندارد؛ رأیِ مالک بند ۴: TSETMC تاریخچۀ دقیقه‌ای نمی‌دهد).
// پس تنها منبعِ صادق، همان ردیفِ تابلویی است که هر پولینگ می‌آید: حجمِ چاپ‌شدۀ
// انباشته (q_tot_tran) کم می‌شود از نمونهٔ قبلی و به دقیقۀ همان نمونه می‌نشیند.
// بیرون از ساعتِ بازار چیزی ثبت نمی‌شود و غایب همان «بدون داده» می‌ماند.
import { dayKey } from './intradayCache';

export const SYMBOL_FLOW_KEY = 'bors:market:symflow:v1';
/** سقف نمادهای نگه‌داشته‌شده در کش (LFU ساده: قدیمی‌ترین حذف می‌شود) */
export const MAX_FLOW_SYMBOLS = 10;
/** سقف دقایق هر نماد — کل نشست ۲۲۵ دقیقه است */
export const MAX_FLOW_BUCKETS = 240;

export type FlowSample = { t: string; cumVol: number; price: number | null };
export type FlowBucket = { t: string; vol: number; dir: 'up' | 'down' | null };
export type FlowEntry = { last: FlowSample | null; buckets: FlowBucket[] };
type FlowStore = { day: string; symbols: Record<string, FlowEntry> };

/** «HH:MM» از شیء تاریخِ محلی */
export function minuteKey(d: Date = new Date()): string {
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function emptyStore(day: string): FlowStore {
  return { day, symbols: {} };
}

function readStore(day: string, storage?: Storage): FlowStore {
  const st = storage ?? (typeof localStorage === 'undefined' ? undefined : localStorage);
  if (!st) return emptyStore(day);
  let raw: string | null = null;
  try {
    raw = st.getItem(SYMBOL_FLOW_KEY);
  } catch {
    return emptyStore(day);
  }
  if (!raw) return emptyStore(day);
  try {
    const parsed = JSON.parse(raw) as FlowStore;
    if (!parsed || typeof parsed !== 'object' || parsed.day !== day || !parsed.symbols) {
      // روزِ تازه ⇒ سریِ دیروز بی‌ارزش است؛ دور ریخته می‌شود نه ادغام
      return emptyStore(day);
    }
    return parsed;
  } catch {
    return emptyStore(day);
  }
}

function writeStore(store: FlowStore, storage?: Storage): void {
  const st = storage ?? (typeof localStorage === 'undefined' ? undefined : localStorage);
  if (!st) return;
  try {
    st.setItem(SYMBOL_FLOW_KEY, JSON.stringify(store));
  } catch {
    /* کشِ پر یا خاموش — سری درون‌روزی دادهٔ از‌دست‌رفته‌داشتنی است */
  }
}

/** دلتای انباشته‌شده به یک دقیقه؛ نمونهٔ هم‌دقیقه رویِ آخرین باکت می‌نشیند */
export function applySample(entry: FlowEntry, s: FlowSample): FlowEntry {
  const buckets = entry.buckets.slice();
  const head = buckets[buckets.length - 1];
  const prev = entry.last;
  const dir: FlowBucket['dir'] =
    prev?.price != null && s.price != null
      ? s.price > prev.price
        ? 'up'
        : s.price < prev.price
          ? 'down'
          : null
      : null;

  if (prev && s.cumVol < prev.cumVol) {
    // شمارشگر از صفر شده (نشست/اصلاحِ سایت) — دلتای منفی هرگز حجم نیست
    return { last: s, buckets };
  }
  const delta = prev ? Math.max(0, s.cumVol - prev.cumVol) : 0;

  if (head && head.t === s.t) {
    buckets[buckets.length - 1] = { t: head.t, vol: head.vol + delta, dir: dir ?? head.dir };
  } else if (delta > 0) {
    buckets.push({ t: s.t, vol: delta, dir });
  }
  const trimmed = buckets.length > MAX_FLOW_BUCKETS ? buckets.slice(-MAX_FLOW_BUCKETS) : buckets;
  return { last: s, buckets: trimmed };
}

export function readFlow(symbol: string, day = dayKey(), storage?: Storage): FlowBucket[] {
  if (!symbol) return [];
  return readStore(day, storage).symbols[symbol]?.buckets ?? [];
}

/** ثبتِ یک نمونه و برگرداندنِ سریِ تازهٔ همان نماد */
export function recordFlow(
  symbol: string,
  sample: FlowSample,
  day = dayKey(),
  storage?: Storage,
): FlowBucket[] {
  if (!symbol) return [];
  const store = readStore(day, storage);
  const entry = store.symbols[symbol] ?? { last: null, buckets: [] };
  const next = applySample(entry, sample);
  const symbols: Record<string, FlowEntry> = { ...store.symbols, [symbol]: next };
  const keys = Object.keys(symbols);
  for (const k of keys.slice(0, Math.max(0, keys.length - MAX_FLOW_SYMBOLS))) delete symbols[k];
  writeStore({ day, symbols }, storage);
  return next.buckets;
}
