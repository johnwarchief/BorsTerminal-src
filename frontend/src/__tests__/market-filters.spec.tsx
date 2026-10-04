// تست فیلترهای جدید تابلو: ضریب حجم مشکوک، خروج از انباشت و ترتیب غربالگری
import { fireEvent, render, screen, within } from '@testing-library/react';
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
    expect(matchesExitAccum({ symbol: 'فولاد', f_clock: true, f_susp: true } as never)).toBe(true);
    expect(matchesExitAccum({ symbol: 'فولاد', f_clock: true, f_susp: false } as never)).toBe(false);
    expect(matchesExitAccum({ symbol: 'فولاد', f_clock: null, f_susp: true } as never)).toBe(false);
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
    render(<MarketFilters sectors={[]} matches={{ f_clock: 5, f_susp: 2, f_jet: 1, f_roobi: 3, f_noqteh: 0, f_smart: 0, f_legal: 0 }} />);
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

  // ── #207: چیپ باید بگوید چرا از فیلترنویسِ TSETMC کمتر می‌شمارد ───────────
  it('چیپ، ردیف‌هایِ پنهانِ همان فیلتر را با درِ هر کدام درِ عنوانش می‌شمارد', () => {
    render(
      <MarketFilters
        sectors={[]}
        matches={{ f_clock: 29, f_susp: 45, f_jet: 5, f_roobi: 1, f_noqteh: 4, f_smart: 0, f_legal: 0 }}
        hiddenInfo={{
          f_clock: { count: 49, doors: { 'پسوندِ عددی': 49 } },
          f_susp: { count: 51, doors: { 'پسوندِ عددی': 44, 'بازار/ابزارِ خاموش': 7 } },
          f_jet: { count: 0, doors: {} },
          f_roobi: { count: 30, doors: { 'نمادِ خاموش': 30 } },
          f_noqteh: { count: 7, doors: { جستجو: 5, صنعت: 2 } },
          f_smart: { count: 0, doors: {} },
          f_legal: { count: 0, doors: {} },
        }}
      />,
    );
    const roobi = screen.getByTitle(/کف‌روبی — ۳۰ ردیف/);
    expect(roobi.getAttribute('title')).toContain('(نمادِ خاموش ۳۰)');
    // دو در با شمارِ خودشان، به رتبهٔ HIDDEN_DOORS
    expect(screen.getByTitle(/حجم مشکوک — ۵۱ ردیف/).getAttribute('title')).toContain(
      '(پسوندِ عددی ۴۴، بازار/ابزارِ خاموش ۷)',
    );
    expect(screen.getByTitle(/نقطه زنی — ۷ ردیف/).getAttribute('title')).toContain(
      '(صنعت ۲، جستجو ۵)',
    );
    // جت هیچ ردیفِ پنهانی ندارد → عنوانِ ساده، بدونِ ادعایِ دروغ
    expect(screen.getByTitle(/^فیلتر جت$/).getAttribute('title')).toBe('فیلتر جت');
  });

  // سنجشِ زنده: ردیف‌هایِ پنهانِ پیش‌فرض *همه* پسوندِ عددی داشتند؛ اگر درِ دیگری
  // صفر باشد نام برده نمی‌شود، وگرنه کاربر «فقط زنده» را خاموش می‌کند و چیزی نمی‌بیند
  it('دری که ردیفی به آن نسبت داده نشده در تولتیپ نوشته نمی‌شود', () => {
    render(
      <MarketFilters
        sectors={[]}
        hiddenInfo={{
          f_clock: { count: 0, doors: {} },
          f_susp: { count: 12, doors: { 'پسوندِ عددی': 12 } },
          f_jet: { count: 0, doors: {} },
          f_roobi: { count: 0, doors: {} },
          f_noqteh: { count: 0, doors: {} },
          f_smart: { count: 0, doors: {} },
          f_legal: { count: 0, doors: {} },
        }}
      />,
    );
    const title = screen.getByTitle(/حجم مشکوک — ۱۲ ردیف/).getAttribute('title') ?? '';
    expect(title).toContain('(پسوندِ عددی ۱۲)');
    expect(title).not.toContain('نمادِ خاموش');
    expect(title).not.toContain('بازار');
    expect(title).not.toContain('جستجو');
  });

  // مالک پرسید «منظورت از در چیه؟» — جمله باید کاری باشد که کاربر می‌کند، نه استعاره
  it('تولتیپ نامِ کلیدی را می‌برد که همان ردیف‌ها را نشان می‌دهد', () => {
    render(
      <MarketFilters
        sectors={[]}
        hiddenInfo={{
          f_clock: { count: 0, doors: {} },
          f_susp: { count: 51, doors: { 'پسوندِ عددی': 44, 'بازار/ابزارِ خاموش': 7 } },
          f_jet: { count: 0, doors: {} },
          f_roobi: { count: 30, doors: { 'نمادِ خاموش': 30 } },
          f_noqteh: { count: 7, doors: { جستجو: 5, صنعت: 2 } },
          f_smart: { count: 0, doors: {} },
          f_legal: { count: 0, doors: {} },
        }}
      />,
    );
    const susp = screen.getByTitle(/حجم مشکوک — ۵۱ ردیف/).getAttribute('title') ?? '';
    expect(susp).toContain('دیده نمی‌شوند');
    expect(susp).toContain('حذفِ پسوندِ عددی');
    expect(susp).toContain('بازارها / ابزارها');
    // فقط زنده هم کلیدِ خودش را دارد
    expect(screen.getByTitle(/کف‌روبی — ۳۰ ردیف/).getAttribute('title')).toContain('فقط زنده');
    // صنعت و جستجو رأیِ خودِ کاربرند، پس هیچ کلیدی وعده داده نمی‌شود
    const noqteh = screen.getByTitle(/نقطه زنی — ۷ ردیف/).getAttribute('title') ?? '';
    expect(noqteh).not.toContain('باز می‌شوند');
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

  /** #171: دو سطحِ روی‌هم به یک نوار تبدیل شد — صنایع و چیپ‌ها راست،
   *  جستجو/شمارندۀ نماد/بازۀ بروزرسانی چپِ همان نوار. */
  it('نوار فیلتر یک‌سطحی است و جستجو و شمارنده در سمتِ چپِ همان نوار', () => {
    render(<MarketFilters sectors={[]} shown={120} total={600} pollMs={15000} onPollChange={() => {}} />);
    const bar = screen.getByTestId('market-filters-bar');
    expect(bar.className).not.toContain('flex-col');
    const kids = Array.from(bar.children);
    expect(kids).toHaveLength(2);
    expect(kids[0]).toBe(screen.getByTestId('quick-filters-bar'));
    expect(kids[1]).toBe(screen.getByTestId('filters-side'));
    // در RTL فرزندِ آخر سمتِ چپ می‌نشیند — جستجو، شمارنده و بازه همه آن‌جاوند
    const side = screen.getByTestId('filters-side');
    expect(within(side).getByLabelText('جستجوی نماد')).toBeInTheDocument();
    expect(within(side).getByLabelText('بازه به‌روزرسانی')).toBeInTheDocument();
    expect(within(side).getByTitle('تعداد نمادهای فعال در جدول')).toBeInTheDocument();
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

/**
 * تنظیمِ «حذفِ پسوندِ عددی»: درِ +N که قبلاً کلید نداشت. جهتِ سوییچ مثل
 * «فقط زنده» است — روشن = قاعده در کار است، پس پیش‌فرضِ آبی = رفتارِ همیشگی.
 */
describe('سوییچِ «حذفِ پسوندِ عددی» در نوارِ فیلتر', () => {
  beforeEach(() => {
    localStorage.clear();
    useTapeStore.getState().resetFilters();
  });

  const toggle = () => screen.getByTestId('numeric-suffix-toggle');

  it('پیش‌فرض: قاعده روشن (ردیف‌های پسونددار حذف) و سوییچ پریده', () => {
    render(<MarketFilters sectors={[]} />);
    expect(useTapeStore.getState().showNumericSuffix).toBe(false);
    expect(toggle()).toHaveAttribute('aria-pressed', 'true');
    expect(toggle().textContent).toContain('پسوند');
  });

  it('یک کلیک: ردیف‌ها دیده می‌شوند، تنظیم در localStorage می‌نشیند و «پاک کردن» شمار می‌کند', () => {
    render(<MarketFilters sectors={[]} />);
    fireEvent.click(toggle());
    expect(useTapeStore.getState().showNumericSuffix).toBe(true);
    expect(toggle()).toHaveAttribute('aria-pressed', 'false');
    expect(localStorage.getItem('bors_tape_show_numeric_suffix_v1')).toBe('1');
    // انحراف از پیش‌فرض ⇒ دکمۀِ «پاک کردن» که فقط با انحرافِ غیرصفر rendered می‌شود باید باشد
    expect(screen.getByTestId('filters-reset')).toBeInTheDocument();
    fireEvent.click(toggle());
    expect(screen.queryByTestId('filters-reset')).not.toBeInTheDocument();
  });

  it('کلیک دوم برمی‌گرداند و کلید را خاموش می‌کند', () => {
    render(<MarketFilters sectors={[]} />);
    fireEvent.click(toggle());
    fireEvent.click(toggle());
    expect(useTapeStore.getState().showNumericSuffix).toBe(false);
    expect(localStorage.getItem('bors_tape_show_numeric_suffix_v1')).toBe('0');
  });

  it('بازنشانیِ فیلترها مثل liveOnly قاعده را به پیش‌فرض برمی‌گرداند', () => {
    render(<MarketFilters sectors={[]} />);
    fireEvent.click(toggle());
    fireEvent.click(screen.getByTestId('filters-reset'));
    expect(useTapeStore.getState().showNumericSuffix).toBe(false);
    expect(localStorage.getItem('bors_tape_show_numeric_suffix_v1')).toBe('0');
  });

  it('تولتیپِ هر دو حالت نامِ همان ردیف‌ها را می‌برد، نه استعارهٔ گنگ', () => {
    render(<MarketFilters sectors={[]} />);
    expect(toggle().getAttribute('title')).toContain('پیش‌فرضِ تابلو');
    fireEvent.click(toggle());
    expect(toggle().getAttribute('title')).toContain('نشست‌هایِ قدیمی');
  });
});
