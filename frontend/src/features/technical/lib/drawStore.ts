// features/technical/lib/drawStore.ts -- ماندگاری ترسیم‌ها + Undo/Redo + اسنپ مگنت (فاز ۳)
// خالص و تست‌پذیر: کلید ذخیره‌سازی شامل نماد و تایم‌فریم است تا هر نماد ترسیم‌های خودش را
// داشته باشد. هیچ mock/دادهٔ ساختگی؛ در نبود localStorage به‌صورت بی‌صدا بی‌اثر می‌شود.

export type StoredPoint = { timestamp: number; value?: number };
export type StoredOverlay = {
  name: string;
  groupId?: string;
  points?: StoredPoint[];
  styles?: Record<string, unknown>;
  extendData?: Record<string, unknown>;
};

const PREFIX = 'fts-draw';
export const SYMBOL_DRAW_PREFIX = 'fts.drawings.v1';

/** کلید استاندارد ذخیره‌سازی اختصاصی هر نماد (fts.drawings.v1.{symbol}) */
export function symbolDrawKey(symbol: string): string {
  return `${SYMBOL_DRAW_PREFIX}.${symbol || '__market__'}`;
}

/** کلید ذخیره‌سازی برای یک نماد/تایم‌فریم (نماد خالی ⇒ کل بورس) */
export function drawKey(symbol: string, timeframe: string): string {
  return `${PREFIX}:${symbol || '__market__'}:${timeframe || 'day'}`;
}

function storage(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch {
    return null;
  }
}

/** خواندن ترسیم‌های اختصاصی نماد از کلید استاندارد fts.drawings.v1.{symbol} */
export function loadSymbolDrawings(symbol: string): StoredOverlay[] {
  const s = storage();
  if (!s) return [];
  try {
    const raw = s.getItem(symbolDrawKey(symbol));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((o): o is StoredOverlay => !!o && typeof (o as StoredOverlay).name === 'string');
  } catch {
    return [];
  }
}

/** ذخیرهٔ ترسیم‌های اختصاصی نماد در کلید استاندارد fts.drawings.v1.{symbol} */
export function saveSymbolDrawings(symbol: string, drawings: StoredOverlay[]): void {
  const s = storage();
  if (!s) return;
  try {
    const clean = drawings.filter((d) => d && typeof d.name === 'string');
    if (clean.length === 0) {
      s.removeItem(symbolDrawKey(symbol));
    } else {
      s.setItem(symbolDrawKey(symbol), JSON.stringify(clean));
    }
  } catch {
    // حافظه در دسترس نیست
  }
}

/** خواندن ترسیم‌های ذخیره‌شده بر اساس نماد و تایم‌فریم (شکل نامعتبر ⇒ آرایهٔ خالی) */
export function loadDrawings(symbol: string, timeframe?: string): StoredOverlay[] {
  const s = storage();
  if (!s) return [];
  try {
    if (timeframe) {
      const raw = s.getItem(drawKey(symbol, timeframe));
      if (!raw) return [];
      const parsed = JSON.parse(raw) as unknown;
      if (!Array.isArray(parsed)) return [];
      return parsed.filter((o): o is StoredOverlay => !!o && typeof (o as StoredOverlay).name === 'string');
    }
    return loadSymbolDrawings(symbol);
  } catch {
    return [];
  }
}

/** ذخیرهٔ ترسیم‌ها بر مبنای نماد و تایم‌فریم */
export function saveDrawings(symbol: string, timeframe: string, drawings: StoredOverlay[]): void {
  const s = storage();
  if (!s) return;
  try {
    const clean = drawings.filter((d) => d && typeof d.name === 'string');
    if (clean.length === 0) {
      s.removeItem(drawKey(symbol, timeframe));
    } else {
      s.setItem(drawKey(symbol, timeframe), JSON.stringify(clean));
    }
  } catch {
    // حافظه در دسترس نیست
  }
}

/** پاک‌کردن ترسیم‌های «این نماد» در همهٔ تایم‌فریم‌ها و کلید نماد (دکمهٔ پاک‌سازی) */
export function clearSymbolDrawings(symbol: string): number {
  const s = storage();
  if (!s) return 0;
  const prefix = `${PREFIX}:${symbol || '__market__'}:`;
  const keys: string[] = [];
  try {
    for (let i = 0; i < s.length; i++) {
      const k = s.key(i);
      if (k && k.startsWith(prefix)) keys.push(k);
    }
    keys.forEach((k) => s.removeItem(k));
    s.removeItem(symbolDrawKey(symbol));
  } catch {
    return 0;
  }
  return keys.length;
}

/** پشتهٔ سادهٔ Undo/Redo روی snapshotها (آرایهٔ ترسیم‌ها) */
export type History<T> = { past: T[]; present: T; future: T[] };

export function initHistory<T>(present: T): History<T> {
  return { past: [], present, future: [] };
}

/** ثبت وضعیت جدید؛ با ثبت جدید، آینده پاک می‌شود */
export function commit<T>(h: History<T>, next: T): History<T> {
  return { past: [...h.past, h.present], present: next, future: [] };
}

export function canUndo<T>(h: History<T>): boolean {
  return h.past.length > 0;
}

export function canRedo<T>(h: History<T>): boolean {
  return h.future.length > 0;
}

export function undo<T>(h: History<T>): History<T> {
  if (!canUndo(h)) return h;
  const prev = h.past[h.past.length - 1];
  return { past: h.past.slice(0, -1), present: prev, future: [h.present, ...h.future] };
}

export function redo<T>(h: History<T>): History<T> {
  if (!canRedo(h)) return h;
  const next = h.future[0];
  return { past: [...h.past, h.present], present: next, future: h.future.slice(1) };
}

/** اسنپ مگنت: اگر قیمت به OHLC همان کندل نزدیک‌تر از آستانهٔ نسبت% باشد، به آن قفل شود */
export function snapToOhlc(
  price: number,
  candle: { open: number; high: number; low: number; close: number } | null,
  thresholdPct = 0.4,
): { price: number; snapped: boolean; target?: 'open' | 'high' | 'low' | 'close' } {
  if (!candle || !Number.isFinite(price) || price <= 0) return { price, snapped: false };
  const threshold = (Math.abs(price) * thresholdPct) / 100;
  const candidates: { k: 'open' | 'high' | 'low' | 'close'; v: number }[] = [
    { k: 'open', v: candle.open },
    { k: 'high', v: candle.high },
    { k: 'low', v: candle.low },
    { k: 'close', v: candle.close },
  ];
  let best: { k: 'open' | 'high' | 'low' | 'close'; v: number; d: number } | null = null;
  for (const c of candidates) {
    if (!Number.isFinite(c.v)) continue;
    const d = Math.abs(c.v - price);
    if (d <= threshold && (best == null || d < best.d)) best = { ...c, d };
  }
  return best ? { price: best.v, snapped: true, target: best.k } : { price, snapped: false };
}
