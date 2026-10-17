// features/portfolio/stores/sarkhatiFormStore.ts — حالَتِ فرمِ سرخطی، نماد‌به‌نماد
//
// چرا این فایل هست: «سرخطی» حالا یکِ تبِّ مستقل است و کاربر درِ آن یکِ فرم را
// می‌بندد، به تبِّ دیگری می‌رود و برمی‌گردد. اگر حالَتِ فرم درِ حافظۀِ مؤلفه
// باشد، هر بازگشت یعنی فرمِ خالی — و این دقیقاً همان «پاک‌کردنِ بی‌دلیل» است که
// مأموریت منع می‌کند. ولی **تأیید** و **عبارتِ تأیید** و **execution_id** اینجا
// نمی‌نشینند: آن‌ها یک‌مصرف‌اند و ماندنشان یعنی عبورِ یکِ رأیِ قدیمی ازِ گیتِ
// تازه (همان قاعدۀ confirm_epoch درِ بک‌اند).
//
// کلیدِ ذخیره خودِ نماد است: رفتن از «فولاد» به «شپنا» قیمتِ فولاد را زیرِ
// شپنا نمی‌گذارد. و همه‌چیز درِ sessionStorage می‌ماند — با بستنِ تب می‌میرد،
// با reload می‌ماند، و هیچ‌جا به سرور یا دیسکِ کاربر نوشته نمی‌شود.
import { create } from 'zustand';

const KEY = ['bors', 'sarkhati', 'form'].join('-');

export type SarkhatiSide = 'buy' | 'sell';

export type OrderFields = {
  side: SarkhatiSide;
  price: string;
  quantity: string;
  /** هدفِ ارسال (قالبِ datetime-local، ساعتِ دیواریِ همین دستگاه) — خالی = فوری */
  targetLocal: string;
  /** پیش‌افتِ یک‌طرفه بر حسبِ میلی‌ثانیه؛ رشته تا «خالی» با «صفر» یکی بماند */
  oneWayMs: string;
  marginMs: string;
};

export const EMPTY_FIELDS: OrderFields = {
  side: 'buy', price: '', quantity: '', targetLocal: '', oneWayMs: '', marginMs: '',
};

type State = {
  bySymbol: Record<string, OrderFields>;
  set: (symbol: string, patch: Partial<OrderFields>) => void;
  drop: (symbol: string) => void;
};

function readSession(): Record<string, OrderFields> {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, Partial<OrderFields>>;
    const out: Record<string, OrderFields> = {};
    for (const [sym, v] of Object.entries(parsed)) {
      if (typeof sym !== 'string') continue;
      out[sym] = { ...EMPTY_FIELDS, ...v };
    }
    return out;
  } catch {
    return {};
  }
}

function writeSession(bySymbol: Record<string, OrderFields>): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(bySymbol));
  } catch {
    /* تبهایِ بی‌storage: فقط درِ حافظه می‌ماند، بی‌صدا و بی‌خطایِ صفحه */
  }
}

export const useSarkhatiFormStore = create<State>((set, get) => ({
  bySymbol: readSession(),
  set: (symbol, patch) => {
    if (!symbol) return;
    const next = { ...get().bySymbol, [symbol]: { ...(get().bySymbol[symbol] ?? EMPTY_FIELDS), ...patch } };
    writeSession(next);
    set({ bySymbol: next });
  },
  drop: (symbol) => {
    const next = { ...get().bySymbol };
    delete next[symbol];
    writeSession(next);
    set({ bySymbol: next });
  },
}));

export function fieldsFor(symbol: string): OrderFields {
  return useSarkhatiFormStore.getState().bySymbol[symbol] ?? EMPTY_FIELDS;
}

/**
 * `datetime-local` ← epoch msِ دیواری. رشتهٔ خالی `null` می‌شود (نه ۰، نه «اکنون»):
 * «هدفی نیست» با «هدفِ صفر» دو چیزند و بک‌اند هم همین تفکیک را می‌خواهد.
 */
export function targetWallMs(local: string): number | null {
  const v = (local || '').trim();
  if (!v) return null;
  const t = Date.parse(v);
  return Number.isFinite(t) ? t : null;
}

/** پیش‌افتِ اعمالی: فقط عددِ مثبت؛ رشتهٔ خالی یعنی «خودِ سرویس تعیین کند» */
export function leadMs(raw: string): number | undefined {
  const n = Number((raw || '').replace(/[٬]/g, '').trim());
  return Number.isFinite(n) && n > 0 ? n : undefined;
}
