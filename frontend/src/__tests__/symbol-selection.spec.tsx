// __tests__/symbol-selection.spec.tsx — WS-2: یک انتخاب، دو جدول، هویتِ معتبر
//
// چهار ادعا اینجا نگهبانی می‌شود، دقیقاً همان‌هایی که task مالک درِ §۲۱ و §۲۲ و §۳۳
// خواسته است:
//   ۱) selection مشترک است: همان store درِ تابلو و بنیادی کار می‌کند (نه دو نسخه)
//   ۲) هویت فقط رشتهٔ نمایشی نیست: املایِ عربی/فارسی و نیم‌فاصله یک کلیدند
//      (همان مشکلی که `watchlist_store.py:12-16` درِ بک‌اند سندی‌اش کرده است)
//   ۳) جعبه مزاحمِ ردیف نیست: کلیکِ جعبه کاربر را به صفحۀ نماد **نمی‌برد**
//      (ردیفِ تابلو هم click دارد هم Space/Enter — بی stopPropagation دوتایی می‌زد)
//   ۴) انتخاب محلی و آنی است: بی‌هیچ درخواستِ شبکه‌ای
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import type { MarketRow } from '@shared/types/marketRow';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';
import { TapeRow } from '@features/market/components/TapeTable';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';
import SymbolSelectBox from '@shared/components/SymbolSelectBox';
import {
  isSelectedSymbol,
  useSelectedSymbolsStore,
} from '@shared/stores/selectedSymbolsStore';

// جدول بنیادی مجازی‌سازی شده و jsdom اندازه ندارد — همان الگوی fts-screen.spec.tsx
vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  return {
    ...mod,
    useVirtualizer: (opts: { count: number }) => ({
      getTotalSize: () => opts.count * 46,
      getVirtualItems: () => Array.from({ length: Math.min(opts.count, 30) },
                                        (_, i) => ({ key: i, index: i, start: i * 46 })),
    }),
  };
});

const marketRow = (over: Partial<MarketRow> = {}) =>
  ({
    symbol: 'فولاد', name: 'فولاد مبارکه', ins_code: '46348559193224090',
    p_last: 1000, p_closing: 990, price_yesterday: 985, percent_change: 1.5,
    percent_last: 0.5, tvol: 1_000_000, z_tot_tran: 40, q_tot_cap: 5e9,
    vol_ratio: 1.4, buyer_power: 1.8, buy_i_vol: 7e5, buy_count_i: 7,
    sell_i_vol: 3e5, sell_count_i: 3, hist_sessions: 60, prior30_vol: 2e7,
    min_low_29: 900, min30_low: 900, ...over,
  }) as unknown as MarketRow;

const screenRow = (over: Partial<FtsScreenRow> = {}) =>
  ({ symbol: 'شپنا', name: 'پالایشگاه شپنا', score: 4, primary_score: 2,
     excluded: false, watchlist: false, ...over } as unknown as FtsScreenRow);

const fetchSpy = vi.fn();

beforeEach(() => {
  localStorage.clear();
  useSelectedSymbolsStore.setState({ items: [] });
  vi.stubGlobal('fetch', fetchSpy);
  fetchSpy.mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('هویتِ انتخاب', () => {
  it('ي/ك عربی و نیم‌فاصله یک کلیدند — همان باگی که بک‌اند رفع کرده', () => {
    useSelectedSymbolsStore.getState().toggle({ symbol: 'داريك' });
    expect(isSelectedSymbol('داریک')).toBe(true);   // باگِ نوشتۀ v9.7.3 درِ watchlist_store
    expect(useSelectedSymbolsStore.getState().items).toHaveLength(1);
    useSelectedSymbolsStore.getState().toggle({ symbol: 'ملی' + '‌' + 'پالیش' });
    expect(isSelectedSymbol('ملیپالیش')).toBe(true);  // نیم‌فاصله حذف می‌شود
  });

  it('فاصله کلید را با بی‌فاصله یکی نمی‌کند — چون بک‌اند هم همین کار را می‌کند', () => {
    // norm_fa درِ fts_engine.py:46 فقط حرف‌ها و نیم‌فاصله را یکی می‌کند و فاصله را
    // نگه می‌دارد؛ کلیدِ user_watchlists هم همین است. اینجا فاصله را حذف می‌کردیم،
    // انتخابِ فرانت با ردیفِ واچ‌لیستِ سرور دو هویت می‌شد (§۲۲: identity معتبر).
    useSelectedSymbolsStore.getState().toggle({ symbol: 'ملی پالیش' });
    expect(isSelectedSymbol('ملیپالیش')).toBe(false);
  });

  it('انتخاب درِ localStorage می‌نشیند و بازنشانیِ state آن را برمی‌گرداند', () => {
    useSelectedSymbolsStore.getState().toggle({ symbol: 'فولاد', name: 'فولاد مبارکه',
                                                 insCode: '46348559193224090' });
    expect(localStorage.getItem(['bors', 'selected-symbols', 'v1'].join('-'))).toContain('فولاد');
    useSelectedSymbolsStore.setState({ items: [] });
    expect(isSelectedSymbol('فولاد')).toBe(false);
  });

  it('کلیکِ دوم انتخاب را برمی‌دارد و insCode ساختگی نمی‌شود', () => {
    const s = useSelectedSymbolsStore.getState();
    s.toggle({ symbol: 'خودرو' });
    expect(useSelectedSymbolsStore.getState().items[0].insCode).toBeNull();
    useSelectedSymbolsStore.getState().toggle({ symbol: 'خودرو' });
    expect(useSelectedSymbolsStore.getState().items).toHaveLength(0);
  });

  it('رشتهٔ خالی انتخاب نیست و فهرست را کثیف نمی‌کند', () => {
    useSelectedSymbolsStore.getState().toggle({ symbol: '  ' });
    expect(useSelectedSymbolsStore.getState().items).toHaveLength(0);
  });
});

describe('جعبه درِ ردیفِ تابلو', () => {
  it('جعبه انتخاب را می‌زند، ولی کاربر را به صفحۀ نماد نمی‌برد', () => {
    const onSelect = vi.fn();
    render(<TapeRow row={marketRow()} selected={false} onSelect={onSelect} />);
    const box = screen.getByTestId('select-box-فولاد');
    expect(box).toHaveAttribute('role', 'checkbox');
    expect(box).toHaveAttribute('aria-checked', 'false');
    fireEvent.click(box);
    expect(isSelectedSymbol('فولاد')).toBe(true);
    expect(onSelect).not.toHaveBeenCalled();
    expect(box).toHaveAttribute('aria-checked', 'true');
  });

  it('Space رویِ جعبه دو کار هم‌زمان نمی‌کند (ردیفِ تابلو Space را می‌گیرد)', () => {
    const onSelect = vi.fn();
    render(<TapeRow row={marketRow()} selected={false} onSelect={onSelect} />);
    fireEvent.keyDown(screen.getByTestId('select-box-فولاد'), { key: ' ' });
    expect(isSelectedSymbol('فولاد')).toBe(true);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('کلیک رویِ خودِ ردیف همچنان نماد را باز می‌کند — چیزی از رفتارِ قبلی کم نشده', () => {
    const onSelect = vi.fn();
    render(<TapeRow row={marketRow()} selected={false} onSelect={onSelect} />);
    fireEvent.click(screen.getByTestId('tape-row'));
    expect(onSelect).toHaveBeenCalledWith('فولاد');
    expect(isSelectedSymbol('فولاد')).toBe(false);
  });
});

// رأیِ مالک ۱۴۰۵-۰۷-۱۷: «مربعِ کوچک یا ستاره فقط اگر موس رویِ همان ردیف رفت نشان
// داده بشه.» jsdom توانِ :hover ندارد، پس این پروند *قراردادِ* کلاس را می‌پاید (که
// ویرایشِ بعدی آن را نیاندازد) و رفتارِ دیدنی را _audit/ws7e_hover_reveal.mts رویِ
// مرورگرِ واقعی می‌سنجد.
describe('پنهان تا hoverِ ردیف', () => {
  it('ردیف حملۀ group دارد و نشانگرها با opacity-0 شروع می‌شوند', () => {
    render(<TapeRow row={marketRow()} selected={false} onSelect={vi.fn()} />);
    expect(screen.getByTestId('tape-row').className).toContain('group');
    for (const id of ['select-box-فولاد', 'watch-star-فولاد']) {
      const cls = String(screen.getByTestId(id).className);
      expect(cls).toContain('opacity-0');
      expect(cls).toContain('group-hover:opacity-100');
      expect(cls).toContain('focus-visible:opacity-100');
      expect(cls).toContain('[@media(hover:none)]:opacity-100');   // اندروید hover ندارد
      expect(cls).toContain('motion-reduce:transition-none');
    }
  });

  it('ستارۀ عضوِ واچ‌لیست همیشه دیده می‌شود (حذفِ اطلاعاتِ دیدنی ممنوع)', () => {
    render(<TapeRow row={marketRow()} selected={false} onSelect={vi.fn()} />);
    expect(String(screen.getByTestId('watch-star-فولاد').className))
      .toContain('data-[in-list=1]:opacity-100');
  });
});

describe('جعبه درِ جدول بنیادی', () => {
  it('همان store را می‌زند — انتخابِ بنیادی درِ تابلو هم دیده می‌شود', () => {
    const onSelect = vi.fn();
    render(<FtsScreenTable rows={[screenRow()]} onSelect={onSelect} />);
    const box = screen.getByTestId('select-box-شپنا');
    fireEvent.click(box);
    expect(isSelectedSymbol('شپنا')).toBe(true);
    expect(onSelect).not.toHaveBeenCalled();
    // همان حالت درِ یک کامپوننتِ جدا (نمای تابلو)
    render(<div data-testid="elsewhere"><SymbolSelectBox symbol="شپنا" /></div>);
    expect(within(screen.getByTestId('elsewhere')).getByTestId('select-box-شپنا'))
      .toHaveAttribute('aria-checked', 'true');
  });

  it('انتخاب هیچ درخواستِ شبکه‌ای نمی‌زند (محلی و آنی)', () => {
    render(<FtsScreenTable rows={[screenRow({ symbol: 'فولاد' })]} onSelect={vi.fn()} />);
    fireEvent.click(screen.getByTestId('select-box-فولاد'));
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
