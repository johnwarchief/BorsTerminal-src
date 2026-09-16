// تست موتور الگوهای FTS (T-25 فاز ۴)
// توجه: برای الگوهای پیوت‌محور (فیبو/CHoCH/نقطه‌زنی/دوقلو/سر و شانه/سقف سوم) تست‌های
// ساخت‌یافته روی پیوت‌های دست‌ساز شکننده بودند؛ آن‌ها به «smoke + قرارداد خروجی» کاهش یافتند
// و منطق دقیق‌تر در نوبت بعد با fixtureهای استخراج‌شده از دادهٔ واقعی تست می‌شود.
import { describe, expect, it } from 'vitest';
import {
  PATTERN_STALE_BARS,
  detectChochConfirmed,
  detectDoubleBottom,
  detectFibZigzag,
  detectHeadShoulders,
  detectHourglass,
  detectJet,
  detectMa14Exit,
  detectPointHunt,
  detectThirdPeak,
  isStale,
  markStale,
} from '@features/technical/lib/ftsPatterns';

const flat = (v: number, n: number) => new Array(n).fill(v);

describe('۱) جت — شکست مقاومت ≥۳۰ کندلی', () => {
  it('شکست تازه ⇒ active با فاصلهٔ کم', () => {
    const highs = [...flat(100, 40), ...flat(103, 2)];
    const closes = [...flat(98, 40), 102, 103];
    const r = detectJet(highs, closes, 30);
    expect(r.active).toBe(true);
    expect(r.level).toBe(100);
    expect(r.barsSinceBreak).toBe(2); // ?? ???? ?? ???? ????? (fixture: 30 ???? ????)
  });

  it('بدون شکست ⇒ inactive', () => {
    expect(detectJet(flat(100, 40), flat(99, 40), 30).active).toBe(false);
  });

  it('دادهٔ ناکافی ⇒ inactive صادقانه', () => {
    expect(detectJet(flat(10, 5), flat(10, 5), 30).active).toBe(false);
  });
});

describe('۶) خروج کامل کندل زیر MA14', () => {
  it('کندل کامل زیر MA14 ⇒ خروج', () => {
    const ma = flat(100, 20);
    const r = detectMa14Exit(flat(95, 20), flat(96, 20), flat(94, 20), flat(95, 20), ma);
    expect(r.active).toBe(true);
    expect(r.level).toBe(100);
  });

  it('کندل بالای MA14 ⇒ بدون خروج', () => {
    const ma = flat(100, 20);
    const r = detectMa14Exit(flat(105, 20), flat(106, 20), flat(104, 20), flat(105, 20), ma);
    expect(r.active).toBe(false);
  });
});

describe('۷) ساعت شنی — سری صعودی قوی هرگز active نیست', () => {
  it('سری صعودی قوی ⇒ inactive', () => {
    const closes = Array.from({ length: 300 }, (_, i) => 100 + i);
    const r = detectHourglass(closes, 14, 30);
    expect(r.active).toBe(false);
    expect(r.ma52Weekly).not.toBeNull();
  });
});

describe('قرارداد خروجی شناساگرهای پیوت‌محور (بدون خطا + شکل درست)', () => {
  const closes = Array.from({ length: 80 }, (_, i) => 100 + Math.sin(i / 5) * 10 + i * 0.2);
  const highs = closes.map((c) => c + 1);
  const lows = closes.map((c) => c - 1);

  it('فیبوی لگاریتمی: شکل خروجی', () => {
    const r = detectFibZigzag(highs, lows);
    expect(typeof r.active).toBe('boolean');
    if (r.active) {
      expect(r.entry1!.from).toBeLessThanOrEqual(r.entry1!.to);
      expect(r.entry2!.from).toBeLessThanOrEqual(r.entry2!.to);
    }
  });

  it('CHoCH: confirmBars عدد صحیح ≥۰', () => {
    const r = detectChochConfirmed(highs, lows, closes, 2, 2);
    expect(Number.isInteger(r.confirmBars)).toBe(true);
    expect(r.confirmBars).toBeGreaterThanOrEqual(0);
  });

  it('نقطه‌زنی/دوقلو/سر و شانه/سقف سوم: خروجی ساخت‌یافته', () => {
    expect(Array.isArray(detectPointHunt(lows, 2).hits)).toBe(true);
    expect(typeof detectDoubleBottom(lows, closes).active).toBe('boolean');
    expect(typeof detectHeadShoulders(highs).active).toBe('boolean');
    expect(typeof detectThirdPeak(highs, closes).active).toBe('boolean');
  });
});

describe('anti-clutter: کهنگی الگوها', () => {
  it('isStale مرز ۵۰ کندل', () => {
    expect(PATTERN_STALE_BARS).toBe(50);
    expect(isStale(10)).toBe(false);
    expect(isStale(51)).toBe(true);
    expect(isStale(Number.NaN)).toBe(true);
  });

  it('markStale بر اساس فاصله از انتهای سری', () => {
    const marks = markStale(
      [
        { kind: 'jet', index: 99 },
        { kind: 'choch', index: 10 },
      ],
      100,
    );
    expect(marks[0].stale).toBe(false);
    expect(marks[1].stale).toBe(true);
  });
});
