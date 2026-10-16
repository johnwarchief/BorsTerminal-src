// __tests__/market-mobile-view.spec.tsx -- نمایِ کارتِ تابلو درِ گوشی (بندِ ۲.۱)
//
// سطح: تستِ UI (jsdom). چیزی که اینجا سنجیده می‌شود «اثرِ انتخابِ نما» است، نه
// حضورِ یکِ کلاسِ CSS: درِ عرضِ گوشی باید کارت‌ها بیایند، جدولِ ۱۱۵۰پیکسلیِ افقی
// نرود، چهار دانۀِ خواستۀِ مالک (نماد/قیمت/درصدِ تغییر/ارزش) درِ هرِ کارت باشد،
// مرتب‌سازی همانِ کلیدهایِ خودِ تابلو را بهِ کار ببرد وِ کلیکِ کارت همانِ onSelect
// ردیفِ دسکتاپ را صدا بزند. کلیدِ «جدولِ کامل» هم باید همانِ جدولِ همیشگی را
// برگرداند (هیچِ داده‌ای پشتِ اصلاحِ اسکرول پنهان نمی‌شود).
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { TapeTable } from '@features/market/components/TapeTable';

// jsdom اندازه ندارد؛ virtualizer را به رندرِ همهٔ سطرها وادار می‌کنیم (همانِ
// تکنیکِ market-components.spec.tsx) تاِ «کارتِ اول/دوم/سوم» درِ آزمون واقعی باشد.
vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: ({ count, estimateSize }: { count: number; estimateSize: () => number }) => ({
    getVirtualItems: () => Array.from({ length: count }, (_, i) => {
      const size = estimateSize();
      return { index: i, start: i * size, size, key: String(i), lane: 0 } as never;
    }),
    getTotalSize: () => count * estimateSize(),
  }),
}));

/**
 * `useMediaQuery` خودِ محصول ازِ `window.matchMedia` می‌خواند؛ اینِ mock فقطِ
 * «گوشی است / نیست» را عوض می‌کند وِ هیچِ رفتارِ دیگری را دست‌کاری نمی‌کند.
 */
let mobile = true;
vi.mock('@shared/lib/useMediaQuery', () => ({ useMediaQuery: () => mobile }));

function row(over: Partial<MarketRow> = {}): MarketRow {
  return {
    symbol: 'شپنا', name: 'پتروشیمی پارس', p_last: 1040, p_closing: 1000,
    percent_change: 4.2, percent_last: 3.1, tvol: 250_000, z_tot_tran: 320,
    q_tot_cap: 2.6e11, vol_ratio: 2.4, buyer_power: 0.62, ins_code: '7745894403636165',
    ...over,
  } as MarketRow;
}

const ROWS = [
  row(),
  row({ symbol: 'فولاد', name: 'فولاد مبارکه اصفهان', p_last: 5170, percent_change: -1.8,
        q_tot_cap: 9.4e11, tvol: 1_200_000, vol_ratio: 0.9 }),
  row({ symbol: 'خودرو', name: 'سازمان صنایع خودروسازی', p_last: 312, percent_change: 0,
        q_tot_cap: 1.1e11, tvol: 80_000, vol_ratio: 6.1 }),
];

beforeEach(() => {
  mobile = true;
});

describe('نمایِ کارتِ تابلو درِ گوشی', () => {
  it('درِ عرضِ گوشی کارت می‌سازد وِ سرستونِ ۱۱۵۰پیکسلیِ جدول را درِ DOM نمی‌گذارد', () => {
    render(<TapeTable rows={ROWS} selected="" onSelect={() => {}} />);
    expect(screen.getByTestId('tape-cards')).toBeTruthy();
    expect(ROWS.every((r) => screen.queryByTestId(`board-card-${r.symbol}`))).toBe(true);
    expect(screen.queryByTestId('tape-head')).toBeNull();
    expect(screen.queryByTestId('tape-scroll')).toBeNull();
  });

  it('هرِ کارت نماد/قیمت/درصدِ تغییر/ارزش را باِ نامِ کاملِ خودش دارد (بندِ ۲.۱)', () => {
    render(<TapeTable rows={ROWS} selected="" onSelect={() => {}} />);
    const card = screen.getByTestId('board-card-فولاد');
    const text = card.textContent ?? '';
    expect(text).toContain('فولاد');
    expect(text).toContain('فولاد مبارکه اصفهان');
    expect(text).toContain('پایانی');
    expect(text).toContain('اختلاف٪');
    expect(text).toContain('حجم');
    expect(text).toContain('تعداد');
    // «ارزش» تنها برچسبِ اینِ خانه است؛ نبودنش یعنی دانۀِ خواستۀِ مالِ مالک پنهان شده
    expect(text).toContain('ارزش');
  });

  it('چیدمانِ کارت فاصلۀِ عمودیِ مشخصِ خودِ کامپوننت را دارد (بی‌انطباقِ سطرها)', () => {
    render(<TapeTable rows={ROWS} selected="" onSelect={() => {}} />);
    expect(String(screen.getByTestId('board-card-شپنا').getAttribute('class'))).toContain('gap-y-2');
  });

  it('جهتِ کارت ازِ رنگِ همانِ ردیفِ دسکتاپ خوانده می‌شود (مثبت/منفی/بی‌داده یکی نیستند)', () => {
    render(<TapeTable rows={ROWS} selected="" onSelect={() => {}} />);
    const up = screen.getByTestId('board-card-شپنا').textContent ?? '';
    // همانِ `fmtPct` ردیفِ دسکتاپ: رقمِ فارسی، ممیزِ لاتین، بی‌علامتِ «+»ِ اختراعی
    expect(up).toContain('۴.۲٪');
    expect(screen.getByTestId('board-card-فولاد').textContent).toContain('-۱.۸٪');
    const none = row({ symbol: 'بی‌درصد', percent_change: null });
    render(<TapeTable rows={[none]} selected="" onSelect={() => {}} />);
    expect(screen.getByTestId('board-card-بی‌درصد').textContent).not.toContain('+');
  });

  it('کلیک وِ Enter رویِ کارت همانِ onSelectِ ردیف را صدا می‌زند (انتخابِ نماد درِ گوشی)', () => {
    const onSelect = vi.fn();
    render(<TapeTable rows={ROWS} selected="" onSelect={onSelect} />);
    fireEvent.click(screen.getByTestId('board-card-خودرو'));
    expect(onSelect).toHaveBeenCalledWith('خودرو');
    fireEvent.keyDown(screen.getByTestId('board-card-خودرو'), { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledTimes(2);
  });

  it('مرتب‌سازیِ کارت ازِ همانِ کلیدهایِ سرستونِ جدول می‌آید وِ «بیشترینِ حجم» اول را عوض می‌کند', () => {
    render(<TapeTable rows={ROWS} selected="" onSelect={() => {}} />);
    const sel = screen.getByTestId('tape-cards-sort') as HTMLSelectElement;
    // پیش‌فرضِ والد: vol_ratio (حجم/ماه) باِ نزولی -- خودرو (۶٫۱) اول است
    expect(sel.value).toBe('vol_ratio');
    const firstCard = () => (screen.getAllByTestId(/^board-card-/)[0].getAttribute('data-testid') ?? '');
    expect(firstCard()).toBe('board-card-خودرو');
    fireEvent.change(sel, { target: { value: 'q_tot_cap' } });
    expect(firstCard()).toBe('board-card-فولاد');
    fireEvent.click(screen.getByTestId('tape-cards-direction'));
    expect(firstCard()).toBe('board-card-خودرو');
  });

  it('کلیدِ «جدولِ کامل» همانِ جدولِ همیشگی را برمی‌گرداند، نه نمایِ سومی', () => {
    render(<TapeTable rows={ROWS} selected="" onSelect={() => {}} />);
    fireEvent.click(screen.getByTestId('tape-view-table'));
    expect(screen.queryByTestId('tape-cards')).toBeNull();
    expect(screen.getByTestId('tape-head')).toBeTruthy();
    expect(screen.getByTestId('tape-scroll')).toBeTruthy();
    fireEvent.click(screen.getByTestId('tape-view-cards'));
    expect(screen.getByTestId('tape-cards')).toBeTruthy();
  });

  it('درِ دسکتاق هیچِ نمایِ دومی ساخته نمی‌شود (بی‌تغییرِ رفتارِ همیشگی)', () => {
    mobile = false;
    render(<TapeTable rows={ROWS} selected="" onSelect={() => {}} />);
    expect(screen.queryByTestId('tape-cards')).toBeNull();
    expect(screen.queryByTestId('tape-view-toggle')).toBeNull();
    expect(screen.getByTestId('tape-head')).toBeTruthy();
  });

  it('فیدِ خالی درِ گوشی هم همانِ پیامِ صادقانۀِ دسکتاپ را می‌گوید، بی‌کارتِ جعلی', () => {
    render(<TapeTable rows={[]} selected="" onSelect={() => {}} emptyNote="فیلترِ «حجم مشکوک» هیچِ نمادی نگذاشت" />);
    expect(screen.queryAllByTestId(/^board-card-/)).toHaveLength(0);
    expect(screen.queryByTestId('tape-cards')).toBeNull();
  });
});
