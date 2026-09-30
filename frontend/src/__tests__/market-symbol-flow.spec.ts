// تستِ سری درون‌روزِ حجم (P-03/#49): دلتای حجمِ انباشته، نه عددِ ساختگی
import { beforeEach, describe, expect, it } from 'vitest';
import {
  MAX_FLOW_BUCKETS,
  MAX_FLOW_SYMBOLS,
  SYMBOL_FLOW_KEY,
  applySample,
  minuteKey,
  readFlow,
  recordFlow,
  type FlowEntry,
} from '@features/market/lib/symbolFlow';

const DAY = '2026-09-30';

const EMPTY: FlowEntry = { last: null, buckets: [] };

describe('دلتای حجم از نمونه‌های انباشته', () => {
  it('نمونۀ اول هیچ باکتی نمی‌سازد (پایه نامعلوم است)', () => {
    const out = applySample(EMPTY, { t: '09:00', cumVol: 5000, price: 100 });
    expect(out.buckets).toEqual([]);
    expect(out.last).toEqual({ t: '09:00', cumVol: 5000, price: 100 });
  });

  it('دو نمونۀ متوالی ⇒ یک باکت به اندازهِ اختلاف', () => {
    const a = applySample(EMPTY, { t: '09:00', cumVol: 5000, price: 100 });
    const b = applySample(a, { t: '09:01', cumVol: 5400, price: 101 });
    expect(b.buckets).toEqual([{ t: '09:01', vol: 400, dir: 'up' }]);
  });

  it('همان دقیقه جمع می‌شود و جهتِ آخرین تغییر قیمت را می‌گیرد', () => {
    let e = applySample(EMPTY, { t: '09:00', cumVol: 1000, price: 100 });
    e = applySample(e, { t: '09:00', cumVol: 1600, price: 101 });
    e = applySample(e, { t: '09:00', cumVol: 2100, price: 99 });
    expect(e.buckets).toEqual([{ t: '09:00', vol: 1100, dir: 'down' }]);
  });

  it('دقیقۀ بی‌معامله باکت نمی‌سازد و شمارندۀ صفرشده دلتای منفی نمی‌دهد', () => {
    const a = applySample(EMPTY, { t: '09:00', cumVol: 9000, price: 100 });
    const b = applySample(a, { t: '09:01', cumVol: 9000, price: 100 });
    expect(b.buckets).toEqual([]);
    const c = applySample(b, { t: '09:02', cumVol: 200, price: 98 });
    expect(c.buckets).toEqual([]);
    expect(c.last).toEqual({ t: '09:02', cumVol: 200, price: 98 });
  });

  it('بی‌قیمت ⇒ جهت ندارد و خاکستری می‌ماند', () => {
    const a = applySample(EMPTY, { t: '09:00', cumVol: 100, price: null });
    const b = applySample(a, { t: '09:01', cumVol: 200, price: null });
    expect(b.buckets[0].dir).toBeNull();
  });

  it('سقف دقایق نگه داشته می‌شود و تازه‌ها می‌مانند', () => {
    let e: FlowEntry = EMPTY;
    for (let i = 0; i < MAX_FLOW_BUCKETS + 30; i++) {
      e = applySample(e, { t: `m${i}`, cumVol: 1000 + i * 10, price: 100 });
    }
    expect(e.buckets).toHaveLength(MAX_FLOW_BUCKETS);
    expect(e.buckets[e.buckets.length - 1].t).toBe(`m${MAX_FLOW_BUCKETS + 29}`);
  });
});

describe('کشِ نمادها', () => {
  beforeEach(() => localStorage.clear());

  it('ثبت و خواندن در یک روز', () => {
    recordFlow('شپنا', { t: '09:00', cumVol: 1000, price: 100 }, DAY, localStorage);
    const b = recordFlow('شپنا', { t: '09:01', cumVol: 1500, price: 101 }, DAY, localStorage);
    expect(b).toEqual([{ t: '09:01', vol: 500, dir: 'up' }]);
    expect(readFlow('شپنا', DAY, localStorage)).toEqual(b);
  });

  it('روزِ دیگر ⇒ سریِ دیروز دور ریخته می‌شود', () => {
    recordFlow('شپنا', { t: '09:01', cumVol: 1500, price: 101 }, DAY, localStorage);
    expect(readFlow('شپنا', '2026-10-01', localStorage)).toEqual([]);
  });

  it('سقفِ ده نماد: قدیمی‌ترین حذف می‌شود', () => {
    for (let i = 0; i < MAX_FLOW_SYMBOLS + 3; i++) {
      recordFlow(`نماد${i}`, { t: '09:01', cumVol: 1500, price: 101 }, DAY, localStorage);
    }
    const raw = JSON.parse(localStorage.getItem(SYMBOL_FLOW_KEY) as string) as {
      symbols: Record<string, unknown>;
    };
    expect(Object.keys(raw.symbols)).toHaveLength(MAX_FLOW_SYMBOLS);
    expect(readFlow('نماد0', DAY, localStorage)).toEqual([]);
  });

  it('کشِ خراب یا بی‌نماد داده را نمی‌شکند', () => {
    localStorage.setItem(SYMBOL_FLOW_KEY, '{not json');
    expect(readFlow('شپنا', DAY, localStorage)).toEqual([]);
    expect(recordFlow('', { t: '09:00', cumVol: 1, price: 1 }, DAY, localStorage)).toEqual([]);
  });

  it('minuteKey دقیقاً HH:MM می‌دهد', () => {
    expect(minuteKey(new Date(2026, 8, 30, 9, 5))).toBe('09:05');
  });
});
