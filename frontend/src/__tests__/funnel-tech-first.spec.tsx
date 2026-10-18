// __tests__/funnel-tech-first.spec.tsx — استراتژیِ «تکنیکال ← تابلو ← بنیادی ← تحویل»
//
// چه چیزی اثبات می‌شود (و چه چیزی نمی‌شود): داوریِ واقعی درِ `funnel_engine.py`
// است و `dev/funnel_engine_v1.py` آن را می‌سنجد. اینجا فقط سه ادعایِ رابطِ کاربری
// با همان پاسخِ دستیِ سرور سنجیده می‌شود:
//   ۱) ترتیبِ گام‌ها از `flowِ` پاسخ می‌آید، نه از یک فهرستِ دومِ فرانت؛
//      جدولِ تکنیکال اولین جدولِ اصلی است و تب‌ها/شماره‌ها هم همان‌جا می‌چرخند.
//   ۲) تک‌تکِ شرط‌هایِ اجراشدۀ همان نماد درِ ردیف دیده می‌شود، با وضعیت و دلیل،
//      و «نبودِ داده» با «رد» یکی نیست.
//   ۳) چیپ‌هایِ فیلترِ تکنیکال بی‌اثر نیستند: کلیک، `tech_chain` را درِ درخواست
//      بعدی می‌فرستد (اثبات از بدنهٔ POST، نه از state).
import type { ReactElement } from 'react';
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FtsFunnelStages } from '@features/master/ui/FtsFunnelStages';
import { funnelFromApi } from '@features/master/lib/funnelView';
import { funnelQueryKey } from '@features/master/api/useFtsFunnel';
import { useFunnelPrefsStore } from '@features/master/stores/funnelPrefsStore';
import { useTapeStore } from '@features/market/stores/tapeStore';
import { FUNNEL_FIXTURE, funnelCalls, installFunnelApi } from './fixtures/funnelApi';
import { TECH_FIRST_FIXTURE } from './fixtures/funnelTechFirst';

vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  const WINDOW = 50;
  return {
    ...mod,
    useVirtualizer: (opts: { count: number; estimateSize?: (i: number) => number }) => ({
      getTotalSize: () => opts.count * 29,
      getVirtualItems: () => Array.from({ length: Math.min(opts.count, WINDOW) },
                                        (_, i) => ({ key: i, index: i, start: i * 29 })),
    }),
  };
});

let restoreFetch = () => {};

beforeEach(() => {
  sessionStorage.clear();
  useFunnelPrefsStore.getState().reset();
  useFunnelPrefsStore.getState().resetToCanonical();
  useTapeStore.getState().resetFilters();
});

afterEach(() => restoreFetch());

const at = (preset: string, stage?: string) =>
  `/master?preset=${preset}${stage ? `&stage=${stage}` : ''}`;

async function ready(payload: typeof FUNNEL_FIXTURE, route: string) {
  restoreFetch = installFunnelApi(payload as never);
  const ui: ReactElement = (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: 0 } } })}>
      <MemoryRouter initialEntries={[route]}>
        <FtsFunnelStages preset="trend" onPresetChange={() => {}} />
      </MemoryRouter>
    </QueryClientProvider>
  );
  render(ui);
  await waitFor(() => expect(document.querySelectorAll('tbody tr').length).toBeGreaterThan(0),
                { timeout: 4000 });
  return payload;
}

/** شمارۀ گام‌ها از همان ترتیبِ اجرا خوانده می‌شود */
function stepBadge(key: string): string {
  const step = screen.getByTestId(`fts-step-${key}`);
  const num = step.querySelector('.num');
  return num?.textContent?.trim() ?? '';
}

describe('مدلِ قیف از پاسخ', () => {
  it('flowِ پاسخ ترتیبِ گام‌ها را تعیین می‌کند، نه حدسِ فرانت', () => {
    const t = funnelFromApi(TECH_FIRST_FIXTURE);
    expect(t.flow).toBe('tech_first');
    expect(t.stageOrder).toEqual(['technical', 'tape', 'fundamental', 'handover']);
    expect(t.techChain).toEqual(['t_weekly_up', 't_setup_jet', 't_setup_fib_33_40']);
    // تنظیماتِ مؤثر ازِ خودِ پاسخ خوانده می‌شود، نه از stateِ رابط
    expect(t.strategySettings).toEqual({ weekly_mode: 'off', daily_mode: 'off',
                                        clock_delta_pct: '1' });
    const r = funnelFromApi(FUNNEL_FIXTURE);
    expect(r.flow).toBe('tape_first');
    expect(r.stageOrder).toEqual(['tape', 'technical', 'fundamental', 'handover']);
  });

  it('پاسخِ بی‌flow (سرورِ قدیمی) همان ترتیبِ جزوه است', () => {
    const legacy = { ...FUNNEL_FIXTURE } as Record<string, unknown>;
    delete legacy.flow;
    expect(funnelFromApi(legacy as never).stageOrder[0]).toBe('tape');
  });

  it('شمارشِ هر فیلترِ تکنیکال از `stages.technical.filter_counts` خوانده می‌شود', () => {
    const t = funnelFromApi(TECH_FIRST_FIXTURE);
    expect(t.techFilterCounts.t_weekly_up).toEqual({ pass: 2, reject: 1, pending: 0, unavailable: 1 });
    // ورودیِ گامِ تابلو باید ماندگانِ تکنیکال باشد، نه جامعۀ غربالگری
    expect(t.stages.technical.input).toBe(4);
    expect(t.stages.tape.input).toBe(1);
  });

  it('کلیدِ کش با `tech_chain` جدا می‌شود (انتخابِ کاربر پاسخِ حالتِ دیگر را نشان ندهد)', () => {
    const base = { preset: 'tech_first' as const, chain: [], logic: 'and' as const,
                   fundMode: 'standard' as const, exceptions: {}, dropSuffix: true,
                   techChain: [] };
    expect(funnelQueryKey({ ...base, techChain: ['t_setup_jet'] }))
      .not.toEqual(funnelQueryKey(base));
    expect(funnelQueryKey({ ...base, techChain: ['t_setup_jet', 't_weekly_up'] }))
      .toEqual(funnelQueryKey({ ...base, techChain: ['t_weekly_up', 't_setup_jet'] }));
  });
});

describe('جدولِ تکنیکال به‌عنوانِ اولین جدولِ اصلی', () => {
  it('کارتِ تکنیکال پیش از کارتِ تابلو درِ DOM می‌آید', async () => {
    await ready(TECH_FIRST_FIXTURE, at('tech_first', 'handover'));
    // پرس‌وج‌و درِ همان ترتیبِ سند است، پس خودِ ترتیبِ DOM را می‌دهد (نه ترتیبِ
    // فهرستِ دستیِ ما).
    const pos = Array.from(document.querySelectorAll('[data-testid]'))
      .map((n) => n.getAttribute('data-testid') ?? '')
      .filter((id) => ['funnel-stage-tape', 'funnel-stage-technical',
                        'funnel-stage-fundamental', 'funnel-stage-handover'].includes(id));
    expect(pos).toEqual(['funnel-stage-technical', 'funnel-stage-tape',
                         'funnel-stage-fundamental', 'funnel-stage-handover']);
    // ورودیِ هر گام از خودِ موتور خوانده می‌شود: تکنیکال کلِ جامعۀ غربالگری (۴)
    // و تابلو فقط ماندگانِ او (۱).
    expect(document.querySelector('[data-testid="funnel-input-technical"]')?.textContent)
      .toContain('۴');
    expect(document.querySelector('[data-testid="funnel-input-tape"]')?.textContent)
      .toContain('۱');
  });

  it('شمارۀِ تب‌ها با ترتیب می‌چرخد: تکنیکال گام ۱، تابلوخوانی گام ۲', async () => {
    await ready(TECH_FIRST_FIXTURE, at('tech_first'));
    expect(stepBadge('technical')).toBe('۱');
    expect(stepBadge('tape')).toBe('۲');
    expect(stepBadge('fundamental')).toBe('۳');
  });

  it('درِ ترتیبِ جزوه همان شمارۀِ دیروز برجا می‌ماند (بازگشت‌ناپذیریِ flow)', async () => {
    await ready(FUNNEL_FIXTURE, at('custom'));
    expect(stepBadge('tape')).toBe('۱');
    expect(stepBadge('technical')).toBe('۲');
    // چیپ‌هایِ تکنیکال درِ این ترتیب اجرا نمی‌شوند؛ پس نباید هم فعال دیده شوند
    const chips = screen.queryByTestId('funnel-tech-chips');
    if (chips) {
      expect(within(chips).getByTestId('funnel-tech-chip-t_setup_jet')).toBeDisabled();
    }
  });

  it('سرستون‌هایِ لازمِ جدولِ تکنیکال رویِ میز هستند', async () => {
    await ready(TECH_FIRST_FIXTURE, at('tech_first', 'technical'));
    const card = screen.getByTestId('funnel-stage-technical');
    for (const label of ['هفتگی', 'روزانه', 'شواهد', 'شرط‌ها', 'تاریخِ داوری', 'داوری', 'دلیل']) {
      expect(within(card).getByRole('columnheader', { name: label })).toBeInTheDocument();
    }
    // «ورودیِ همین گام» هم خوانده شود: ۴ نماد واردِ تکنیکال شد، ۱ به تابلو رسید
    expect(within(card).getByTestId('funnel-input-technical').textContent).toContain('۴');
  });

  it('نتیجه و دلیلِ هر شرط درِ ردیف دیده می‌شود — عبور و رد و بی‌داده جدا', async () => {
    await ready(TECH_FIRST_FIXTURE, at('tech_first', 'technical'));
    const card = screen.getByTestId('funnel-stage-technical');
    // جدول پیش‌فرض فقط عبوری‌ها را می‌شمارد (رأیِ مالک ۱۴۰۵-۰۷-۱۹)
    const body = within(within(card).getByTestId('funnel-scroll-technical'));
    expect(body.getByText('فولاد')).toBeInTheDocument();
    expect(body.queryByText('همراه')).not.toBeInTheDocument();
    const gate = body.getByTestId('funnel-tech-check-فولاد-t_weekly_up');
    expect(gate.textContent).toContain('✓');
    expect(gate.getAttribute('title')).toContain('روند هفتگی صعودی');
    expect(gate.getAttribute('title')).toContain('tech_trend_w');
    const jet = body.getByTestId('funnel-tech-check-فولاد-t_setup_jet');
    expect(jet.textContent).toContain('✓');
    // تاریخِ داوری از خودِ ردیف است، نه زمانِ درخواست
    expect(body.getByTestId('funnel-tech-date-فولاد').textContent).not.toBe('—');
  });

  it('با «همه» گشوده می‌شود: وتوی هفتگی با ستاپِ قبول نشکستن است، و بی‌داده رد نیست',
     async () => {
    await ready(TECH_FIRST_FIXTURE, at('tech_first', 'technical'));
    const card = screen.getByTestId('funnel-stage-technical');
    fireEvent.click(within(card).getByTestId('funnel-tech-scope-all'));
    const body = within(within(card).getByTestId('funnel-scroll-technical'));
    // «همراه»: گیت رد، ستاپ جت قبول ⇒ ردیف باید رد باشد، نه عبور
    const rowM = body.getByText('همراه').closest('tr') as HTMLElement;
    expect(within(rowM as never).getByTestId('funnel-tech-check-همراه-t_setup_jet').textContent)
      .toContain('✓');
    expect(within(rowM as never).getByTestId('funnel-tech-check-همراه-t_weekly_up').textContent)
      .toContain('✗');
    expect(rowM.getAttribute('data-verdict')).toBe('reject');
    // «خودرو»: ریسکِ فعال ⇒ رد، با دلیلِ همان شاهد
    const rowX = body.getByText('خودرو').closest('tr') as HTMLElement;
    expect(within(rowX as never).getByTestId('funnel-tech-check-خودرو-t_risk_third_peak').textContent)
      .toContain('✗');
    expect(rowX.getAttribute('data-verdict')).toBe('reject');
    // «شپنا»: اسکن داوری نکرده ⇒ حکمش unavailable است، نه reject
    const rowS = body.getByText('شپنا').closest('tr') as HTMLElement;
    expect(rowS.getAttribute('data-verdict')).toBe('unavailable');
    expect(within(rowS as never).getByTestId('funnel-tech-date-شپنا').textContent).toBe('—');
    expect(within(rowS as never).getByTestId('funnel-tech-check-شپنا-t_setup_jet').textContent)
      .toContain('—');
  });
});

describe('چیپ‌هایِ شرطِ تکنیکال', () => {
  it('نام‌ها از رجیستریِ سرور می‌آید و گیتِ اجباری دکمه نیست', async () => {
    // پیش از رندر، همان انتخابی که پاسخِ below برایش شمارش فرستاده روشن می‌شود:
    // pressed بودنِ چیپ از store است، نه از بدنهٔ پاسخ.
    useFunnelPrefsStore.getState().toggleTechFilter('t_setup_jet');
    await ready(TECH_FIRST_FIXTURE, at('tech_first', 'technical'));
    const chips = screen.getByTestId('funnel-tech-chips');
    expect(within(chips).getByText('روندِ هفتگی صعودی')).toBeInTheDocument();
    // نام از رجیستری می‌آید: چیپی که رجیستری ندارد درِ رابط ساخته نمی‌شود
    expect(within(chips).queryByText('ستاپِ جعلی')).not.toBeInTheDocument();
    // گیت انتخابی نیست: span است، نه button
    const gate = within(chips).getByTestId('funnel-tech-gate-t_weekly_up');
    expect(gate.tagName).toBe('SPAN');
    const jet = within(chips).getByTestId('funnel-tech-chip-t_setup_jet');
    expect(jet.tagName).toBe('BUTTON');
    expect(jet).toHaveAttribute('aria-pressed', 'true');   // درِ این پاسخ اجرا شده
    expect(jet.textContent).toContain('۲');               // عبورِ همین فیلتر از سرور
  });

  it('کلیک رویِ چیپ، `tech_chain` را درِ درخواستِ بعدی می‌فرستد', async () => {
    await ready(TECH_FIRST_FIXTURE, at('tech_first', 'technical'));
    fireEvent.click(screen.getByTestId('funnel-tech-chip-t_risk_third_peak'));
    await waitFor(() => expect(useFunnelPrefsStore.getState().techChain)
      .toContain('t_risk_third_peak'), { timeout: 4000 });
    await waitFor(() => {
      const last = funnelCalls[funnelCalls.length - 1] as { tech_chain?: string[] };
      expect(last.tech_chain).toContain('t_risk_third_peak');
    }, { timeout: 4000 });
  });
});

describe('تنظیماتِ مستقلِ استراتژی و شاهدِ فیبو (رأیِ مالک ۱۴۰۵-۰۷-۲۷)', () => {
  it('پیچ‌ها از رجیستری ساخته می‌شوند و انتخاب، درِ درخواستِ بعدی می‌رود', async () => {
    await ready(TECH_FIRST_FIXTURE, at('tech_first', 'technical'));
    const row = screen.getByTestId('funnel-strategy-settings');
    // دو پیچ، دقیقاً آن‌طور که رجیستری تعریف کرده — رابط چیزی اختراع نمی‌کند
    expect(within(row).getByTestId('funnel-setting-weekly_mode')).toBeInTheDocument();
    const clock = within(row).getByTestId('funnel-setting-clock_delta_pct') as HTMLSelectElement;
    expect(clock.value).toBe('1');                     // پیش‌فرضِ همین استراتژی
    fireEvent.change(clock, { target: { value: '2' } });
    await waitFor(() => {
      const last = funnelCalls[funnelCalls.length - 1] as
        { strategy_settings?: Record<string, string> };
      expect(last.strategy_settings?.clock_delta_pct).toBe('2');
    }, { timeout: 4000 });
  });

  it('presetِ بی‌تعریف، هیچ پیچی نمی‌سازد (تنظیماتِ تازه به قدیمی‌ها نشت نمی‌کند)',
    async () => {
      await ready(FUNNEL_FIXTURE, at('trend', 'tape'));
      expect(screen.queryByTestId('funnel-strategy-settings')).toBeNull();
    });

  it('مقدارِ اصلاح درِ ردیفِ جدول دیده می‌شود، نه فقط خوردنِ یک برچسب', async () => {
    await ready(TECH_FIRST_FIXTURE, at('tech_first', 'technical'));
    const pct = await screen.findByTestId('funnel-fib-pct-فولاد-t_setup_fib_33_40',
                                        {}, { timeout: 4000 });
    expect(pct.textContent).toBe('۳۵.۲٪');   // همان fmtPctِ همیشگیِ رابط
    const chip = screen.getByTestId('funnel-tech-check-فولاد-t_setup_fib_33_40');
    // نقاطِ مبنایِ محاسبه (مبدأ/مقصد/کف/سقفِ موج) درِ همان سطر حمل می‌شود
    expect(String(chip.getAttribute('title'))).toContain('33-40');
  });

  it('دو تنظیمِ متفاوت، یکِ کلیدِ کش ندارند', () => {
    const base = { preset: 'tech_first' as const, chain: [], logic: 'and' as const,
      fundMode: 'standard' as const, exceptions: {}, dropSuffix: true, techChain: [] };
    const a = funnelQueryKey({ ...base, strategySettings: { clock_delta_pct: '1' } });
    const b = funnelQueryKey({ ...base, strategySettings: { clock_delta_pct: '2' } });
    const none = funnelQueryKey(base);
    expect(a).not.toEqual(b);
    expect(a).not.toEqual(none);
  });
});
