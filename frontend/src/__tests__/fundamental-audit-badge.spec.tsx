// تست‌های F-06 — بج ممیزی/شفافیت وضعیت (AuditBadge):
// ۱) بج متراکم با وضعیت (قبول سبز · مردود قرمز · N/A خاکستری)
// ۲) بازشوی «چرا این وضعیت؟» با جدول مقدار واقعی سهم vs تارگت FTS + انحراف
// ۳) متن تشریحی علت + مرجع قاعده
// ۴) رفتار دفاعی: اگر فیلدهای ممیزی بک‌اند نبودند، فقط همان چیزی که هست (بدون عدد ساختگی)
// ۵) نصب روی کارت بنیادی (FtsCard) و ستون‌های جدول غربالگری (FtsScreenTable)
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  AuditBadge,
  AuditReasonCard,
  auditDeviation,
} from '@features/fundamental/components/AuditBadge';
import { FtsCard } from '@features/fundamental/components/FtsCard';
import { FtsScreenTable } from '@features/fundamental/ui/FtsScreenTable';
import { cardAuditEvidence, screenAuditEvidence } from '@features/fundamental/lib/auditEvidence';
import { toFaDigits } from '@shared/lib/fmt';
import type { FtsCard as FtsCardType } from '@features/fundamental/api/useFtsCard';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';

// jsdom اندازه ندارد -- virtualizer را به رندر کامل وادار می‌کنیم (الگوی tape-patterns)
vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  /** jsdom اندازه ندارد؛ پنجرهٔ ۱۲ ردیفی مثل پنجرهٔ مرورگر (۷۰vh/۴۶px) شبیه‌سازی می‌شود */
  const WINDOW = 12;
  return {
    ...mod,
    useVirtualizer: ({ count }: { count: number }) => ({
      getTotalSize: () => count * 46,
      getVirtualItems: () =>
        Array.from({ length: Math.min(count, WINDOW) }, (_, i) => ({ key: i, index: i, start: i * 46 })),
    }),
  };
});


const visa = JSON.parse(
  readFileSync(path.resolve(import.meta.dirname, 'fixtures/fundamental-visa.json'), 'utf8'),
) as FtsCardType;

function row(patch: Partial<FtsScreenRow> = {}): FtsScreenRow {
  return {
    symbol: 'نماد',
    symbol_norm: 'نماد',
    name: 'شرکت نمونه',
    sector_name: 'مواد و محصولات دارویی',
    pricing_mode: 'free',
    rev_growth: 45.2,
    eps_series: [100, 120, 150],
    eps_last: 150,
    eps_data_gap: false,
    gross_margin: 32.5,
    sales_to_mcap: 1.2,
    profit_potential_pct: 42.0,
    annual_sales_bt: 90.0,
    mcap: 5e13,
    score: 4,
    i1_pass: true,
    i1a_pass: true,
    i1b_pass: true,
    i1b_applicable: true,
    i3_na: false,
    i4_na: false,
    verdict: 'WATCH',
    i2_pass: true,
    i3_pass: true,
    i4_pass: true,
    i5_pass: false,
    excluded: false,
    exclusion_reasons: '',
    m141: false,
    watchlist: true,
    ...patch,
  };
}

afterEach(() => cleanup());

describe('AuditBadge — بج وضعیت', () => {
  it('سه وضعیت با برچسب و رنگ درست (قبول سبز · مردود قرمز · N/A خاکستری)', () => {
    render(
      <>
        <AuditBadge state="pass" testId="b-pass" />
        <AuditBadge state="fail" testId="b-fail" />
        <AuditBadge state="na" testId="b-na" />
      </>,
    );
    expect(screen.getByTestId('b-pass').textContent).toContain('قبول');
    expect(screen.getByTestId('b-fail').textContent).toContain('مردود');
    expect(screen.getByTestId('b-na').textContent).toContain('N/A');
    expect(screen.getByTestId('b-pass').className).toContain('text-accent-green');
    expect(screen.getByTestId('b-fail').className).toContain('text-accent-red');
    expect(screen.getByTestId('b-na').className).toContain('text-text-secondary');
  });

  it('برچسب دلخواه جای متن پیش‌فرض می‌نشیند و title کوتاه حفظ می‌شود', () => {
    render(<AuditBadge state="na" label="سابقهٔ EPS کمتر از ۲ سال" hintTitle="علت + راه‌حل" testId="b-c" />);
    const b = screen.getByTestId('b-c');
    expect(b.textContent).toContain('سابقهٔ EPS کمتر از ۲ سال');
    expect(b.textContent).not.toContain('N/A');
    expect(b.getAttribute('title')).toBe('علت + راه‌حل');
  });
});

describe('AuditBadge — هزینهٔ صفر در حالت بسته (F-08)', () => {
  it('شاهدِ تابعی تا وقتی کارت باز نشده اصلاً فراخوانی نمی‌شود', () => {
    let calls = 0;
    render(
      <AuditBadge
        state="fail"
        testId="lazy"
        evidence={() => {
          calls += 1;
          return { actualValue: 1, targetThreshold: 2, unit: '٪', reason: 'علت' };
        }}
      />,
    );
    expect(calls).toBe(0);
    expect(screen.queryByTestId('audit-popover')).toBeNull();
    fireEvent.mouseOver(screen.getByTestId('lazy'));
    expect(calls).toBe(1);
    expect(screen.getByTestId('audit-popover')).toBeInTheDocument();
    expect(screen.getByTestId('audit-reason').textContent).toContain('علت');
  });
});

describe('AuditBadge — بازشوی «چرا این وضعیت؟»', () => {
  it('hover کارت را با سربرگ + جدول مقایسه + علت + مرجع قاعده باز می‌کند', () => {
    render(
      <AuditBadge
        state="fail"
        testId="b-1"
        evidence={{
          actualValue: 21.5,
          targetThreshold: 30,
          unit: '٪',
          reason: 'حاشیهٔ ناخالص پایین‌تر از کف ۲۰٪ است.',
          ruleRef: 'جزوهٔ FTS — شاخص ۳',
        }}
      />,
    );
    expect(screen.queryByTestId('audit-popover')).toBeNull();
    fireEvent.mouseOver(screen.getByTestId('b-1'));
    const pop = screen.getByTestId('audit-popover');
    expect(within(pop).getByText('چرا این وضعیت؟')).toBeInTheDocument();
    expect(within(pop).getByTestId('audit-actual').textContent).toContain(toFaDigits('21.50') + '٪');
    expect(within(pop).getByTestId('audit-target').textContent).toContain(toFaDigits('30') + '٪');
    // انحراف = ۲۱٫۵ − ۳۰ = −۸٫۵ (منفی ⇒ از تارگت عقب)
    expect(within(pop).getByTestId('audit-deviation').textContent).toContain('−' + toFaDigits('8.50'));
    expect(within(pop).getByTestId('audit-deviation').className).toContain('text-accent-red');
    expect(within(pop).getByTestId('audit-reason').textContent).toContain('حاشیهٔ ناخالص پایین‌تر');
    expect(within(pop).getByTestId('audit-rule').textContent).toContain('جزوهٔ FTS');
  });

  it('وضعیت قبول انحراف مثبت را سبز نشان می‌دهد', () => {
    render(<AuditBadge state="pass" testId="b-2" evidence={{ actualValue: 45.2, targetThreshold: 30, unit: '٪' }} />);
    fireEvent.mouseOver(screen.getByTestId('b-2'));
    const dev = screen.getByTestId('audit-deviation');
    expect(dev.textContent).toContain('+' + toFaDigits('15.20'));
    expect(dev.className).toContain('text-accent-green');
  });

  it('کلیک بازشو را پین می‌کند و کلیک دوباره/Esc/کلیک بیرون می‌بندد', () => {
    render(<AuditBadge state="na" testId="b-3" evidence={{ reason: 'دادهٔ کافی نیست.' }} />);
    const b = screen.getByTestId('b-3');
    fireEvent.click(b);
    expect(screen.getByTestId('audit-popover')).toBeInTheDocument();
    expect(b.getAttribute('aria-expanded')).toBe('true');
    // راه‌انداز span است نه <button> تا داخل سلول‌های <button> کارت، button تودرتو نسازد
    expect(b.tagName).toBe('SPAN');
    expect(b.getAttribute('role')).toBe('button');
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByTestId('audit-popover')).toBeNull();
    fireEvent.click(b);
    expect(screen.getByTestId('audit-popover')).toBeInTheDocument();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByTestId('audit-popover')).toBeNull();
  });
});

describe('AuditBadge — رفتار دفاعی (نبود فیلدهای ممیزی بک‌اند)', () => {
  it('بدون مقدار/تارگت، جدول ساخته نمی‌شود و «قابل‌محاسبه نیست» می‌آید', () => {
    render(<AuditReasonCard state="na" evidence={{ reason: 'دلیل متنی موجود است.' }} />);
    expect(screen.queryByTestId('audit-compare')).toBeNull();
    expect(screen.getByTestId('audit-reason').textContent).toContain('دلیل متنی موجود است.');
  });

  it('شاهد کاملاً خالی: متن صادقانه + هیچ عدد ساختگی', () => {
    render(<AuditReasonCard state="fail" evidence={null} />);
    expect(screen.queryByTestId('audit-compare')).toBeNull();
    expect(screen.queryByTestId('audit-rule')).toBeNull();
    expect(screen.getByTestId('audit-reason').textContent).toContain('توضیحات تکمیلی برای این وضعیت ثبت نشده است');
  });

  it('auditDeviation: جهت پایین‌بهتر، جفت غیرعددی و تارگت صفر', () => {
    expect(auditDeviation(8, 12, 'higher')).toMatchObject({ delta: -4, meets: false });
    expect(auditDeviation(8, 12, 'lower')).toMatchObject({ delta: 4, meets: true });
    expect(auditDeviation(8, 0, 'higher')).toMatchObject({ delta: 8, pct: null, meets: true });
    expect(auditDeviation('نقدی', 12)).toBeNull();
    expect(auditDeviation(null, null)).toBeNull();
  });
});

describe('#204 — کارت بنیادی دیگر بج ممیزی ندارد (شواهد: جدول و پنل)', () => {
  it('سازندۀ شاهد هنوز اعدادِ واقعی را می‌دهد، ولی کارت هیچ بازشویی نمی‌سازد', () => {
    const audit = cardAuditEvidence(visa);
    const sales = visa.indicators?.['4']?.sales_to_mcap;
    const thr = visa.indicators?.['4']?.sales_threshold;
    expect(audit['4_sales_to_mcap']?.actualValue).toBe(sales ?? null);
    expect(audit['4_sales_to_mcap']?.targetThreshold).toBe(thr ?? null);
    expect(sales).not.toBeNull();
    expect(thr).not.toBeNull();
    render(<FtsCard score={visa.score ?? null} passes={visa.passes ?? {}} audit={audit} onDrill={() => {}} />);
    expect(screen.queryAllByTestId(/^fts-cell-audit-/)).toHaveLength(0);
    expect(screen.queryAllByTestId('audit-popover')).toHaveLength(0);
    fireEvent.mouseOver(screen.getByTestId('fts-card-cell-4_sales_to_mcap'));
    expect(screen.queryByTestId('audit-popover')).toBeNull();
  });

  // علتِ «حکم نداریم» تنها چیزی است که از بج مانده — بی‌آن کارت بی‌داده را
  // بی‌توضیح می‌گذارد و همان «چرا عددی نیست» دوباره سؤال می‌شود.
  it('سلولِ بی‌داده علت را به‌صورتِ متنِ ساده می‌نویسد، نه بازشو و نه «شکاف داده»', () => {
    render(<FtsCard score={2} passes={{ '3_gross_margin': false }} audit={null} />);
    /** #169: واژۀ حکم فقط در برچسبِ نتیجه است */
    expect(screen.getByTestId('fts-verdict-3_gross_margin')).toHaveTextContent('رد');
    expect(screen.queryByText('شکاف داده')).toBeNull();
    const gap = screen.getByTestId('fts-cell-gap-1a_monetary_growth');
    expect(gap.textContent).toContain('گزارش ماهانهٔ کدال نیست');
    fireEvent.mouseOver(gap);
    expect(screen.queryByTestId('audit-popover')).toBeNull();
  });
});

describe('AuditBadge در جدول غربالگری (FtsScreenTable)', () => {
  const thresholds = { growth_min: 30, margin_min: 20, v10_sales_to_mcap_min: 1, v10_eps_years: 3 };

  it('علامت شاخص ۱ با تارگت کانفیگ، جدول مقایسه دارد', () => {
    render(<FtsScreenTable rows={[row()]} onSelect={() => {}} thresholds={thresholds} />);
    fireEvent.mouseOver(screen.getByTestId('fts-mark-1a_monetary_growth'));
    const pop = screen.getByTestId('audit-popover');
    expect(within(pop).getByTestId('audit-actual').textContent).toContain(toFaDigits('45.20'));
    expect(within(pop).getByTestId('audit-target').textContent).toContain(toFaDigits('30') + '٪');
  });

  it('بدون تارگت‌ها: ستون تارگت «—» و انحراف «قابل‌محاسبه نیست»', () => {
    render(<FtsScreenTable rows={[row()]} onSelect={() => {}} />);
    fireEvent.mouseOver(screen.getByTestId('fts-mark-1a_monetary_growth'));
    const pop = screen.getByTestId('audit-popover');
    expect(within(pop).getByTestId('audit-target').textContent).toBe('—');
    expect(within(pop).getByTestId('audit-deviation').textContent).toContain('قابل‌محاسبه نیست');
  });

  it('ستون شاخص ۲ سابقهٔ EPS را با تارگت سال مقایسه می‌کند', () => {
    const ev = screenAuditEvidence('2_eps_trend', row({ eps_series: [null, 590, 990] }), thresholds);
    expect(ev.actualValue).toBe(2);
    expect(ev.targetThreshold).toBe(3);
    expect(ev.unit).toBe('سال');
  });

  it('ستون بی‌داده دقیقاً علت را نشان می‌دهد و برچسب کلی «شکاف داده» ندارد', () => {
    render(<FtsScreenTable rows={[row({ rev_growth: null, i1_pass: null, i1a_pass: null })]} onSelect={() => {}} />);
    expect(screen.getByTestId('fts-gap-reason-1a_monetary_growth').textContent).toContain('گزارش ماهانهٔ کدال نیست');
    expect(screen.queryByText('شکاف داده')).toBeNull();
  });
});
