// دکمهٔ دانلودِ جدولِ تابلوخوانی — «آنچه می‌بینی همان است که دانلود می‌شود».
// چکِ اصلی: ستون‌هایِ فایل با سرستون‌هایِ جدول یکی‌اند، ترتیبِ ردیف‌ها همان
// مرتب‌سازیِ روی صفحه است، و اعداد خام می‌روند نه رقمِ فارسی (وگرنه Excel
// آن‌ها را عدد نمی‌شناسد و جمع/فیلتر نمی‌شود).
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { TapeTable } from '@features/market/components/TapeTable';
import type { MarketRow } from '@shared/types/marketRow';

const BOM = String.fromCharCode(0xfeff);

const mk = (symbol: string, over: Partial<MarketRow> = {}): MarketRow =>
  ({
    symbol,
    name: symbol,
    p_last: 1000,
    p_closing: 990,
    percent_change: 1.5,
    percent_last: 2.5,
    tvol: 5000,
    z_tot_tran: 40,
    q_tot_cap: 2e9,
    vol_ratio: 3,
    buyer_power: 1.4,
    ...over,
  }) as unknown as MarketRow;

function rowsOf(blob: Blob) {
  return blob.text().then((t) => t.replace(BOM, '').split('\r\n').filter(Boolean));
}

function renderTape(rows: MarketRow[]) {
  return render(
    <TapeTable rows={rows} selected="" onSelect={() => {}} />,
  );
}

describe('دانلودِ جدولِ تابلوخوانی', () => {
  it('دکمه با شمارِ ردیفِ دیدنی رندر می‌شود', () => {
    renderTape([mk('الف'), mk('ب')]);
    const btn = screen.getByTestId('download-tape-rows');
    expect(btn.getAttribute('data-count')).toBe('2');
  });

  it('جدولِ خالی دکمه را غیرفعال می‌کند (نه فایلِ خالی)', () => {
    renderTape([]);
    // جدولِ بی‌ردیف EmptyState می‌دهد و اصلاً نوارِ ابزار ندارد
    expect(screen.queryByTestId('download-tape-rows')).toBeNull();
  });

  it('ستون‌هایِ فایل همان سرستون‌هایِ جدول‌اند و اعداد خام‌اند', async () => {
    const spy = vi.fn();
    const orig = URL.createObjectURL;
    URL.createObjectURL = spy.mockReturnValue('blob:x') as unknown as typeof orig;
    URL.revokeObjectURL = (() => {}) as unknown as typeof URL.revokeObjectURL;
    try {
      renderTape([mk('الف', { vol_ratio: 9 }), mk('ب', { vol_ratio: 2 })]);
      fireEvent.click(screen.getByTestId('download-tape-rows'));
      const blob = (spy.mock.calls as unknown as unknown[][])[0][0] as Blob;
      const lines = await rowsOf(blob);

      // خطِ ۰ راهنمایِ Excel، خطِ ۱ سرستون‌ها
      expect(lines[0]).toBe('sep=;');
      const head = lines[1].split(';');
      const domHead = Array.from(
        document.querySelectorAll('[data-testid="tape-head"] > *'),
      ).map((el) => (el.textContent ?? '').trim());
      expect(head.length).toBe(domHead.length);
      expect(head[0]).toBe('نماد');

      // مرتب‌سازیِ پیش‌فرض vol_ratio نزولی ⇒ «الف» (۹) پیش از «ب» (۲)
      expect(lines[2].split(';')[0]).toBe('الف');
      expect(lines[3].split(';')[0]).toBe('ب');

      // ستونِ «اختلاف٪» درصد است نه کسر: (1000-990)/990*100 = 1.01
      const diffIdx = head.indexOf('اختلاف٪');
      expect(diffIdx).toBeGreaterThan(-1);
      expect(Number(lines[2].split(';')[diffIdx])).toBeCloseTo(1.01, 2);

      // ارزش به میلیارد ریال تبدیل شده (2e9 ریال ⇒ 2)
      const valIdx = head.indexOf('ارزش');
      expect(Number(lines[2].split(';')[valIdx])).toBe(2);

      // هیچ رقمِ فارسی‌ای در بدنه نیست — وگرنه Excel عدد نمی‌بیند
      expect(/[\u06f0-\u06f9]/.test(lines[2])).toBe(false);
    } finally {
      URL.createObjectURL = orig;
    }
  });
});
