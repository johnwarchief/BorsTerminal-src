// __tests__/fts-funnel-stages.spec.tsx — رندرِ قیف از پاسخِ /api/funnel
//
// این پرونده «منطق داوری» را تست نمی‌کند؛ منطق داوری درِ `funnel_engine.py` است و
// ۳۷ case درِ `dev/funnel_engine_v1.py` (ثبت‌شدۀ بیرونِ موتور) آن را می‌سنجد.
// چیزی که اینجا اثبات می‌شود دو چیز است:
//   ۱) فرانت همان حکمِ سرور را نمایش می‌دهد و دوباره داوری نمی‌کند — با ردیفِ
//      عمداً متناقض درِ فیکسچر («همراه» نشانه و امتیازِ پنج دارد ولی پاسخ می‌گوید
//      تکنیکالش رد شده؛ اگر فرانت خودش حکم بدهد، این تست می‌شکند).
//   ۲) ساختارِ UI که مالک خواست: یک workspace، سه سیستمِ انتخاب، چهار گام،
//      جدولِ مسلط، دلیلِ دیدنی، و حفظِ گام پس از بازگشت.
import type { ReactElement } from 'react';
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FtsFunnelStages } from '@features/master/ui/FtsFunnelStages';
import { funnelFromApi, stageProgressFor } from '@features/master/lib/funnelView';
import { useFunnelPrefsStore } from '@features/master/stores/funnelPrefsStore';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { FUNNEL_FIXTURE, installFunnelApi } from './fixtures/funnelApi';

// بدنهٔ هر جدولِ قیف مجازی‌سازی شده (پنج‌هزار ردیفِ universe رویِ هم)، و jsdom
// اندازه ندارد؛ همان الگوی `fts-screen.spec.tsx`: پنجره‌ای به بزرگیِ فهرست.
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

const renderRouted = (ui: ReactElement, at = '/master?stage=handover&preset=custom') =>
  render(<MemoryRouter initialEntries={[at]}>{ui}</MemoryRouter>);

const withClient = (ui: ReactElement, at?: string) =>
  renderRouted(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: 0 } } })}>
      {ui}
    </QueryClientProvider>,
    at,
  );

beforeEach(() => {
  sessionStorage.clear();
  useFunnelPrefsStore.getState().reset();
  useFunnelPrefsStore.getState().resetToCanonical();
  restoreFetch = installFunnelApi();
});

afterEach(() => restoreFetch());

/** صبرِ کوتاه تا پرس‌وجویِ قیف بنشیند؛ بی‌این اولین assert رویِ خالی می‌خورد. */
async function ready(at?: string) {
  const view = withClient(<FtsFunnelStages preset="custom" onPresetChange={() => {}} />, at);
  // صفحه بی‌درنگ کارتِ خالی را می‌سازد؛ شاهدِ واقعی رسیدنِ پاسخِ سرور، خودِ
  // ردیف‌هایند (بی‌این، assertها رویِ خالیِ اولیه می‌شکنند).
  await waitFor(() => expect(document.querySelectorAll('tbody tr').length).toBeGreaterThan(0),
                { timeout: 4000 });
  return view;
}

describe('قیف از پاسخِ سرور', () => {
  it('حکمِ سرور عیناً نمایش داده می‌شود — فرانت دوباره داوری نمی‌کند', async () => {
    await ready('/master?stage=technical&preset=custom');
    const table = screen.getByTestId('funnel-stage-technical');
    // «همراه» نشانه دارد و امتیاز پنج، ولی پاسخ می‌گوید تکنیکالش رد است.
    const why = within(table).getByTestId('funnel-why-همراه');
    expect(why.textContent).toContain('وتوی قطعی');
    // روندِ هفتگی هم از همان پاسخ می‌آید (نه از محاسبۀ ستاپ در فرانت)
    expect(within(table).getAllByText('نزولی').length).toBeGreaterThan(0);
  });

  it('ردیفی که پاسخ می‌گوید سنجیده‌نشده، درِ «در انتظار» می‌ماند و به تحویل نمی‌رود', async () => {
    const first = await ready('/master?stage=fundamental&preset=custom');
    const table = screen.getByTestId('funnel-stage-fundamental');
    expect(within(table).getAllByText(/گزارشش نرسیده/).length).toBeGreaterThan(0);
    first.unmount();
    await ready('/master?stage=handover&preset=custom');
    // گام چهارم: «شپنا» درِ جدولِ اصلیِ تحویل نیست (بنیادش سنجیده نشده) و فقط
    // درِ صفِ «در انتظار»ِ همان کارت می‌نشیند.
    const hand = screen.getByTestId('funnel-stage-handover');
    const main = within(within(hand).getByTestId('funnel-scroll-handover'));
    expect(main.queryByText('شپنا')).not.toBeInTheDocument();
    expect(main.getByText('فولاد')).toBeInTheDocument();
    expect(within(within(hand).getByTestId('funnel-pending-handover')).getByText('شپنا'))
      .toBeInTheDocument();
  });

  it('دلیلِ هر ردیف درِ خودِ جدول دیده می‌شود، نه در tooltip', async () => {
    await ready('/master?stage=tape&preset=custom');
    const tape = screen.getByTestId('funnel-stage-tape');
    expect(within(tape).getByRole('columnheader', { name: 'دلیل' })).toBeInTheDocument();
    expect(within(tape).getByTestId('funnel-why-سپ').textContent).toContain('حجم مشکوک');
  });

  it('شمارشِ هر گام از همان پاسخ می‌آید: پنج وضعیت رویِ جامعۀ غربالگری', async () => {
    const f = funnelFromApi(FUNNEL_FIXTURE);
    expect(f.total).toBe(4);                       // Y = واجدِ شرایطِ غربالگری
    expect(f.marketUniverse).toBe(5);              // X = جامعۀ تابلو
    expect(f.excludedCount).toBe(1);               // Z = خارج‌ها
    expect(f.marketUniverse).toBe(f.total + f.excludedCount); // X = Y + Z
    expect(f.boardScope).toBe(5);
    // coverageِ بک‌اند عیناً می‌نشیند — فرانت چیزی نمی‌شمارد که سرور گفته باشد.
    expect(f.counts.tape).toEqual({ pass: 3, reject: 1, pending: 0, unavailable: 0, not_required: 0 });
    expect(f.counts.technical.not_required).toBe(1);   // «سپ» درِ تابلو رد شده
    expect(f.counts.fundamental.not_required).toBe(2); // «سپ» + «همراه»
    expect(f.stages.technical.entries.find((e) => e.symbol === 'همراه')?.status.technical).toBe('reject');
    expect(f.stages.fundamental.pending.find((e) => e.symbol === 'شپنا')?.status.fundamental)
      .toBe('pending');
  });

  it('خارج از جامعۀ غربالگری درِ هیچ جدولِ گامی نمی‌نشیند (جدول شلوغ نمی‌شود)', () => {
    const f = funnelFromApi(FUNNEL_FIXTURE);
    for (const key of ['tape', 'technical', 'fundamental', 'handover'] as const) {
      expect(f.stages[key].entries.some((e) => e.symbol === 'آبادا'), key).toBe(false);
      expect(f.stages[key].pending.some((e) => e.symbol === 'آبادا'), key).toBe(false);
    }
    // ولی گم هم نمی‌شود: علتش درِ مدل هست و از خودِ سرور آمده، نه ساختگی.
    expect(f.exclusions.map((e) => e.symbol)).toEqual(['آبادا']);
    expect(f.exclusions[0].reasonCode).toBe('STOPPED');
    expect(f.exclusions[0].humanReason).toContain('مشمول فرایند تعلیق');
    expect(f.exclusionLabels.STOPPED).toBe('متوقف');
  });

  it('هیچ نمادی از هیچ گامی گم نمی‌شود: جدولِ هر گام = کلِ جامعۀ غربالگری', () => {
    const f = funnelFromApi(FUNNEL_FIXTURE);
    for (const key of ['tape', 'technical', 'fundamental', 'handover'] as const) {
      const s = f.stages[key];
      expect(s.entries.length + s.pending.length, key).toBe(f.total);
      expect(s.ruled, key).toBe(f.total);
      expect(s.summary.pass + s.summary.reject + s.summary.pending
              + s.summary.unavailable + s.summary.not_required, key).toBe(f.total);
    }
    // آنکه تابلو رد کرده درِ گامِ تکنیکال هم دیده می‌شود، با حکمِ «لازم نبود» —
    // نه اینکه غیب شود و «سنجیده نشده» خوانده شود.
    const sep = f.stages.technical.entries.find((e) => e.symbol === 'سپ');
    expect(sep?.status.technical).toBe('not_required');
    expect(sep?.why.technical).toContain('تابلو نماد را رد کرده');
  });

  // رأیِ مالک ۱۴۰۵-۰۷-۱۷: «به‌صورتِ زنده نشان بدهد در حال محاسبه». تا اسکنِ
  // پس‌زمینه running است یا نمادی در انتظارِ داوری، سرخط جای خودش را با
  // «در حال محاسبه» + شمارِ ساخته‌شده و صف عوض می‌کند.
  it('اسکنِ نرسیدهٔ تکنیکال پنهان نمی‌ماند و «در حال محاسبه» نشان می‌دهد', async () => {
    await ready('/master?stage=technical&preset=custom');
    const line = screen.getByTestId('funnel-computing');
    expect(line.textContent).toContain('در حال محاسبه');
    expect(line.textContent).toContain('ساخته‌شده: ۱۸');
    expect(line.textContent).toContain('در صف: ۲');
    expect(screen.queryByTestId('funnel-tech-coverage')).not.toBeInTheDocument();
  });

  it('بی‌صف، همان سرخط به «سنجیده شده» برمی‌گردد (برچسبِ در حال محاسبه همیشگی نیست)', async () => {
    restoreFetch();
    restoreFetch = installFunnelApi({
      ...FUNNEL_FIXTURE,
      tech_scan: { pending_symbols: 0, running: false, queued: 0, done: 20, failed: 0 },
    });
    await ready('/master?stage=technical&preset=custom');
    expect(screen.queryByTestId('funnel-computing')).not.toBeInTheDocument();
    expect(screen.getByTestId('funnel-tech-coverage').textContent).toContain('تکنیکال سنجیده شده');
  });

  it('«لازم نبود» درِ خودِ جدول دیده می‌شود، نه در tooltip', async () => {
    await ready('/master?stage=technical&preset=custom');
    const tech = screen.getByTestId('funnel-stage-technical');
    expect(within(tech).getByTestId('funnel-not-required-technical').textContent)
      .toContain('۱ لازم نبود');
    expect(within(tech).getByTestId('funnel-why-سپ').textContent)
      .toContain('تابلو نماد را رد کرده');
    expect(within(tech).getByTestId('funnel-ruled-technical').textContent)
      .toContain('کلِ جامعۀ غربالگری');
  });

  it('سایدبار نمادِ خارج از جامعه را «سنجیده نشده» نمی‌خواند', () => {
    const f = funnelFromApi(FUNNEL_FIXTURE);
    const p = stageProgressFor(f, 'آبادا');
    expect(p.map((x) => x.state))
      .toEqual(['not_in_universe', 'not_in_universe', 'not_in_universe', 'not_in_universe']);
    expect(p[0].why).toContain('مشمول فرایند تعلیق');
    // نمادِ داخلِ جامعه همان حکمهایِ همیشگی را می‌گیرد — این شاخهٔ جدید کورشان نمی‌کند.
    expect(stageProgressFor(f, 'سپ')[0].state).toBe('blocked');
    expect(stageProgressFor(f, 'فولاد').map((x) => x.state))
      .toEqual(['passed', 'passed', 'passed', 'passed']);
  });

  it('خلاصۀ دو جامعه درِ خطِ شمارش؛ علتِ خروج فقط درِ بخشِ بازشونده', async () => {
    await ready('/master?stage=tape&preset=custom');
    // X / Y / Z هر سه رویِ صفحه‌اند — نه یکی به‌جای دیگری.
    expect(screen.getByTestId('funnel-universe-market').textContent).toContain('۵');
    expect(screen.getByTestId('funnel-universe-screening').textContent).toContain('۴');
    const toggle = screen.getByTestId('funnel-universe-excluded');
    expect(toggle.textContent).toContain('۱');
    // بسته است: خارج‌ها درِ جدولِ گام‌ها شلوغی نمی‌کنند.
    expect(screen.queryByTestId('funnel-exclusions')).not.toBeInTheDocument();
    fireEvent.click(toggle);
    const panel = screen.getByTestId('funnel-exclusions');
    expect(within(panel).getByTestId('funnel-exclusion-STOPPED').textContent)
      .toContain('متوقف');
    expect(within(panel).getByTestId('funnel-exclusion-row-آبادا').textContent)
      .toContain('آبادا');
  });
});

describe('ساختارِ workspace (رأیِ مالک ۱۴-۰۷-۶)', () => {
  it('بی‌?stage= مستقیم گام تابلوخوانی باز می‌شود، نه صفحۀ نقشه راه', async () => {
    withClient(<FtsFunnelStages preset="custom" onPresetChange={() => {}} />, '/master');
    await waitFor(() => expect(screen.getByTestId('funnel-stage-tape')).toBeInTheDocument());
    expect(screen.getByTestId('fts-funnel-workspace')).toBeInTheDocument();
    expect(screen.queryByTestId('fts-funnel-overview')).not.toBeInTheDocument();
    expect(screen.queryByTestId('funnel-stage-technical')).not.toBeInTheDocument();
  });

  it('سه سیستمِ انتخابی یک‌جا و فعال پریده می‌ماند؛ ساعت‌شنی درِ انتخابگر نیست', async () => {
    await ready('/master?stage=tape&preset=swing');
    for (const m of ['swing', 'trend', 'custom']) {
      expect(screen.getByTestId(`funnel-mode-${m}`)).toBeInTheDocument();
    }
    expect(screen.getByTestId('funnel-mode-swing')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.queryByTestId('funnel-mode-hourglass')).not.toBeInTheDocument();
  });

  it('کلیک رویِ روندگیر افق را به والد می‌دهد؛ Custom افق سراسری را دست نمی‌زند', async () => {
    const seen: string[] = [];
    withClient(<FtsFunnelStages preset="swing" onPresetChange={(p) => seen.push(p)} />,
               '/master?stage=tape');
    await waitFor(() => expect(screen.getByTestId('funnel-mode-trend')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('funnel-mode-trend'));
    fireEvent.click(screen.getByTestId('funnel-mode-custom'));
    expect(seen).toEqual(['trend']);
    expect(useFunnelPrefsStore.getState().preset).toBe('custom');
  });

  it('چهار گام به‌صورتِ تب‌هایِ فشرده‌اند و گامِ فعال aria-current دارد', async () => {
    await ready('/master?stage=fundamental&preset=custom');
    const nav = screen.getByTestId('fts-process-stepper');
    for (const s of ['tape', 'technical', 'fundamental', 'handover']) {
      expect(within(nav).getByTestId(`fts-step-${s}`)).toBeInTheDocument();
    }
    expect(within(nav).getByTestId('fts-step-fundamental')).toHaveAttribute('aria-current', 'step');
  });

  it('سرستون‌هایِ هر گام با همان گام است + ستونِ دلیل', async () => {
    await ready('/master?stage=technical&preset=custom');
    const tech = screen.getByTestId('funnel-stage-technical');
    for (const h of ['هفتگی', 'روزانه', 'شاخه', 'شواهد', 'داوری', 'دلیل']) {
      expect(within(tech).getByRole('columnheader', { name: h })).toBeInTheDocument();
    }
    expect(within(tech).queryByRole('columnheader', { name: 'حجم/ماه' })).not.toBeInTheDocument();
  });
});

describe('زنجیرۀ Custom', () => {
  beforeEach(() => useFunnelPrefsStore.getState().resetToCanonical());

  it('افزودن، حذف و جابه‌جایی ترتیب را درِ حالتِ canonical ثبت می‌کند', () => {
    const s = () => useFunnelPrefsStore.getState().chain;
    useFunnelPrefsStore.getState().addFilter('f_susp');
    useFunnelPrefsStore.getState().addFilter('f_noqteh');
    useFunnelPrefsStore.getState().addFilter('f_smart');
    expect(s()).toEqual(['f_susp', 'f_noqteh', 'f_smart']);
    useFunnelPrefsStore.getState().moveFilter(0, 2);
    expect(s()).toEqual(['f_noqteh', 'f_smart', 'f_susp']);
    useFunnelPrefsStore.getState().removeFilter('f_smart');
    expect(s()).toEqual(['f_noqteh', 'f_susp']);
    // ترتیبِ متفاوت باید درِ درخواستِ تازه هم دیده شود (نه فقط درِ state)
    useFunnelPrefsStore.getState().addFilter('f_roobi');
    expect(s()).toEqual(['f_noqteh', 'f_susp', 'f_roobi']);
  });

  it('ذخیره/بازخوانیِ preset دقیقاً همان زنجیره و سخت‌گیری را برمی‌گرداند', () => {
    const st = useFunnelPrefsStore.getState();
    st.addFilter('f_susp'); st.addFilter('f_noqteh'); st.setFundMode('hard');
    const id = useFunnelPrefsStore.getState().saveChain('فیلتر شخصی من', 'deadbeefcafe');
    useFunnelPrefsStore.getState().resetToCanonical();
    expect(useFunnelPrefsStore.getState().chain).toEqual([]);
    useFunnelPrefsStore.getState().loadChain(id);
    const back = useFunnelPrefsStore.getState();
    expect(back.chain).toEqual(['f_susp', 'f_noqteh']);
    expect(back.fundMode).toBe('hard');
    expect(back.savedChains[0].registryVersion).toBe('deadbeefcafe');
    expect(typeof back.savedChains[0].createdAt).toBe('number');
  });

  it('استثنای بنیادی صریح و نماد‌محور است، نه جبرانِ خودکار', () => {
    useFunnelPrefsStore.getState().setException('شپنا', ['I1']);
    expect(useFunnelPrefsStore.getState().exceptions).toEqual({ شپنا: ['I1'] });
    useFunnelPrefsStore.getState().setException('شپنا', []);
    expect(useFunnelPrefsStore.getState().exceptions).toEqual({});
  });
});

describe('بازسازِ Custom درِ همان workspace (§۵ §۸ §۱۰)', () => {
  it('فیلترها از رجیستری می‌آیند، نه از arrayِ پنج‌تاییِ پیشین', async () => {
    await ready('/master?stage=tape&preset=custom');
    fireEvent.click(screen.getByTestId('funnel-chain-add'));
    const menu = screen.getByTestId('funnel-chain-menu');
    // «پول هوشمند» و «کد به کد» درِ چیپ‌هایِ قدیمیِ Custom نبودند؛ درِ رجیستری هستند
    expect(within(menu).getByTestId('funnel-chain-pick-f_smart')).toBeInTheDocument();
    expect(within(menu).getByTestId('funnel-chain-pick-f_legal')).toBeInTheDocument();
    expect(within(menu).getAllByRole('menuitem')).toHaveLength(7);
  });

  it('افزودن، شمارشِ ترتیبیِ همان گام را کنارِ چیپ می‌گذارد', async () => {
    useFunnelPrefsStore.getState().addFilter('f_susp');
    await ready('/master?stage=tape&preset=custom');
    const chip = screen.getByTestId('funnel-chain-f_susp');
    expect(within(chip).getByTestId('funnel-chain-count-f_susp').textContent).toBe('۴ ← ۳');
  });

  it('جابه‌جاییِ چیپ، ترتیبِ زنجیره را عوض می‌کند', async () => {
    useFunnelPrefsStore.getState().addFilter('f_susp');
    useFunnelPrefsStore.getState().addFilter('f_noqteh');
    await ready('/master?stage=tape&preset=custom');
    fireEvent.click(screen.getByTestId('funnel-chain-up-f_noqteh'));
    expect(useFunnelPrefsStore.getState().chain).toEqual(['f_noqteh', 'f_susp']);
    const order = Array.from(
      document.querySelectorAll('[data-testid^="funnel-chain-f_"]'),
    ).map((el) => el.getAttribute('data-testid'));
    expect(order).toEqual(['funnel-chain-f_noqteh', 'funnel-chain-f_susp']);
  });

  it('ذخیره و بازخوانی، همان زنجیره را دقیق برمی‌گرداند', async () => {
    useFunnelPrefsStore.getState().addFilter('f_susp');
    useFunnelPrefsStore.getState().addFilter('f_noqteh');
    await ready('/master?stage=tape&preset=custom');
    fireEvent.change(screen.getByTestId('funnel-chain-name'), { target: { value: 'فیلترِ من' } });
    fireEvent.click(screen.getByTestId('funnel-chain-save'));
    expect(useFunnelPrefsStore.getState().savedChains[0].chain).toEqual(['f_susp', 'f_noqteh']);
    expect(useFunnelPrefsStore.getState().savedChains[0].registryVersion).toBe('deadbeefcafe');
    fireEvent.click(screen.getByTestId('funnel-chain-reset'));
    expect(useFunnelPrefsStore.getState().chain).toEqual([]);
    fireEvent.click(screen.getByTestId('funnel-chain-load-فیلترِ من'));
    expect(useFunnelPrefsStore.getState().chain).toEqual(['f_susp', 'f_noqteh']);
  });

  it('حذفِ چیپ فقط همان فیلتر را از زنجیره بیرون می‌اندازد', async () => {
    useFunnelPrefsStore.getState().addFilter('f_susp');
    useFunnelPrefsStore.getState().addFilter('f_jet');
    await ready('/master?stage=tape&preset=custom');
    fireEvent.click(screen.getByTestId('funnel-chain-remove-f_susp'));
    expect(useFunnelPrefsStore.getState().chain).toEqual(['f_jet']);
    expect(screen.queryByTestId('funnel-chain-f_susp')).not.toBeInTheDocument();
  });
});

describe('حفظِ حالت', () => {
  it('گذر از سطر، گام را درِ مسیر نگه می‌دارد تا بازگشت به همان‌جا برگردد', async () => {
    withClient(<FtsFunnelStages preset="custom" onPresetChange={() => {}} />,
               '/master?stage=handover&preset=custom');
    await waitFor(() => expect(
      screen.getByTestId('funnel-stage-tape').querySelector('tbody tr')).toBeTruthy(),
      { timeout: 4000 });
    const tr = screen.getByTestId('funnel-stage-tape').querySelector('tbody tr');
    fireEvent.click(tr!.querySelector('button')!);
    expect(useSymbolStore.getState().symbol).toBe('فولاد');
    expect(screen.getByTestId('funnel-stage-tape')).toBeInTheDocument();
  });

  it('پاسخِ بی‌داده صفحه را نمی‌شکند: جای خالی با علت می‌آید', async () => {
    restoreFetch();
    // پاسخِ واقعیِ no_data هیچ ردیفی ندارد: نه entries، نه matrix، نه coverage.
    restoreFetch = installFunnelApi({ ...FUNNEL_FIXTURE, entries: {}, status_matrix: {},
                                       coverage: undefined, status: 'no_data' });
    withClient(<FtsFunnelStages preset="custom" onPresetChange={() => {}} />,
               '/master?stage=handover&preset=custom');
    await waitFor(() => expect(screen.getByTestId('funnel-stage-handover')).toBeInTheDocument());
    expect(screen.getByTestId('funnel-stage-handover').querySelectorAll('tbody tr')).toHaveLength(0);
  });
});
