// تست فیلترهای جدید تابلو: ضریب حجم مشکوک، خروج از انباشت و ترتیب غربالگری
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { MarketFilters } from '@features/market/components/MarketFilters';
import { ASSET_TYPES } from '@features/market/lib/assetType';
import {
  DEFAULT_ASSET_TYPES,
  VOL_RATIO_DEFAULT,
  VOL_RATIO_MAX,
  VOL_RATIO_MIN,
  clampVolRatio,
  matchesExitAccum,
  matchesVolRatio,
  useTapeStore,
} from '@features/market/stores/tapeStore';

describe('استور فیلترهای جدید', () => {
  beforeEach(() => {
    useTapeStore.getState().resetFilters();
  });

  it('پیش‌فرض ضریب حجم ۳× و بازه ۱.۵ تا ۵ قفل است', () => {
    expect(VOL_RATIO_DEFAULT).toBe(3);
    expect(VOL_RATIO_MIN).toBe(1.5);
    expect(VOL_RATIO_MAX).toBe(5);
    expect(useTapeStore.getState().volRatioMin).toBe(3);
    expect(useTapeStore.getState().volRatioOn).toBe(false);
  });

  it('clampVolRatio خارج از بازه و مقادیر نامعتبر را به پیش‌فرض برمی‌گرداند', () => {
    expect(clampVolRatio(1)).toBe(1.5);
    expect(clampVolRatio(9)).toBe(5);
    expect(clampVolRatio(2.5)).toBe(2.5);
    expect(clampVolRatio(Number.NaN)).toBe(3);
  });

  it('setVolRatioMin در استور clamp می‌کند و reset بازنشانی می‌کند', () => {
    useTapeStore.getState().setVolRatioMin(4.5);
    useTapeStore.getState().setVolRatioOn(true);
    expect(useTapeStore.getState().volRatioMin).toBe(4.5);
    expect(useTapeStore.getState().volRatioOn).toBe(true);
    useTapeStore.getState().resetFilters();
    expect(useTapeStore.getState().volRatioOn).toBe(false);
    expect(useTapeStore.getState().volRatioMin).toBe(3);
  });

  it('matchesVolRatio فقط عدد معتبر بالای آستانه را رد می‌کند', () => {
    expect(matchesVolRatio(3.2, 3)).toBe(true);
    expect(matchesVolRatio(2.9, 3)).toBe(false);
    expect(matchesVolRatio(null, 3)).toBe(false);
    expect(matchesVolRatio(Number.NaN, 3)).toBe(false);
  });

  it('خروج از انباشت ترکیب ساعت و حجم مشکوک است', () => {
    expect(matchesExitAccum({ f_clock: true, f_susp: true })).toBe(true);
    expect(matchesExitAccum({ f_clock: true, f_susp: false })).toBe(false);
    expect(matchesExitAccum({ f_clock: null, f_susp: true })).toBe(false);
    useTapeStore.getState().toggleExitAccum();
    expect(useTapeStore.getState().exitAccum).toBe(true);
    useTapeStore.getState().toggleExitAccum();
    expect(useTapeStore.getState().exitAccum).toBe(false);
  });

  it('سوییچ ترتیب غربالگری و بازگشت در reset', () => {
    expect(useTapeStore.getState().screenOrder).toBe('tape_first');
    useTapeStore.getState().setScreenOrder('technical_first');
    expect(useTapeStore.getState().screenOrder).toBe('technical_first');
    useTapeStore.getState().resetFilters();
    expect(useTapeStore.getState().screenOrder).toBe('tape_first');
  });
});

describe('کنترل‌های فیلتر در MarketFilters', () => {
  beforeEach(() => {
    useTapeStore.getState().resetFilters();
  });

  it('چیپ‌های سریع FTS مستقیماً روی نوار رندر شده و فعال/غیرفعال می‌شوند', () => {
    render(<MarketFilters sectors={[]} matches={{ f_clock: 5, f_susp: 2, f_jet: 1, f_roobi: 3, f_noqteh: 0, f_smart_flow: 4 }} />);
    const clockChip = screen.getByText(/الگوی ساعت/);
    expect(clockChip).toBeInTheDocument();
    expect(screen.getByText('(۵)')).toBeInTheDocument();
    expect(screen.getByText(/کف‌روبی/)).toBeInTheDocument();
    expect(screen.getByText('(۳)')).toBeInTheDocument();

    fireEvent.click(clockChip.closest('button')!);
    expect(useTapeStore.getState().quickFilters).toContain('f_clock');

    fireEvent.click(clockChip.closest('button')!);
    expect(useTapeStore.getState().quickFilters).not.toContain('f_clock');
  });

  it('فیلترهای فعال در شمارندهٔ «پاک کردن» شمرده و با ریست پاک می‌شوند', () => {
    useTapeStore.getState().toggleQuickFilter('f_clock');
    useTapeStore.getState().toggleQuickFilter('f_susp');
    render(<MarketFilters sectors={[]} />);
    const reset = screen.getByText(/پاک کردن/);
    expect(reset.textContent).toContain('۲');
    fireEvent.click(reset);
    expect(useTapeStore.getState().quickFilters).toEqual([]);
  });
});

const TSETMC_LABELS = [
  'سهام',
  'فرابورس - بازار پایه',
  'حق تقدم',
  'انرژی',
  'صندوق سرمایه‌گذاری',
  'اختیار معامله',
  'اوراق بدهی',
  'تسهیلات مسکن',
  'بورس کالا',
  'آتی',
  'معاملات پایانی TAL',
] as const;

const ACTIVE_BY_DEFAULT = ['سهام', 'فرابورس - بازار پایه', 'حق تقدم', 'انرژی', 'صندوق سرمایه‌گذاری'];
const INACTIVE_BY_DEFAULT = ['اختیار معامله', 'اوراق بدهی', 'تسهیلات مسکن', 'بورس کالا', 'آتی', 'معاملات پایانی TAL'];

describe('نوار تک‌خطی فیلترها و dropdown بازارها', () => {
  beforeEach(() => {
    useTapeStore.getState().resetFilters();
  });

  const openMenu = () => {
    fireEvent.click(screen.getByRole('button', { name: /بازارها \/ ابزارها/ }));
  };
  const optionBox = (label: string) =>
    screen.getByRole('checkbox', { name: label }) as HTMLInputElement;

  it('نوار فیلتر دو سطحی کامپکت است (شامل وضعیت و فیلترها)', () => {
    render(<MarketFilters sectors={[]} />);
    const bar = screen.getByTestId('market-filters-bar');
    expect(bar.className).toContain('flex-col');
    // ۱۱ چیپ بازار دیگر بیرون از dropdown رندر نمی‌شوند
    expect(screen.queryByText('اختیار معامله')).not.toBeInTheDocument();
  });

  it('رگرسیون Z-Index: منوی باز با portal روی body و z-[9999] رندر می‌شود (نه زیر جدول)', () => {
    render(<MarketFilters sectors={[]} />);
    openMenu();
    const menu = screen.getByTestId('asset-filter-menu') as HTMLElement;
    // خارج از DOM نوار فیلتر، مستقیماً زیر body -- اسیر overflow/stacking والدین نیست
    expect(menu.parentElement).toBe(document.body);
    expect(menu.closest('[data-testid="market-filters-bar"]')).toBeNull();
    expect(menu.style.zIndex).toBe('9999');
    expect(menu.style.position).toBe('fixed');
    // گزینه‌های منو همچنان کاربردی‌اند
    expect(screen.getByRole('checkbox', { name: 'سهام' })).toBeInTheDocument();
  });

  it('dropdown «بازارها / ابزارها» هر ۱۱ گزینه TSETMC را با پنج تیکِ پیش‌فرض دارد', () => {
    render(<MarketFilters sectors={[]} />);
    openMenu();
    for (const label of TSETMC_LABELS) expect(optionBox(label)).toBeInTheDocument();
    for (const label of ACTIVE_BY_DEFAULT) expect(optionBox(label).checked).toBe(true);
    for (const label of INACTIVE_BY_DEFAULT) expect(optionBox(label).checked).toBe(false);
  });

  it('تیک‌زدن گزینهٔ غیرفعال، آن را به مجموعهٔ صریح اضافه می‌کند', () => {
    render(<MarketFilters sectors={[]} />);
    openMenu();
    fireEvent.click(optionBox('اختیار معامله'));
    expect(useTapeStore.getState().assetTypes).toContain('option');
    expect(optionBox('اختیار معامله').checked).toBe(true);
    fireEvent.click(optionBox('سهام'));
    expect(useTapeStore.getState().assetTypes).not.toContain('stock');
  });

  it('«همه» هر ۱۱ را فعال و «پیش‌فرض» به پنج‌تایی بازمی‌گرداند', () => {
    render(<MarketFilters sectors={[]} />);
    openMenu();
    fireEvent.click(screen.getByRole('button', { name: 'همه' }));
    expect(useTapeStore.getState().assetTypes).toHaveLength(ASSET_TYPES.length);
    fireEvent.click(screen.getByRole('button', { name: 'پیش‌فرض' }));
    expect(useTapeStore.getState().assetTypes).toEqual(DEFAULT_ASSET_TYPES);
  });

  it('سوییچ سریع «فقط بازار پایه» داخل منو: تک‌کلیک ست payeh، کلیک دوم بازگشت به پیش‌فرض', () => {
    render(<MarketFilters sectors={[]} />);
    openMenu();
    fireEvent.click(screen.getByRole('button', { name: 'فقط بازار پایه' }));
    expect(useTapeStore.getState().assetTypes).toEqual(['payeh']);
    fireEvent.click(screen.getByRole('button', { name: 'فقط بازار پایه' }));
    expect(useTapeStore.getState().assetTypes).toEqual(DEFAULT_ASSET_TYPES);
  });

  it('سوییچ سریع «فقط سهام بورس/فرابورس» دقیقاً stock+payeh را می‌گذارد', () => {
    render(<MarketFilters sectors={[]} />);
    openMenu();
    fireEvent.click(screen.getByRole('button', { name: 'فقط سهام بورس/فرابورس' }));
    expect(useTapeStore.getState().assetTypes).toEqual(['stock', 'payeh']);
  });
});
