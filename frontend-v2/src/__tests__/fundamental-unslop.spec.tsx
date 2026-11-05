import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FundamentalScreenTable } from '@features/fundamental/ui/FundamentalScreenTable';
import { FundamentalDetail } from '@features/fundamental/ui/FundamentalDetail';
import { useFundamentalPrefs } from '@features/fundamental/stores/prefs';
import { resetExcludeAxes } from '@features/fundamental/lib/exclusionFilter';
import { useCodalHealth } from '@features/fundamental/api/useCodalHealth';
import { useFtsCard } from '@features/fundamental/api/useFtsCard';
import { useSectorPe } from '@features/fundamental/api/useSectorPe';
import type { ScreenerCoreRow } from '@features/fundamental/api/useScreenerCore';

vi.mock('@features/fundamental/api/useFtsCard', () => ({ useFtsCard: vi.fn() }));
vi.mock('@features/fundamental/api/useSectorPe', () => ({ useSectorPe: vi.fn() }));
vi.mock('@features/fundamental/api/useCodalHealth', () => ({ useCodalHealth: vi.fn() }));
vi.mock('@features/fundamental/api/useCalendar', () => ({
  useSymbolCalendar: () => ({ data: { status: 'ok', events: [] }, isLoading: false, isError: false }),
}));

/**
 * R-UNSLOP · قراردادِ کاریِ پروفایل و جدولِ بنیادی.
 * هیچ‌کدام از این‌ها «چشمی» ثابت نمی‌شوند: هر قاعده از متنِ سورس یا از DOMِ
 * رندرشده خوانده می‌شود، چونِ passِCraft دقیقاً همین‌ها را هدف گرفت.
 */

// vitest از frontend-v2 اجرا می‌شود؛ سورس‌سنجی با مسیرِ cwd انجام می‌شود نه import.meta
// (در jsdom آدرسِ ماژول http است نه file).
const STYLES = resolve(process.cwd(), 'src/app/styles.css');
const FEATURE = resolve(process.cwd(), 'src/features/fundamental').replace(/\\/g, '/');

function sourceFiles(dir: string, into: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = `${dir}/${entry.name}`;
    if (entry.isDirectory()) sourceFiles(full, into);
    else if (/\.tsx?$/.test(entry.name)) into.push(full);
  }
  return into;
}

const featureSources = sourceFiles(FEATURE).map((path) => ({ path, text: readFileSync(path, 'utf8') }));

/** فقط فایل‌هایِ UI؛ رشته‌هایِ داده/CSV در lib آزادند (ستونِ CSV کاراکترِ روند را نگه می‌دارد). */
const uiSources = featureSources.filter((file) => file.path.includes(`${FEATURE}/ui/`));

describe('unslop · قراردادِ فضایی و قلمیِ سطح بنیادی', () => {
  it('هیچ font-bold/extrabold/medium در سورسِ فیچر نمی‌ماند (سلسله‌مراتب با اندازه و رنگ)', () => {
    for (const file of featureSources) {
      for (const weight of ['font-bold', 'font-extrabold', 'font-semibold', 'font-medium']) {
        expect(file.text.includes(weight), `${file.path} :: ${weight}`).toBe(false);
      }
    }
  });

  it('هیچ متنِ زیرِ ۱۱px در فیچر نیست (کفِ فارسی)', () => {
    const banned = ['text-[8px]', 'text-[8.5px]', 'text-[9px]', 'text-[9.5px]', 'text-[10px]', 'text-[10.5px]',
      't-85', 't-9 ', 't-95', 't-10 ', 't-105', 't-125'];
    for (const file of featureSources) {
      for (const token of banned) expect(file.text.includes(token), `${file.path} :: ${token}`).toBe(false);
    }
  });

  it('ریتمِ ۴px: هیچ utilityِ بی‌شبیهِ ۰٫۵/۱٫۵/۲٫۵ و هیچ ارتفاعِ بی‌قافیه نمی‌ماند', () => {
    const banned = ['gap-1.5', 'gap-0.5', 'px-1.5', 'py-0.5', 'py-1.5', 'p-2.5', 'mt-0.5', 'px-2.5', 'py-2.5', 'p-1.5',
      'h-[26px]', 'h-[18px]', 'w-[26px]'];
    for (const file of featureSources) {
      for (const token of banned) expect(file.text.includes(token), `${file.path} :: ${token}`).toBe(false);
    }
  });

  it('شعاع‌ها فقط ۱۲/۸/۴/۲‌اند؛ rounded-full تنها روی نقطه و دایره‌های واقعی', () => {
    const banned = ['rounded-[3px]', 'rounded-[var(--radius-sm)]', 'rounded-sm', 'rounded-md', 'rounded-full'];
    for (const file of uiSources) {
      for (const token of banned) {
        if (token === 'rounded-full') {
          // قرصِ سوئیچِ تنظیمات و نقطهٔ رژیم مجازند؛ هیچ میلهٔ مستطیلی گردِ کامل نمی‌شود.
          const uses = file.text.split('rounded-full').length - 1;
          const allowed = file.path.endsWith('FtsSettingsDrawer.tsx') ? 2 : file.path.endsWith('RegimeGlyph.tsx') ? 1 : 0;
          expect(uses, `${file.path} :: rounded-full`).toBeLessThanOrEqual(allowed);
          continue;
        }
        expect(file.text.includes(token), `${file.path} :: ${token}`).toBe(false);
      }
    }
  });

  it('آیکنِ متن نیست: هیچ کاراکترِ ✓ ✕ ← → ↑ ↓ ↕ در UI نمانده است', () => {
    const glyphs = ['✓', '✕', '←', '→', '↑', '↓', '↕'];
    for (const file of uiSources) {
      for (const glyph of glyphs) expect(file.text.includes(glyph), `${file.path} :: ${glyph}`).toBe(false);
    }
  });

  it('شاخهٔ CSVِ روند دست‌نخورده می‌ماند (قراردادِ ستون)', () => {
    const axis = featureSources.find((file) => file.path.endsWith('lib/axisMeta.ts'))!;
    expect(axis.text).toContain('formatEpsTrend');
    expect(axis.text).toContain('↑');
    // DOM با مقدارِ بی‌فلش + آیکنِ SVG کار می‌کند.
    expect(axis.text).toContain('formatEpsValue');
  });
});

describe('unslop · مقیاسِ تایپوگرافیِ سطح بنیادی در styles.css', () => {
  const css = readFileSync(STYLES, 'utf8');
  const roles = ['fd-meta', 'fd-secondary', 'fd-title', 'fd-figure', 'fd-heading', 'fd-status-word'];

  it('شش جفتِ اندازه/وزنِ مجاز و هیچ‌کدام زیرِ ۱۱px نه', () => {
    const sizes = roles.map((role) => {
      const m = css.match(new RegExp(`\\.fundamental-surface \\.${role} \\{[^}]*?font-size: (\\d+(?:\\.\\d+)?)px`));
      expect(m, role).not.toBeNull();
      return Number(m![1]);
    });
    const weights = roles.map((role) => {
      const m = css.match(new RegExp(`\\.fundamental-surface \\.${role} \\{[^}]*?font-weight: (\\d+)`));
      expect(m, role).not.toBeNull();
      return Number(m![1]);
    });
    const pairs = new Set(sizes.map((size, index) => `${size}/${weights[index]}`));
    // مقیاسِ پروفایل: ۱۲/۴۰۰ · ۱۳/۴۰۰ · ۱۳/۵۰۰ · ۲۰/۵۰۰ · ۱۶/۵۰۰ · ۱۲/۵۰۰
    expect([...pairs].sort()).toEqual(['12/400', '12/500', '13/400', '13/500', '16/500', '20/500']);
    expect(Math.min(...sizes)).toBeGreaterThanOrEqual(11);
  });

  it('`<b>/<strong>` روی همین سطح ۵۰۰ می‌نشیند', () => {
    expect(css).toMatch(/\.fundamental-surface b,\s*\.fundamental-surface strong \{\s*font-weight: 500;/);
  });

  it('جدول دو چگالی دارد: راحت ۱۲px، فشرده ۱۱px', () => {
    expect(css).toMatch(/\.fd-table \{ --fd-cell-fs: 12px; \}/);
    expect(css).toMatch(/\.fd-table--compact \{ --fd-cell-fs: 11px; \}/);
  });

  it('سقفِ حرکت: پلکانِ شش‌پله‌ای، آخرین تأخیر ≤ ۲۰۰ms و یک منحنی', () => {
    const block = css.slice(css.indexOf('حرکتِ مهارشده'), css.indexOf('@keyframes fdIn'));
    const delays = [...block.matchAll(/animation-delay: (\d+)ms/g)].map((m) => Number(m[1]));
    expect(delays.length).toBeGreaterThan(0);
    expect(Math.max(...delays)).toBeLessThanOrEqual(200);
    // پله‌ها فقط تا فرزندِ ششم تازه می‌شوند؛ هفتم و بعد روی آخرین پله می‌نشینند.
    expect(block).toContain('nth-child(n+7)');
    expect(block).not.toMatch(/nth-child\(7\)/);
    expect(block).not.toMatch(/nth-child\(8\)/);
    expect(block).not.toMatch(/nth-child\(9\)/);
    // تک‌منحنی: هیچ ease-outِ خام روی انیمیشن‌هایِ fd نمی‌ماند.
    expect(block).not.toContain('ease-out');
    expect(css.match(/--fd-ease/g)!.length).toBeGreaterThan(2);
  });

  it('سرِ میله‌های نمودار ۲px است (نه ۱px نه ۳px)', () => {
    expect(css).toMatch(/\.fd-delta-bar,[\s\S]{0,120}\.fd-history-bar \{[\s\S]{0,40}border-radius: 2px 2px 0 0/);
  });
});

describe('unslop · کنتراستِ نقشِ muted روی سطح‌ها (محاسبه‌شده از توکن‌ها)', () => {
  const css = readFileSync(STYLES, 'utf8');

  function tokens(theme: string): Record<string, string> {
    const block = css.match(new RegExp(`html\\[data-theme='${theme}'\\] \\{([\\s\\S]*?)\\}`));
    expect(block, `theme ${theme}`).not.toBeNull();
    const out: Record<string, string> = {};
    for (const m of block![1]!.matchAll(/(--[\w-]+):\s*(#[0-9a-fA-F]{6})/g)) out[m[1]!] = m[2]!.toLowerCase();
    return out;
  }

  function channel(v: number): number {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  }

  function luminance(hex: string): number {
    const n = hex.replace('#', '');
    const r = channel(Number.parseInt(n.slice(0, 2), 16));
    const g = channel(Number.parseInt(n.slice(2, 4), 16));
    const b = channel(Number.parseInt(n.slice(4, 6), 16));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  function ratio(fg: string, bg: string): number {
    const a = luminance(fg);
    const b = luminance(bg);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  }

  it('--text-3 روی --bg/--panel/--panel-2 در brass و warm ≥ ۴٫۵:۱ است', () => {
    for (const theme of ['brass', 'warm'] as const) {
      const t = tokens(theme);
      for (const surface of ['--bg', '--panel', '--panel-2']) {
        expect(ratio(t['--text-3']!, t[surface]!), `${theme} text-3 on ${surface}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it('--text-2 (متنِ روانِ پنل‌ها) هم ≥ ۴٫۵:۱ است', () => {
    for (const theme of ['brass', 'warm'] as const) {
      const t = tokens(theme);
      for (const surface of ['--panel', '--panel-2']) {
        expect(ratio(t['--text-2']!, t[surface]!), `${theme} text-2 on ${surface}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });
});

/* ---------- اثباتِ رندرشده ---------- */

const rows: ScreenerCoreRow[] = [
  {
    symbol: 'رنيك', name: 'جنرال مکانیک', sector_name: 'خدمات فني و مهندسي', score: 3, verdict: 'WATCH',
    i1_pass: false, i1_na: false, i2_pass: true, i2_na: false, i3_pass: false, i3_na: false,
    i4_pass: true, i4_na: false, i5_pass: true, i5_na: false,
    rev_growth: 45.9, eps_series: [1119, 1615, 1672], eps_years_available: 3,
    gross_margin: 11.5, sales_to_mcap: 1.15, profit_potential_pct: 13.2, pricing_mode: 'neutral',
  },
  {
    symbol: 'البرز', name: 'بیمه البرز', sector_name: 'بيمه وصندوق بازنشستگي به جزتامين اجتماعي',
    score: 3, verdict: 'EXCLUDED', excluded: true,
    i1_pass: true, i1_na: false, i2_pass: null, i2_na: true, i3_pass: null, i3_na: true,
    i4_pass: null, i4_na: true, i4_reason: 'معاف: صنعت بیمه', i5_pass: true, i5_na: false,
    rev_growth: 83.5, eps_series: [1425, 454, 456], eps_years_available: 3,
    gross_margin: null, sales_to_mcap: null, profit_potential_pct: 0, pricing_mode: 'mandatory',
  },
];
const thresholds = { growth_min: 60, margin_min: 40, v10_sales_to_mcap_min: 0.33, profit_potential_min: 40, v10_eps_years: 3 };

const card = {
  status: 'success', symbol: 'رنيك', sector: 'خدمات فني و مهندسي', score: 3, verdict: 'WATCH',
  passes: { '1_growth': false, '2_eps_trend': true, '3_gross_margin': false, '4_sales_to_mcap': true, '5_industry': true },
  indicators: {
    '1': {
      monetary: { monetary_pct: 45.9, threshold: 40, target_threshold: 60, pass: false, data_gap: false, reason: '', ytd_now_bt: 5550, ytd_prev_bt: 3800 },
      volume: { applicable: false, real_pct: -8.8, volume_pct: null, pass: false, threshold: 0, data_gap: false },
    },
    '2': { eps_series: [1119, 1615, 1672], years_available: 3, years_required: 3, evidence: 'تلفیقی', consolidated_used: true, data_gap: false, reason: '', period_ends: ['1403', '1404', '1405'] },
    '3': { margin_pct: 11.5, threshold: 40, optimal_threshold: 30, margin_tier: 'below', gross_profit_bt: 12.4, revenue_bt: 107.8, na: false },
    '4': { sales_to_mcap: 1.15, sales_threshold: 0.33, potential_pct: 13.2, potential_threshold: 40, annual_sales_bt: 5.5, months_used: 6, available: true, na: false },
    '5': { verdict: 'neutral', label: 'خنثی', sector: 'خدمات فني و مهندسي', market_share_pct: 4.2, outlook: 'نیازمند بررسی', regime_label: 'خنثی', pass: true },
  },
  history: [{ period_end: '1404/12/29', revenue: 82657, eps: 1615, audited: true, consolidated: false }],
  details: { '۱': { formula: 'رشد ریالی', source: 'کدال', subchecks: [] } },
  freshness: { as_of: '2026-07-09', axes: {} },
  profile: { kind: 'production', margin_class: 'production' },
};

beforeEach(() => {
  resetExcludeAxes();
  useFundamentalPrefs.setState({ density: 'comfortable', sortKey: 'score', sortDir: 'desc' });
  vi.mocked(useFtsCard).mockReturnValue({ data: card, isLoading: false, isError: false } as never);
  vi.mocked(useSectorPe).mockReturnValue({ data: { pe: 6.2, median: 7.5, sector: 'x', peers: 12 }, isLoading: false, isError: false } as never);
  vi.mocked(useCodalHealth).mockReturnValue({ data: undefined, isLoading: false, isError: true } as never);
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe('unslop · اثباتِ رندرشده در جدول', () => {
  it('تراکم، کلاسِ جدول را عوض می‌کند: راحت ۱۲px / فشرده ۱۱px', () => {
    const { rerender } = render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    const root = screen.getByTestId('fundamental-screen-table');
    expect(root.className).toContain('fd-table');
    expect(root.className).not.toContain('fd-table--compact');
    useFundamentalPrefs.setState({ density: 'compact' });
    rerender(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(root.className).toContain('fd-table--compact');
  });

  it('روندِ EPS آیکنِ SVG است، نه کاراکترِ فلش — و نامِ دسترس‌پذیرش روند را می‌گوید', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    const cell = screen.getByTestId('fundamental-cell-رنيك-eps');
    expect(cell.textContent).toContain('۱۶۷۲');
    expect(cell.textContent).not.toContain('↑');
    expect(cell.textContent).not.toContain('→');
    const icon = cell.querySelector('[data-trend="up"]');
    expect(icon).toBeTruthy();
    expect(icon?.getAttribute('aria-label')).toBe('روند صعودی');
    expect(icon?.querySelector('path')).toBeTruthy();
    // روندِ نزولی هم آیکنِ خودش را دارد.
    expect(screen.getByTestId('fundamental-cell-البرز-eps').querySelector('[data-trend="flat"]')).toBeTruthy();
  });

  it('مهرِ وضعیت = نقطهٔ ۶پیکسلی + واژهٔ فارسی، بدونِ گلیفِ متن', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    const status = screen.getByTestId('fundamental-cell-رنيك-margin').querySelector('.fd-status')!;
    expect(status.textContent).toBe('رد');
    expect(status.querySelector('.fd-status-dot')).toBeTruthy();
    expect(status.className).toContain('fd-status--fail');
    expect(status.textContent).not.toContain('✕');
    // راهنمای جدول هم آیکنِ واقعی دارد (چهار وضعیت، هر کدام با شکلِ خودش).
    const legend = screen.getByTestId('fundamental-legend');
    expect(legend.querySelectorAll('svg').length).toBe(4);
    expect(legend.textContent).not.toContain('✓');
    expect(legend.textContent).not.toContain('−');
  });

  it('سرستونِ مرتب‌سازی آیکنِ SVG دارد و ↕ نمی‌نویسد', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    const button = screen.getByRole('button', { name: 'مرتب‌سازی رشد فروش' });
    expect(button.textContent).not.toContain('↕');
    expect(button.querySelector('svg')).toBeTruthy();
    expect(button.querySelector('[data-sort]')?.getAttribute('data-sort')).toBe('none');
    // کلیکِ اول روی ستونِ نو نزولی است؛ آیکنِ جهت باید عوض شود.
    fireEvent.click(button);
    expect(screen.getByRole('button', { name: 'مرتب‌سازی رشد فروش' }).querySelector('[data-sort]')?.getAttribute('data-sort')).toBe('desc');
    fireEvent.click(screen.getByRole('button', { name: 'مرتب‌سازی رشد فروش' }));
    expect(screen.getByRole('button', { name: 'مرتب‌سازی رشد فروش' }).querySelector('[data-sort]')?.getAttribute('data-sort')).toBe('asc');
  });

  it('ارتفاعِ ردیف‌ها در هر دو چگالی روی شبکهٔ ۴px و برابر است', () => {
    const { rerender } = render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(screen.getByTestId('fundamental-row-رنيك').getAttribute('style')).toContain('min-height: 92px');
    useFundamentalPrefs.setState({ density: 'compact' });
    rerender(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    expect(screen.getByTestId('fundamental-row-رنيك').getAttribute('style')).toContain('min-height: 44px');
  });

  it('املاءِ صنعت فقط در نمایش فارسی می‌شود؛ فیلتر و مقدارِ خام دست نمی‌خورند', () => {
    render(<FundamentalScreenTable rows={rows} thresholds={thresholds} onSelect={vi.fn()} asOf={null} />);
    const select = screen.getByLabelText('فیلتر صنعت') as HTMLSelectElement;
    const option = Array.from(select.options).find((item) => item.value.startsWith('بيمه'));
    expect(option).toBeTruthy();
    expect(option!.value).toBe('بيمه وصندوق بازنشستگي به جزتامين اجتماعي');
    expect(option!.textContent).toBe('بیمه و صندوق بازنشستگی به جزِ تأمین اجتماعی');
    // سرستونِ محور ۵ هم فارسی نشان می‌دهد.
    expect(screen.getByTestId('fundamental-cell-البرز-industry').textContent).toContain('بیمه و صندوق');
  });
});

describe('unslop · اثباتِ رندرشده در پروفایل', () => {
  it('دکمهٔ بازگشت پیکانِ SVG دارد و «←» نه', () => {
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const back = screen.getByTestId('fundamental-back');
    expect(back.textContent?.trim()).toBe('جدول بنیادی');
    expect(back.querySelector('svg')).toBeTruthy();
    expect(back.textContent).not.toContain('←');
  });

  it('بخشِ «فرمول و منبع» با mt-auto به پایینِ پنل نمی‌چسبد (باندِ مرده)', () => {
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const panel = screen.getByTestId('panel-growth');
    expect(panel.querySelector('details')?.className).not.toContain('mt-auto');
  });

  it('میله‌های روبانِ امتیاز دیگر rounded-full نیستند', () => {
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const bars = screen.getByTestId('fundamental-score-ribbon').querySelectorAll('[data-status]');
    expect(bars.length).toBe(5);
    for (const bar of Array.from(bars)) expect(bar.className).not.toContain('rounded-full');
  });

  it('هیچ کاراکترِ آیکنی در کلِ سطحِ پروفایل نمی‌ماند', () => {
    const { container } = render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    const text = container.textContent ?? '';
    for (const glyph of ['✓', '✕', '←', '↑', '↓', '↕']) {
      expect(text.includes(glyph), glyph).toBe(false);
    }
    // و هیچ کلاسی از سه وزنِ ممنوع در خروجی نیست.
    expect(container.innerHTML).not.toContain('font-bold');
    expect(container.innerHTML).not.toContain('font-extrabold');
    expect(container.innerHTML).not.toMatch(/text-\[(8|8\.5|9|9\.5|10|10\.5)px\]/);
  });

  it('نامِ صنعت در سرصفحه و پنلِ ۵ فارسی می‌شود', () => {
    render(<FundamentalDetail symbol="رنيك" onBack={vi.fn()} />);
    expect(screen.getByTestId('panel-industry').textContent).toContain('خدمات فنی و مهندسی');
    expect(screen.getByTestId('panel-industry').textContent).not.toContain('فني');
    const header = document.querySelector('[data-testid="fundamental-detail"] header')!;
    expect(header.textContent).toContain('خدمات فنی و مهندسی');
  });
});
