// __tests__/obsidian-strategy-graph.spec.tsx -- تست‌های جامع گراف شبکه‌ای ابسیدین FTS
// اعتبارسنجی تم روشن/تاریک، چینش RTL، جریان مهندسی معکوس و پوشش کامل ۴ صفحه چارت
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { ObsidianStrategyGraph, getGraphLinks, CHART_TREE, computeTreeLayout, COLLAPSIBLE_IDS } from '../features/master/components/ObsidianStrategyGraph';
import { useStrategyParamsStore, FTS_DEFAULT_PARAMS } from '../features/master/stores/strategyParamsStore';
import { useUiStore } from '../shared/stores/uiStore';

/** دو دستهٔ پیش‌فرض‌بسته را باز می‌کند (دابل‌کلیک رویِ گرهِ دسته). */
function expandAll() {
  fireEvent.click(screen.getByTestId('tree-expand-all'));
}

describe('گراف استراتژی شبکه ابسیدین FTS (ObsidianStrategyGraph)', () => {
  beforeEach(() => {
    useStrategyParamsStore.getState().resetAll();
    useUiStore.getState().setTheme('dark');
  });

  it('بوم اصلی SVG را با ساختار کامل رسم می‌کند', () => {
    render(<ObsidianStrategyGraph selectedPreset="swing" />);
    const canvas = screen.getByTestId('obsidian-strategy-canvas');
    expect(canvas).toBeInTheDocument();
  });

  it('در تم روشن (Light Theme) کانتینر و پلاک‌ها استایل کنتراست بالا دریافت می‌کنند', () => {
    useUiStore.getState().setTheme('light');
    const { container } = render(<ObsidianStrategyGraph selectedPreset="swing" />);

    // کانتینر اصلی باید استایل روشن دریافت کند
    expect(container.firstChild).toHaveClass('bg-slate-50');
    // متن جریان RTL در تم روشن باید خوانا باشد
    expect(screen.getByText(/جریان مهندسی معکوس/i)).toBeInTheDocument();
  });

  it('سوییچ بین مهندسی معکوس نوسان‌گیری و جریان کلاسیک کار می‌کند', () => {
    render(<ObsidianStrategyGraph selectedPreset="swing" />);

    const classicBtn = screen.getByRole('button', { name: /جریان مستقیم \(کلاسیک\)/i });
    expect(classicBtn).toBeInTheDocument();

    fireEvent.click(classicBtn);
    expect(screen.getByText(/شروع از بنیادی/i)).toBeInTheDocument();

    const reverseBtn = screen.getByRole('button', { name: /مهندسی معکوس \(نوسان‌گیری\)/i });
    fireEvent.click(reverseBtn);
    expect(screen.getByText(/شروع از تابلوخوانی/i)).toBeInTheDocument();
  });

  it('شامل تمام نودهای کلیدی ۴ صفحه چارت درختی بدون از قلم افتادن بندهاست', () => {
    render(<ObsidianStrategyGraph selectedPreset="swing" />);
    // «رصد جریان نقدینگی» و «مدیریت سرمایه» پیش‌فرض تا شده‌اند تا نخستین
    // نگاه خوانا باشد. هیچ‌کدام حذف نشده — بازشان می‌کنیم و می‌سنجیم که
    // همه سرِ جایشان‌اند. این خودش گاردِ همان رفتارِ تاشدن هم هست.
    expandAll();

    // رکن تابلوخوانی (صفحه ۳)
    expect(screen.getAllByText(/حجم مشکوک/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/الگوی ساعت/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/خروج از باکس رنج/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/کف‌روبی و جمع‌آوری صف/i).length).toBeGreaterThan(0);

    // رکن تکنیکال دو زمانه (صفحه ۲)
    expect(screen.getAllByText(/تایم هفتگی صعودی/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/ستاپ جت/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/ستاپ پولبک/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/ستاپ فیبوناچی/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/تغییر ساختار CHoCH/i).length).toBeGreaterThan(0);

    // رکن ۵ شاخص بنیادی (صفحه ۱)
    expect(screen.getAllByText(/سوپربنیادی/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/رد صلب بنیادی/i).length).toBeGreaterThan(0);

    // رکن مدیریت سرمایه و خروج (صفحه ۴)
    expect(screen.getAllByText(/حد ضرر نوسان‌گیر/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/در اولین سقف/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/خروج در سقف سوم/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/واگرایی مقاومتی/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/نمودارهای جریان نقدینگی/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/کف دوقلو/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/رصد مداوم پورتفو/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/سقف دارایی بورس/i).length).toBeGreaterThan(0);
  });

  it('ویرایشگر زنده پارامترها را تغییر داده و دکمه بازنشانی به جزوه درست عمل می‌کند', () => {
    render(<ObsidianStrategyGraph selectedPreset="swing" />);
    expandAll(); // شاخه‌ها پیش‌فرض بسته‌اند (خوانایی در ۱۳۶۶×۷۶۸)

    // نود پیش‌فرض tape_volume است
    expect(screen.getByText(/ضریب حجم مشکوک/i)).toBeInTheDocument();

    // تغییر مقدار ضریب با استور
    act(() => {
      useStrategyParamsStore.getState().updateParam('minVolumeRatio', 4.5);
    });
    expect(useStrategyParamsStore.getState().params.minVolumeRatio).toBe(4.5);

    // کلیک روی بازنشانی به جزوه
    const resetBtn = screen.getByRole('button', { name: /بازنشانی به جزوه/i });
    act(() => {
      fireEvent.click(resetBtn);
    });
    expect(useStrategyParamsStore.getState().params.minVolumeRatio).toBe(FTS_DEFAULT_PARAMS.minVolumeRatio);
  });

  describe('پلاک نماد روی نقشۀ چهارچارتی (۲۲۲)', () => {
    it('با نمادِ انتخابی، هر چهار فاز و سطوحِ ورود/حمایت/مقاومت/حدضرر دیده می‌شوند', () => {
      render(
        <ObsidianStrategyGraph
          selectedPreset="swing"
          symbol="فولاد"
          symbolPhaseStatus={[{ k: 'F', status: 'pass', label: 'بنیادی تایید' },
            { k: 'T', status: 'wait', label: 'در انتظار ستاپ' },
            { k: 'S', status: 'pass', label: 'الگوی ساعت' },
            { k: 'M', status: 'fail', label: 'وتوی سبد' }]}
          symbolLevels={{ price: 30000, entry: 31500, support: 29200, resistance: 31500, hardStop: 28100, exitVerdict: 'hold' }}
        />,
      );
      const plaque = screen.getByTestId('graph-symbol-plaque');
      expect(plaque).toBeInTheDocument();
      expect(plaque.textContent).toContain('فولاد');
      for (const k of ['F', 'T', 'S', 'M']) expect(plaque.textContent).toContain(k);
      expect(plaque.textContent).toContain('ورود');
      expect(plaque.textContent).toContain('حدضرر');
      expect(plaque.textContent).toContain('۳۱۵۰۰');
      expect(plaque.textContent).toContain('۲۸۱۰۰');
    });

    it('بی نماد، پلاک رسم نمی‌شود (نقشۀ راهنمای کلان دست‌نخورده)', () => {
      render(<ObsidianStrategyGraph selectedPreset="swing" />);
      expect(screen.queryByTestId('graph-symbol-plaque')).not.toBeInTheDocument();
    });
  });
});

// درختِ روندگیر باید همان درِ قیف باشد: کف‌روبی + نقطه‌زنی (چارت ۳ جزوه).
describe('شاخۀ روندگیر درِ هر دو جهتِ جریان', () => {
  it('کف‌روبی و نقطه‌زنی به مسیرِ روندگیر وصل‌اند و به stop_trend می‌رسند', () => {
    for (const flow of ['reverse', 'classic'] as const) {
      const links = getGraphLinks(flow).filter((l) => l.presets.includes('trend'));
      const ids = links.flatMap((l) => [l.source, l.target]);
      // دو گره‌ای که دروازۀ قیفِ روندگیر از همان‌ها می‌شمارد (f_roobi + f_noqteh)
      expect(ids).toContain('tape_floor_sweep');
      expect(ids).toContain('setup_point_hunt');
      // و شاخه باید به مدیریتِ سرمایه برسد، نه اینکه گرهٔ بی‌مقصد بماند
      expect(ids).toContain('stop_trend');
      expect(links.some((l) => l.source === 'tape_floor_sweep' || l.target === 'tape_floor_sweep')).toBe(true);
      expect(links.some((l) => l.source === 'setup_point_hunt' || l.target === 'setup_point_hunt')).toBe(true);
    }
  });
});

// #223: سه گره‌ای که در جزوه پیدا نشدند — حالا واژۀ خودِ جزوه را دارند و
// هیچ ادعایِ عددیِ بی‌منبع در درخت نمی‌ماند. متنِ تفصیلی فقط درِ پنلِ «نما»
// (گرهٔ برگزیده) دیده می‌شود، پس تست اول گره را انتخاب می‌کند.
describe('#223 — واژگانِ سه گره از خودِ جزوه', () => {
  beforeEach(() => {
    useStrategyParamsStore.getState().resetAll();
    useUiStore.getState().setTheme('dark');
  });

  const pickNode = (label: RegExp) => {
    const text = screen.getByText(label);
    fireEvent.click(text.closest('g')!);
  };

  it('شاخص ۵ همان «نوع نرخ‌گذاری» است که موتور می‌شمارد، نه DPS و مجمع', () => {
    render(<ObsidianStrategyGraph selectedPreset="trend" />);
    expect(screen.getAllByText(/نوع نرخ‌گذاری/).length).toBeGreaterThan(0);
    pickNode(/شاخص ۵/);
    expect(screen.getAllByText(/دستوری نباشد/).length).toBeGreaterThan(0);
    const body = document.body.textContent ?? '';
    expect(body).not.toMatch(/DPS/);
    expect(body).not.toMatch(/مجمع/);
    expect(body).not.toMatch(/سود انباشته/);
  });

  it('گرهٔ خروج، «اولین سقف» را می‌گوید و درصد را از دستِ کاربر می‌گیرد', () => {
    render(<ObsidianStrategyGraph selectedPreset="trend" />);
    expandAll(); // شاخه‌ها پیش‌فرض بسته‌اند (خوانایی در ۱۳۶۶×۷۶۸)
    expect(screen.getAllByText(/در اولین سقف/).length).toBeGreaterThan(0);
    expect(document.body.textContent ?? '').not.toMatch(/R1|ذخیره سود/);
    pickNode(/در اولین سقف/);
    expect(screen.getAllByText(/لایه لایه برویم و اصل پول را نگه داریم/).length).toBeGreaterThan(0);

    act(() => {
      useStrategyParamsStore.getState().updateParam('exitHalfPct', 30);
    });
    expect(screen.getAllByText(/۳۰/).length).toBeGreaterThan(0);
  });

  // تستِ گرهٔ R/R برداشته شد: خودِ گره در ۱٫۰٫۶۶ حذف شد چون در هیچ‌یک از
  // چهار صفحهٔ چارت و در احکامِ مالک نبود — آستانه‌اش «پیش‌فرضِ برنامه» بود،
  // یعنی ادعایی بی‌منبع رویِ نموداری که قرار است عینِ چارت باشد.
});

// ─────────────────────────────────────────────────────────────────────────
// سلسله‌مراتبِ صفحهٔ ۲ چارت (افزودهٔ ۱٫۰٫۶۶)
//
// چارت صریح است: روندِ *روزانه* تعیین می‌کند کدام ستاپ معتبر است، نه
// هفتگی. تا پیش از این، گراف طبقهٔ روزانه را اصلاً نداشت و «هفتگی صعودی»
// مستقیم به هر شش ستاپ وصل بود — یعنی به کاربر می‌گفت «هفتگی صعودی ⇒ هر
// ستاپی مجاز است». این تست‌ها نمی‌گذارند آن میان‌بر برگردد.
describe('چارت ص۲: روندِ روزانه درِ ستاپ‌ها را تعیین می‌کند', () => {
  const all = () => getGraphLinks('classic');
  const targetsOf = (src: string) =>
    all().filter((l) => l.source === src).map((l) => l.target);

  it('هفتگیِ صعودی فقط به سه شاخهٔ روزانه می‌رود (و نقطه‌زنیِ ص۳)', () => {
    const t = targetsOf('tech_weekly_up');
    expect(t).toEqual(expect.arrayContaining(['tech_daily_up', 'tech_daily_down', 'tech_daily_flat']));
    // هیچ ستاپِ وابسته‌به‌روزانه‌ای نباید مستقیم زیرِ هفتگی باشد
    for (const s of ['setup_pullback', 'setup_jet', 'setup_fib', 'setup_choch', 'setup_last_low', 'setup_double_bottom']) {
      expect(t).not.toContain(s);
    }
  });

  it('روزانهٔ صعودی ⇒ فقط پولبک و جت', () => {
    const t = targetsOf('tech_daily_up');
    expect(new Set(t)).toEqual(new Set(['setup_jet', 'setup_pullback']));
  });

  it('روزانهٔ نزولی ⇒ فقط فیبوناچی و CHoCH', () => {
    const t = targetsOf('tech_daily_down');
    expect(new Set(t)).toEqual(new Set(['setup_fib', 'setup_choch']));
  });

  it('روزانهٔ خنثی ⇒ فقط آخرین کف/سقف و کف دوقلو', () => {
    const t = targetsOf('tech_daily_flat');
    expect(new Set(t)).toEqual(new Set(['setup_last_low', 'setup_double_bottom']));
  });

  it('هر سه شاخهٔ روزانه در جریانِ معکوس هم هستند', () => {
    const rev = getGraphLinks('reverse');
    const t = rev.filter((l) => l.source === 'tech_weekly_up').map((l) => l.target);
    expect(t).toEqual(expect.arrayContaining(['tech_daily_up', 'tech_daily_down', 'tech_daily_flat']));
  });

  it('هیچ شاخهٔ روزانه‌ای بن‌بست نیست', () => {
    for (const d of ['tech_daily_up', 'tech_daily_down', 'tech_daily_flat']) {
      expect(targetsOf(d).length).toBeGreaterThan(0);
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────
// ستون‌فقراتِ درخت (۱٫۰٫۶۶) — خوانده‌شده از خودِ تصویرِ چارت.
// پیش از این گراف یک «شبکهٔ تخت» بود: یک هاب و ۴۹ برگ، با ۵۰ مختصاتِ
// دستی. حالا ساختار اعلانی است و چیدمان از آن مشتق می‌شود.
describe('ستون‌فقراتِ درخت از CHART_TREE', () => {
  it('سه رکن و چهار شاخهٔ ص۴ زیرِ هسته‌اند', () => {
    expect(CHART_TREE.fts_core).toEqual(
      expect.arrayContaining(['pillar_s', 'pillar_t', 'pillar_f', 'money_mgmt',
                              'strategy_group', 'portfolio_principles']),
    );
  });

  it('T سه شاخهٔ چارت را دارد: خرید / فروش / حد ضرر', () => {
    expect(CHART_TREE.pillar_t).toEqual(['signal_buy', 'signal_sell', 'stop_loss']);
  });

  it('S پنج شاخهٔ چارت را دارد', () => {
    expect(CHART_TREE.pillar_s).toEqual(
      ['sel_style', 'sel_liquidity', 'sel_volume', 'sel_patterns', 'sel_filter'],
    );
  });

  it('«خشک کردن» زیرِ الگوهای تابلوخوانی است، نه زیرِ فیلتر', () => {
    // در چارت فرزندِ روندگیر زیرِ «الگوهای تابلوخوانی» است؛ تا ۱٫۰٫۶۶
    // داخلِ «فیلترهای نهایی» ادغام شده بود.
    expect(CHART_TREE.sel_patterns).toContain('tape_dry_up');
    expect(CHART_TREE.sel_filter ?? []).not.toContain('tape_dry_up');
  });

  it('هیچ مختصاتی دستی نیست — همهٔ گره‌هایِ درخت از چیدمان می‌آیند', () => {
    const layout = computeTreeLayout();
    const named = new Set([...Object.keys(CHART_TREE), ...Object.values(CHART_TREE).flat()]);
    for (const id of named) expect(layout[id]).toBeDefined();
  });

  it('عمق با چارت می‌خواند: هسته ۰، رکن ۱، دستهٔ T دو، ستاپ ۵', () => {
    const l = computeTreeLayout();
    expect(l.fts_core.depth).toBe(0);
    expect(l.pillar_t.depth).toBe(1);
    expect(l.signal_buy.depth).toBe(2);
    expect(l.setup_pullback.depth).toBe(5);
  });

  it('والد وسطِ فرزندانش می‌نشیند', () => {
    const l = computeTreeLayout();
    const kids = CHART_TREE.tech_daily_up.map((k) => l[k].y);
    expect(l.tech_daily_up.y).toBeCloseTo((Math.min(...kids) + Math.max(...kids)) / 2, 5);
  });

  it('هر یالِ CHART_TREE در گراف هست', () => {
    const links = getGraphLinks('classic');
    const have = new Set(links.map((x) => `${x.source}>${x.target}`));
    for (const [par, kids] of Object.entries(CHART_TREE)) {
      for (const k of kids) expect(have.has(`${par}>${k}`)).toBe(true);
    }
  });

  it('هیچ یالِ تکراری نیست — دو خط رویِ هم کشیده نمی‌شود', () => {
    for (const flow of ['classic', 'reverse'] as const) {
      const pairs = getGraphLinks(flow).map((l) => `${l.source}>${l.target}`);
      expect(new Set(pairs).size).toBe(pairs.length);
    }
  });

  it('در پیش‌فرضِ بسته، برچسب‌ها رویِ ۱۳۶۶×۷۶۸ رویِ هم نمی‌افتند', () => {
    // باگِ لپ‌تاپِ مالک: با همهٔ شاخه‌ها باز، مقیاسِ بوم در آن پنجره ۰٫۴۱
    // می‌شد و فاصلهٔ واقعیِ دو برچسب ۱۳٫۲ پیکسل — کمتر از ~۱۸ که برچسب
    // لازم دارد. این تست همان حساب را نگه می‌دارد.
    const c = new Set(COLLAPSIBLE_IDS.filter((i) => !i.startsWith('pillar_')));
    const d = computeTreeLayout('fts_core', { collapsed: c });
    const ys = Object.values(d).map((v) => v.y);
    const h = Math.max(...ys) - Math.min(...ys);
    const scale = Math.min(1150 / 1960, 620 / (h + 96)); // ناحیهٔ گراف در ۱۳۶۶×۷۶۸
    expect(32 * scale).toBeGreaterThanOrEqual(18);
  });

  it('چیدمان در بومِ ۱۹۶۰×۱۵۰۰ جا می‌شود', () => {
    const l = Object.values(computeTreeLayout());
    expect(Math.min(...l.map((v) => v.x))).toBeGreaterThan(0);
    expect(Math.max(...l.map((v) => v.x))).toBeLessThan(1960);
    expect(Math.max(...l.map((v) => v.y))).toBeLessThan(1500);
  });
});
