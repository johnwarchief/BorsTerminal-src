// features/technical/lib/priceAlerts.ts -- داوریِ هشدارها روی قیمتِ تازهٔ تابلو
// هیچ عددی اینجا ساخته نمی‌شود: بی‌قیمت ⇒ بی‌داوری. آستانه همیشه از استور
// می‌آید و همین‌جا فقط مقایسه می‌شود.
import type { PriceAlert } from '../stores/priceAlertStore';

export type AlertTick = {
  symbol?: string | null;
  p_last?: number | null;
  p_closing?: number | null;
};

/**
 * همان عددی که نوارِ بالایِ چارت نشان می‌دهد: آخرین قیمت، و اگر نبود قیمتِ پایانی.
 * صفر و منفی و NaN هیچ‌کدام قیمت نیستند ⇒ به سراغِ پایانی می‌رویم و اگر آن هم
 * نبود null. پیش از گشایشِ بازار p_last صفر است، نه «بی‌قیمتِ» نماد.
 */
export function tickPrice(row: AlertTick | null | undefined): number | null {
  if (!row) return null;
  const candidates = [row.p_last, row.p_closing];
  for (const p of candidates) {
    if (typeof p === 'number' && Number.isFinite(p) && p > 0) return p;
  }
  return null;
}

/** عبور از آستانه: «بالای» با برابر بودن هم شلیک می‌کند (برابر = عبور) */
export function crossed(alert: Pick<PriceAlert, 'side' | 'price'>, price: number): boolean {
  if (!Number.isFinite(price)) return false;
  return alert.side === 'above' ? price >= alert.price : price <= alert.price;
}

/**
 * idهای هشدارهایی که باید شلیک شوند. ردیف‌هایِ تکراریِ یک نماد: نخستین قیمتِ
 * معتبر؛ و نمادی که در فید نیست (تعطیل، حذف‌شده) بی‌صدا رد می‌شود.
 */
export function dueAlertIds(alerts: PriceAlert[], rows: readonly AlertTick[]): string[] {
  if (alerts.length === 0 || rows.length === 0) return [];
  const priceBySymbol = new Map<string, number>();
  for (const r of rows) {
    const s = typeof r.symbol === 'string' ? r.symbol.trim() : '';
    if (!s || priceBySymbol.has(s)) continue;
    const p = tickPrice(r);
    if (p != null) priceBySymbol.set(s, p);
  }
  const out: string[] = [];
  for (const a of alerts) {
    if (!a.active || a.firedAt != null) continue;
    const p = priceBySymbol.get(a.symbol);
    if (p == null) continue;
    if (crossed(a, p)) out.push(a.id);
  }
  return out;
}

/** متنِ یکِ هشدارِ شلیک‌شده برای بنر — همه‌چیز از خودِ هشدار، بدونِ حدس */
export function firedLabel(a: PriceAlert, price: number | null): string {
  const verb = a.side === 'above' ? 'بالا رفت از' : 'پایین آمد از';
  const now = price == null ? '' : ` (اکنون: ${Math.round(price).toLocaleString('fa-IR')})`;
  return `${a.symbol} — ${verb} ${Math.round(a.price).toLocaleString('fa-IR')} ریال${now}`;
}
