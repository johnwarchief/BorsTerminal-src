// __tests__/fts-toolbar-1405-07-21.spec.tsx — شمارنده‌هایِ وابسته، نوارِ چسبان و تب‌هایِ گام
//
// سه خواستِ مأموریتِ ۱۴۰-۰۷-۱ درِ همین پرونده:
//   ۱) عددِ کنارِ هر چیپِ تابلوخوانی به «مجموعۀ نامزدهایِ فعلی» وابسته باشد،
//      نه شمارِ مستقلِ همان فیلتر درِ کلِّ بازار — و درِ هر دو منطقِ
//      اشتراک(AND)/اجتماع(OR) جدا رفتار کند.
//   ۲) «سنجیده نشد» هرگز داخلِ شمارندۀ قبولی نرود.
//   ۳) تب‌هایِ گام شمارندۀ «چند نماد از این گام عبور کرد» را نشان دهند و
//      بارگذاری/خطا/خالی با «صفر عبوری» اشتباه نشود.
//   ۴) نوارِ فیلتر چسبان بماند و سرستونِ جدول را نپوشاند (کلاس/ترازِ لایه).
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { countQuickFilters, countQuickMatches, MarketFilters } from '@features/market/components/MarketFilters';
import { FtsProcessStepper } from '@features/master/ui/FtsProcessStepper';
import { funnelFromApi } from '@features/master/lib/funnelView';
import { STATUS_HINT, STATUS_LABEL, type StageSummary } from '@features/master/lib/ftsFunnel';
import type { QuickFilter } from '@features/market/stores/tapeStore';
import { FUNNEL_FIXTURE } from './fixtures/funnelApi';

const ALL: QuickFilter[] = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh', 'f_smart', 'f_legal'];

/** ردیفِ کمینه: پرچم‌هایِ بک‌اند، بی‌پیکربندیِ محلی (داوریِ دوم نمی‌سازیم). */
const row = (over: Partial<Record<QuickFilter, boolean | null>> = {}) =>
  ({ symbol: 'خودرو', ...Object.fromEntries(ALL.map((f) => [f, false])), ...over });

describe('شمارنده‌های فیلترها به نامزدِ جاری وابسته‌اند', () => {
  // چهار ردیف: «مشکوک» دو تا، «جت» یکی از همان دو تا + یکی دیگر، «ساعت» هیچ.
  const rows = [
    row({ f_susp: true, f_jet: true }),
    row({ f_susp: true }),
    row({ f_jet: true }),
    row(),
  ];

  it('بی‌چیپِ روشن، مبنایِ شمارش کلِّ مجموعه است (رفتارِ پیشین)', () => {
    const { matched } = countQuickFilters(rows, undefined, [], 'and');
    expect(matched.f_susp).toBe(2);
    expect(matched.f_jet).toBe(2);
  });

  it('با یک چیپِ روشن، عددِ بقیه رویِ همان نامزدها می‌شمارد', () => {
    const { matched } = countQuickFilters(rows, undefined, ['f_susp'], 'and');
    // مبنایِ «جت» = ردیف‌هایِ f_susp (۲ تا)؛ از آن‌ها فقط یک جت دارد.
    expect(matched.f_jet).toBe(1);
    // خودِ چیپِ روشن leave-one-out می‌شمارد (مبنایش بقیهٔ روشن است = همه).
    expect(matched.f_susp).toBe(2);
  });

  it('با دو چیپِ روشن درِ اشتراک، هر دو اندازهٔ اشتراک را می‌بینند', () => {
    const { matched } = countQuickFilters(rows, undefined, ['f_susp', 'f_jet'], 'and');
    expect(matched.f_susp).toBe(1);
    expect(matched.f_jet).toBe(1);
  });

  it('درِ اجتماع مبنایِ هر چیپ اتحادِ بقیه است، نه اشتراکشان', () => {
    const { matched } = countQuickFilters(rows, undefined, ['f_susp', 'f_jet'], 'or');
    // مبنایِ «ساعت» = f_susp ∪ f_jet = ۳ ردیف؛ ساعت هیچ‌کدام را ندارد.
    expect(matched.f_clock).toBe(0);
    // مبنایِ «جت» = فقط f_susp (۲ ردیف) → یکی جت دارد.
    expect(matched.f_jet).toBe(1);
  });

  it('بی‌حکم درِ شمارندۀ قبولی نمی‌نشیند و رویِ همان نامزدِ جاری گزارش می‌شود', () => {
    const unjudged = [row({ f_susp: true, f_roobi: null }), row({ f_roobi: null })];
    const { matched, unevaluated } = countQuickFilters(unjudged, undefined, ['f_susp'], 'and');
    expect(matched.f_roobi).toBe(0);
    // مبنایِ «کف‌روبی» با چیپِ روشنِ «مشکوک» به یک ردیف می‌رسد؛ بی‌وابستگی
    // دو تا می‌شد — یعنی شمارندۀ «سنجیده نشد» هم به نامزدِ جاری گره خورده است.
    expect(unevaluated.f_roobi).toBe(1);
    expect(countQuickFilters(unjudged, undefined, [], 'and').unevaluated.f_roobi).toBe(2);
  });

  it('countQuickMatches همان شمارِ وابسته را برمی‌گرداند (بک‌مبسِ امضایِ قبلی)', () => {
    expect(countQuickMatches(rows, undefined, ['f_susp'], 'and').f_jet)
      .toBe(countQuickFilters(rows, undefined, ['f_susp'], 'and').matched.f_jet);
  });
});

const sum = (pass: number, over: Partial<StageSummary> = {}): StageSummary =>
  ({ pass, reject: 0, pending: 0, unavailable: 0, not_required: 0, ...over });

describe('تب‌های گام با شمارندهٔ عبوری‌ها', () => {
  const counts = {
    tape: sum(12), technical: sum(8), fundamental: sum(5), handover: sum(3),
  };
  const renderStepper = (props: Omit<React.ComponentProps<typeof FtsProcessStepper>, 'active'>) =>
    render(<MemoryRouter initialEntries={['/master?stage=tape']}>
      <FtsProcessStepper active="tape" {...props} />
    </MemoryRouter>);

  it('عددِ هر تب = عبوری‌هایِ همان گام، داخل پرانتزِ کنارِ عنوان', () => {
    renderStepper({ counts });
    expect(screen.getByTestId('fts-step-count-tape').textContent).toBe('۱۲');
    expect(screen.getByTestId('fts-step-count-technical').textContent).toBe('۸');
    expect(screen.getByTestId('fts-step-count-fundamental').textContent).toBe('۵');
    expect(screen.getByTestId('fts-step-count-handover').textContent).toBe('۳');
  });

  it('صفرِ واقعی همان «۰» است، نه خط ترمه', () => {
    renderStepper({ counts: { tape: sum(0), technical: sum(0), fundamental: sum(0), handover: sum(0) } });
    expect(screen.getByTestId('fts-step-count-tape').textContent).toBe('۰');
  });

  it('بارگذاریِ نخست (بی‌شمارش) «…» است، نه صفرِ عبوری', () => {
    renderStepper({ state: 'loading' });
    expect(screen.getByTestId('fts-step-count-tape').textContent).toBe('…');
  });

  it('تازۀسازیِ با شمارشِ موجود همان عددِ معتبر را نگه می‌دارد', () => {
    renderStepper({ counts, state: 'loading' });
    expect(screen.getByTestId('fts-step-count-tape').textContent).toBe('۱۲');
  });

  it('خطا با رنگِ جدا از «صفر عبوری» خوانده می‌شود', () => {
    renderStepper({ counts, state: 'error' });
    const badge = screen.getByTestId('fts-step-count-tape');
    expect(badge.textContent).toBe('!');
    expect(badge.className).toContain('accent-red');
  });

  it('تبِ فعال از تبِ غیرفعال متمایز است', () => {
    renderStepper({ counts });
    const on = screen.getByTestId('fts-step-tape');
    const off = screen.getByTestId('fts-step-technical');
    expect(on.className).toContain('bg-accent-blue/15');
    expect(on.getAttribute('aria-current')).toBe('step');
    expect(off.className).not.toContain('bg-accent-blue/15');
    expect(off.getAttribute('aria-current')).toBeNull();
  });
});

describe('نوار فیلتر چسبان است و سرستون را نمی‌پوشاند', () => {
  it('نوارِ غربالگریِ تابلو sticky است و زیرِ نوارِ نماد قفل می‌شود', () => {
    render(<MemoryRouter initialEntries={['/market']}>
      <MarketFilters sectors={[]} />
    </MemoryRouter>);
    const bar = screen.getByTestId('market-filters-bar');
    expect(bar.className).toContain('sticky');
    // `top-[var(--pinned-h)]` = دقیقاً زیرِ تاپ‌بار + نوارِ نماد؛ z-20 زیرِ
    // نوارِ نماد (z-30) و بالایِ سرستونِ جدول (z-10) — پس هیچ‌کدام را نمی‌پوشاند.
    expect(bar.className).toContain('top-[var(--pinned-h)]');
    expect(bar.className).toMatch(/z-20/);
  });
});

describe('«کاربرد ندارد» و «قابل ارزیابی نیست» دو وضعیت‌اند', () => {
  it('واژگانِ وضعیتِ گام و شاخص یکی نیست و هیچ‌کدام تهی نمانده', () => {
    expect(STATUS_LABEL.not_applicable).toBe('کاربرد ندارد');
    expect(STATUS_LABEL.pending).toBe('در انتظار');
    expect(STATUS_LABEL.unavailable).toBe('داده در دسترس نیست');
    expect(STATUS_HINT.not_applicable).not.toBe(STATUS_HINT.unavailable);
    // «لازم نبود» (گامِ اجرانشده) هم با «کاربرد ندارد» (شاخصِ بی‌معنا) قاطی نمی‌شود.
    expect(STATUS_LABEL.not_required).not.toBe(STATUS_LABEL.not_applicable);
  });
});

describe('«عبور با ملاحظات» را رابط نمی‌سازد', () => {
  it('بی‌پرچمِ سرور هیچ ردیفی ملاحظات نمی‌گیرد (داورِ دوم درِ فرانت نیست)', () => {
    const bare = funnelFromApi(FUNNEL_FIXTURE as never);
    const rows = [...bare.stages.fundamental.entries, ...bare.stages.handover.entries];
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.every((e) => e.fundCaveat === false)).toBe(true);
  });
});
