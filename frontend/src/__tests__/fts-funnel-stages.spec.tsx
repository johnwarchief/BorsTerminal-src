// __tests__/fts-funnel-stages.spec.tsx — رندرِ قیف از پاسخِ /api/funnel
//
// این پرونده «منطق داوری» را تست نمی‌کند؛ منطق داوری درِ `funnel_engine.py` است و
// ۲۶ case درِ `dev/funnel_engine_v1.py` (ثبت‌شدۀ بیرونِ موتور) آن را می‌سنجد.
// چیزی که اینجا اثبات می‌شود دو چیز است:
//   ۱) فرانت همان حکمِ سرور را نمایش می‌دهد و دوباره داوری نمی‌کند — با ردیفِ
//      عمداً متناقض درِ فیکسچر («همراه» نشانه و امتیازِ پنج دارد ولی پاسخ می‌گوید
//      تکنیکالش رد شده؛ اگر فرانت خودش حکم بدهد، این تست می‌شکند).
//   ۲) ساختارِ UI که مالک خواست: یک workspace، سه سیستمِ انتخاب، چهار گام،
//      جدولِ مسلط، دلیلِ دیدنی، و حفظِ گام پس از بازگشت.
import type { ReactElement } from 'react';
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FtsFunnelStages } from '@features/master/ui/FtsFunnelStages';
import { funnelFromApi } from '@features/master/lib/funnelView';
import { useFunnelPrefsStore } from '@features/master/stores/funnelPrefsStore';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { FUNNEL_FIXTURE, installFunnelApi } from './fixtures/funnelApi';

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
    // گام چهارم فقط تحویل را نشان می‌دهد؛ «شپنا» درِ کارتِ بنیادی همان‌جا می‌ماند
    // (سنجیده‌نشده) و هرگز به فهرستِ تحویل نمی‌آید.
    const hand = screen.getByTestId('funnel-stage-handover');
    expect(within(hand).queryByText('شپنا')).not.toBeInTheDocument();
    expect(within(hand).getByText('فولاد')).toBeInTheDocument();
  });

  it('دلیلِ هر ردیف درِ خودِ جدول دیده می‌شود، نه در tooltip', async () => {
    await ready('/master?stage=tape&preset=custom');
    const tape = screen.getByTestId('funnel-stage-tape');
    expect(within(tape).getByRole('columnheader', { name: 'دلیل' })).toBeInTheDocument();
    expect(within(tape).getByTestId('funnel-why-سپ').textContent).toContain('حجم مشکوک');
  });

  it('شمارشِ هر گام از همان پاسخ می‌آید: ورودی، ماندگار، حذف‌شده', async () => {
    const f = funnelFromApi(FUNNEL_FIXTURE);
    expect(f.stages.tape.summary.pass).toBe(2);
    expect(f.stages.tape.entries).toHaveLength(3);
    expect(f.stages.technical.entries.find((e) => e.symbol === 'همراه')?.status.technical).toBe('reject');
    expect(f.stages.fundamental.entries.find((e) => e.symbol === 'شپنا')?.status.fundamental)
      .toBe('pending');
    expect(f.total).toBe(922);
    expect(f.boardScope).toBe(5865);
  });

  it('هیچ سقفِ پنهانی درِ مسیرِ نمایش نیست: هرچه پاسخ بدهد همان‌قدر ردیف است', async () => {
    const f = funnelFromApi(FUNNEL_FIXTURE);
    expect(f.stages.tape.entries.length).toBe(FUNNEL_FIXTURE.entries!.tape!.length);
    expect(f.stages.handover.entries.length).toBe(FUNNEL_FIXTURE.entries!.handover!.length);
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
    restoreFetch = installFunnelApi({ ...FUNNEL_FIXTURE, entries: {}, status: 'no_data' });
    withClient(<FtsFunnelStages preset="custom" onPresetChange={() => {}} />,
               '/master?stage=handover&preset=custom');
    await waitFor(() => expect(screen.getByTestId('funnel-stage-handover')).toBeInTheDocument());
    expect(screen.getByTestId('funnel-stage-handover').querySelectorAll('tbody tr')).toHaveLength(0);
  });
});
