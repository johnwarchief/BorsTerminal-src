// __tests__/obsidian-strategy-graph.spec.tsx -- تست‌های جامع گراف شبکه‌ای ابسیدین FTS
// اعتبارسنجی تم روشن/تاریک، چینش RTL، جریان مهندسی معکوس و پوشش کامل ۴ صفحه چارت
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { ObsidianStrategyGraph, getGraphLinks } from '../features/master/components/ObsidianStrategyGraph';
import { useStrategyParamsStore, FTS_DEFAULT_PARAMS } from '../features/master/stores/strategyParamsStore';
import { useUiStore } from '../shared/stores/uiStore';

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
    expect(screen.getAllByText(/واگرایی منفی RSI/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/سقف دارایی بورس/i).length).toBeGreaterThan(0);
  });

  it('ویرایشگر زنده پارامترها را تغییر داده و دکمه بازنشانی به جزوه درست عمل می‌کند', () => {
    render(<ObsidianStrategyGraph selectedPreset="swing" />);

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
    expect(screen.getAllByText(/در اولین سقف/).length).toBeGreaterThan(0);
    expect(document.body.textContent ?? '').not.toMatch(/R1|ذخیره سود/);
    pickNode(/در اولین سقف/);
    expect(screen.getAllByText(/لایه لایه برویم و اصل پول را نگه داریم/).length).toBeGreaterThan(0);

    act(() => {
      useStrategyParamsStore.getState().updateParam('exitHalfPct', 30);
    });
    expect(screen.getAllByText(/۳۰/).length).toBeGreaterThan(0);
  });

  it('گرهٔ R/R عددِ جزوه ادعا نمی‌کند؛ آستانه پیش‌فرضِ برنامه است', () => {
    render(<ObsidianStrategyGraph selectedPreset="trend" />);
    expect(screen.getAllByText(/R\/R/).length).toBeGreaterThan(0);
    expect(document.body.textContent ?? '').not.toMatch(/حداقل ۱ به ۲/);
    pickNode(/R\/R کم/);
    expect(screen.getByText(/دلیلِ طلبِ سهم R\/R کم است/)).toBeInTheDocument();
    expect(screen.getByText(/پیش‌فرضِ برنامه/)).toBeInTheDocument();
  });
});
