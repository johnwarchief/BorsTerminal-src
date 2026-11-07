// تست چیدمانِ نقشۀ بازار: نسبتِ سطح باید همان نسبتِ داده باشد
//
// چرا این تست وجود دارد: مرجع (صفحۀ ۲ و ۱۲) مستطیل‌هایی می‌خواهد که «اندازه‌شان
// از معیارِ انتخابی می‌آید». اگر الگوریتم چیدمان مساحت را خراب کند، نقشه دقیقاً
// همان دروغی را می‌گوید که کل پنل برایِ فرارِ از آن ساخته شده — و هیچ تستِ
// مرورگریِ ساده‌ای آن را از روی screenshot نمی‌گیرد.
import { describe, expect, it } from 'vitest';
import {
  squarify,
  TREEMAP_LABEL_MIN_H,
  TREEMAP_LABEL_MIN_W,
  type TreemapItem,
} from '@features/market/lib/treemapLayout';

const area = (r: { w: number; h: number }) => r.w * r.h;

function items(values: [string, number][]): TreemapItem[] {
  return values.map(([key, value]) => ({ key, value }));
}

describe('squarify — حفظِ مساحت', () => {
  it('جمعِ مساحت‌ها ~۱ است (چیدمانِ کاملِ کادر)', () => {
    const { rects } = squarify(items([['a', 500], ['b', 300], ['c', 120], ['d', 80]]));
    expect(rects).toHaveLength(4);
    expect(rects.reduce((s, r) => s + area(r), 0)).toBeCloseTo(1, 6);
  });

  it('نسبتِ مساحتِ هر خانه با نسبتِ مقدارش یکی است', () => {
    const data = items([['a', 1000], ['b', 250], ['c', 100], ['d', 50]]);
    const { rects } = squarify(data);
    const total = 1400;
    const byKey = Object.fromEntries(rects.map((r) => [r.key, area(r)]));
    for (const [key, value] of [['a', 1000], ['b', 250], ['c', 100], ['d', 50]] as const) {
      expect(byKey[key] / value).toBeCloseTo(1 / total, 6);
    }
  });

  it('بدونِ همپوشانی و بیرون‌زدگی: هر خانه درِ [0,1]×[0,1]', () => {
    const { rects } = squarify(items(Array.from({ length: 24 }, (_u, i) => [`s${i}`, 24 - i])));
    for (const r of rects) {
      expect(r.x).toBeGreaterThanOrEqual(-1e-9);
      expect(r.y).toBeGreaterThanOrEqual(-1e-9);
      expect(r.x + r.w).toBeLessThanOrEqual(1 + 1e-9);
      expect(r.y + r.h).toBeLessThanOrEqual(1 + 1e-9);
    }
    // همپوشانیِ جفتی
    for (let i = 0; i < rects.length; i++) {
      for (let j = i + 1; j < rects.length; j++) {
        const a = rects[i];
        const b = rects[j];
        const ox = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x));
        const oy = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
        expect(ox * oy).toBeLessThan(1e-9);
      }
    }
  });

  it('مقادیرِ بی‌قدر حذف و شمرده می‌شوند (صفر خانۀ بی‌پیکسل نمی‌سازد)', () => {
    const { rects, dropped } = squarify(items([['a', 900], ['z', 0], ['n', NaN], ['q', -5], ['b', 100]]));
    expect(dropped).toBe(3);
    expect(rects.map((r) => r.key).sort()).toEqual(['a', 'b']);
  });

  it('همۀ صفر ⇒ چیدمانِ خالی، نه خانه‌هایِ تصادفی', () => {
    const { rects, dropped } = squarify(items([['a', 0], ['b', 0]]));
    expect(rects).toEqual([]);
    expect(dropped).toBe(2);
  });

  it('ترتیبِ نزولیِ ورودی حفظ می‌شود: بزرگ‌ترین خانه بیشترین مساحت', () => {
    const { rects } = squarify(items([['small', 1], ['big', 999]]));
    const big = rects.find((r) => r.key === 'big')!;
    const small = rects.find((r) => r.key === 'small')!;
    expect(area(big)).toBeGreaterThan(area(small));
  });

  it('ورودیِ بی‌مرتب هم همان مساحت‌ها را می‌دهد (چیدمان به ترتیبِ ورودی وابسته نیست)', () => {
    const a = squarify(items([['x', 120], ['y', 800], ['z', 40]]));
    const b = squarify(items([['z', 40], ['y', 800], ['x', 120]]));
    const sumA = Object.fromEntries(a.rects.map((r) => [r.key, area(r).toFixed(6)]));
    const sumB = Object.fromEntries(b.rects.map((r) => [r.key, area(r).toFixed(6)]));
    expect(sumA).toEqual(sumB);
  });

  it('تک‌مقدار کل کادر را می‌گیرد', () => {
    const { rects } = squarify(items([['only', 7]]));
    expect(rects).toEqual([{ key: 'only', x: 0, y: 0, w: 1, h: 1 }]);
  });

  it('خانه‌هایِ بسیار کوچک درِ دامنه‌یِ متن نمی‌افتند: آستانه‌ها معنا دارند', () => {
    expect(TREEMAP_LABEL_MIN_W).toBeGreaterThan(0);
    expect(TREEMAP_LABEL_MIN_H).toBeGreaterThan(0);
    const { rects } = squarify(items([['big', 1e6], ...Array.from({ length: 40 }, (_u, i) => [`t${i}`, 1] as [string, number])]));
    const tiny = rects.filter((r) => r.key !== 'big');
    expect(tiny.length).toBe(40);
    expect(tiny.every((r) => area(r) > 0)).toBe(true);
  });
});
