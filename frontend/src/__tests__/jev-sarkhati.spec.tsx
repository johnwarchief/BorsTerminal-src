// src/__tests__/jev-sarkhati.spec.tsx — لایۀ jev-ui درِ تبِّ سرخطی: چه کاری
// می‌کند، چه کاری نمی‌کند، و چه چیزی بیرون نمی‌فرستد
//
// پنج پرسشِ این آزمون ازِ اصلاحیهٔ مالک می‌آید، نه از سلیقهٔ نویسنده:
//  ۱) قاعده‌ها واقعاً آرایشِ پنل‌هایِ ثانویه را عوض می‌کنند؟ (و درِ حالتِ عادی
//     هیچ چیز جابه‌جا نمی‌شود — یعنی لایه تزئینی نیست)
//  ۲) راهنما فقط «اضافه» می‌شود؟ (با کلیکِ تکراری ظاهر می‌شود، بی‌آن‌که
//     کنترلِ ضروری‌ای به دیدنی‌بودنش وابسته باشد)
//  ۳) خطایِ resolver و حالتِ pending هیچ‌چیز را خراب نمی‌کنند؟
//  ۴) بدونِ شبکه و بدونِ کلید کار می‌کند؟ (fetch هرگز صدا زده نمی‌شود)
//  ۵) چه چیزی به resolver می‌رسد؟ نماد، قیمت، حجم، برچسبِ حساب و شناسۀِ
//     سفارش باید درِ `app` و درِ `sent` نباشند. این سنجشِ serialized است،
//     نه خواندنِ کامنت.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Decision } from 'jev-ui';
import { SarkhatiProTools, DEFAULT_PRO_IDS, type ProItem }
  from '@features/portfolio/components/sarkhati/SarkhatiProTools';
import { appStateForJev, resolveJevRules, JEV_TRANSPORT, type JevAppState }
  from '@features/portfolio/lib/jevSarkhati';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const ITEMS: ProItem[] = [
  { id: 'schedule', label: 'زمان‌بندی', testId: 'sarkhati-tab-schedule' },
  { id: 'risk', label: 'ریسک و ایمنی', testId: 'sarkhati-tab-risk' },
  { id: 'monitor', label: 'پایش و سابقه', testId: 'sarkhati-tab-monitor' },
];

const HINT = {
  short: 'نشستِ راستی‌آزمایی‌شده نداریم',
  extra: 'مسیرِ بازکردن: «اتصال»',
  detail: '«ادامۀ دستوری» درِ ریسک و ایمنی لازم است',
};

function baseApp(patch: Partial<JevAppState> = {}): JevAppState {
  return {
    canTrade: true, halted: false, session: 'connected', mode: 'mock',
    hasScheduled: false, hasUnclear: false, panel: 'schedule', ...patch,
  };
}

const order = () => screen.getAllByTestId(/sarkhati-tab-(schedule|risk|monitor)/)
  .map((el) => el.getAttribute('data-ranked-id') ?? '');

function setup(props: Partial<Parameters<typeof SarkhatiProTools>[0]> = {}) {
  const onSelect = vi.fn();
  render(
    <SarkhatiProTools items={ITEMS} app={baseApp()} panel="schedule" suggestedGo="risk"
      hint={HINT} onSelect={onSelect} trackDwell={false} {...props} />,
  );
  return { onSelect };
}

describe('قاعده‌ها: آرایشِ پنل‌هایِ ثانویه', () => {
  it('حالتِ عادی = همان ترتیبِ امروز؛ لایه بی‌سروصدی اضافه نمی‌شود', async () => {
    setup();
    await waitFor(() => expect(order()).toEqual([...DEFAULT_PRO_IDS]));
  });

  it('توقفِ اضطراری ← «ریسک و ایمنی» بالا می‌آید', async () => {
    setup({ app: baseApp({ halted: true, canTrade: false, session: 'expired' }) });
    await waitFor(() => expect(order()[0]).toBe('risk'));
    expect(order()).toHaveLength(3); // هیچ پنلی حذف نمی‌شود
  });

  it('نتیجۀ نامعلوم ← «پایش و سابقه» بالا می‌آید', async () => {
    setup({ app: baseApp({ hasUnclear: true }) });
    await waitFor(() => expect(order()[0]).toBe('monitor'));
  });

  it('سفارشِ زمان‌بندی‌شده ← «زمان‌بندی» اول می‌ماند و بقیه نزدیکش می‌شوند', async () => {
    setup({ app: baseApp({ hasScheduled: true }) });
    await waitFor(() => expect(order()).toEqual(['schedule', 'monitor', 'risk']));
  });

  it('کنترلِ منفی: اگر قاعدۀِ توقفِ اضطراری برداشته شود، آزمونِ بالا باید قرمز شود', async () => {
    const d = { id: 'sarkhati_pro_rank', question: { type: 'choice' as const, instructions: 'x', criteria: {} } };
    const halted = await resolveJevRules([d], { app: baseApp({ halted: true }) });
    const normal = await resolveJevRules([d], { app: baseApp() });
    const first = (o: typeof halted) => Object.entries(
      (o.answers['sarkhati_pro_rank'] as { probabilities: Record<string, number> }).probabilities)
      .sort((a, b) => b[1] - a[1])[0][0];
    expect(first(halted)).toBe('risk');
    expect(first(normal)).toBe('schedule');
    expect(first(halted)).not.toBe(first(normal));
  });
});

describe('راهنما: فقط اضافه، و فقط وقتی لازم است', () => {
  it('با دروازۀ باز و بی‌نشانهٔ گیرکردن، راهنما نیست — و هیچ چیز دیگری هم کم نمی‌شود', async () => {
    setup();
    await waitFor(() => expect(order()).toHaveLength(3));
    expect(screen.queryByTestId('sarkhati-hint')).toBeNull();
  });

  it('سه کلیکِ تکراری رویِ یک مقصد باِ دروازۀ بسته ← راهنما ظاهر می‌شود', async () => {
    setup({ app: baseApp({ canTrade: false, session: 'expired' }) });
    await waitFor(() => expect(order()).toHaveLength(3));
    for (let i = 0; i < 3; i += 1) fireEvent.click(screen.getByTestId('sarkhati-tab-monitor'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-hint')).toBeTruthy());
    // بلندیِ راهنما ازِ همان useScore می‌آید: mode=mock + تکرار ← سه بریده
    expect(screen.getByTestId('sarkhati-hint').getAttribute('data-level')).toBe('2');
    expect(screen.getByTestId('sarkhati-hint').textContent).toContain(HINT.detail);
  });

  it('هر سه چیپ همیشه دیدنی‌اند، چه راهنما باشد چه نباشد', async () => {
    const withHint = setup({ app: baseApp({ canTrade: false, session: 'auth_failed' }) });
    await waitFor(() => expect(order()).toHaveLength(3));
    for (let i = 0; i < 4; i += 1) fireEvent.click(screen.getByTestId('sarkhati-tab-risk'));
    await waitFor(() => expect(screen.getByTestId('sarkhati-hint')).toBeTruthy());
    expect(screen.getAllByTestId(/sarkhati-tab-(schedule|risk|monitor)/)).toHaveLength(3);
    expect(withHint.onSelect).toHaveBeenCalled();
  });
});

describe('fallbackِ قطعی: شبکه، کلید، و خطایِ resolver', () => {
  it('هیچ درخواستِ شبکه‌ای ساخته نمی‌شود؛ نه هنگامِ رندر، نه هنگامِ کلیک', async () => {
    setup({ app: baseApp({ halted: true, canTrade: false }) });
    await waitFor(() => expect(order()).toHaveLength(3));
    fireEvent.click(screen.getByTestId('sarkhati-tab-risk'));
    await waitFor(() => expect(order()).toHaveLength(3));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('resolver اگر بترکد، چیپ‌ها باِ ترتیبِ خام می‌مانند و راهنما نمی‌آید', async () => {
    setup({ resolve: async () => { throw new Error('resolver down'); } });
    await waitFor(() => expect(screen.getAllByTestId(/sarkhati-tab-(schedule|risk|monitor)/))
      .toHaveLength(3));
    expect(order()).toEqual([...DEFAULT_PRO_IDS]);
    expect(screen.queryByTestId('sarkhati-hint')).toBeNull();
  });

  it('meta هیچ ادعایِ مدل، usage یا هزینه نمی‌سازد', async () => {
    const decisions: Decision[] = [
      { id: 'sarkhati_pro_rank', question: { type: 'choice', instructions: 'x', criteria: {} } },
      { id: 'sarkhati_hint', question: { type: 'noul', instructions: 'y' } },
    ];
    const out = await resolveJevRules(decisions, { app: baseApp({ halted: true }) });
    expect(out.meta.transport).toBe(JEV_TRANSPORT);
    expect(out.meta.requests).toBe(0);
    expect(out.meta.model).toBeUndefined();
    expect(out.meta.usage).toBeUndefined();
    expect(out.meta.costUsd).toBeUndefined();
    expect(out.meta.estimated).toBeUndefined();
    expect(Object.keys(out.answers).sort()).toEqual(['sarkhati_hint', 'sarkhati_pro_rank']);
  });
});

describe('سانسورِ داده: چه چیزی به resolver می‌رسد', () => {
  // پاسخِ نمونه باِ چند فیلدِ حساسِ واقعی‌نما ساخته می‌شود. کنترلی که سنسور را
  // زنده نگه می‌دارد: همان رشته‌ها درِ `STATUS` پیدا می‌شوند (خطِ «مثبت»)، پس
  // نبودشان درِ payload کارِ `appStateForJev` است، نه بی‌داده‌بودنِ تست.
  // نماد/قیمت/حجم اصلاً درِ ورودیِ این تابع نیستند؛ ازِ همان اول جدا ساخته شده.
  const STATUS = {
    adapter: 'mofid', dry_run: true, read_only: false, live_enabled: false,
    traffic_allowed: true, session: { state: 'connected', account_label: 'IR-123456789' },
    ledger_size: 9, durable_events: 14, kill_reason: null, blocked_on: ['confirm_gate'],
  };

  it('app فقط هفت کلیدِ غیرحساس است', () => {
    const app = appStateForJev({
      canTrade: false, halted: true, session: 'expired', status: STATUS,
      hasScheduled: true, hasUnclear: true, panel: 'risk',
    });
    expect(Object.keys(app).sort()).toEqual(
      ['canTrade', 'halted', 'hasScheduled', 'hasUnclear', 'mode', 'panel', 'session']);
    expect(app.mode).toBe('dry_run');
    expect(app.session).toBe('expired');
  });

  it('کنترلِ مثبت: فیلدهایِ حساس درِ خودِ پاسخِ سرویس هست', () => {
    const raw = JSON.stringify(STATUS);
    for (const needle of ['IR-123456789', 'mofid', 'ledger_size', 'blocked_on']) {
      expect(raw, `سنسور بی‌مصرف است: «${needle}» درِ پاسخ نیست`).toContain(needle);
    }
  });

  it('هیچ نشانیِ کارگزاری، حساب یا شمارشی درِ payloadِ resolver نیست', async () => {
    const app = appStateForJev({
      canTrade: false, halted: false, session: 'auth_failed', status: STATUS,
      hasScheduled: false, hasUnclear: false, panel: 'connect',
    });
    const decisions: Decision[] = [
      { id: 'sarkhati_pro_rank', question: { type: 'choice', instructions: 'x', criteria: {} } },
      { id: 'sarkhati_hint', question: { type: 'noul', instructions: 'y' } },
    ];
    const out = await resolveJevRules(decisions, { app, recent_actions: ['pro:risk'] });
    const wire = JSON.stringify(out.sent);
    for (const leak of ['IR-123456789', 'account_label', 'mofid', 'ledger_size',
      'durable_events', 'blocked_on', 'confirm_gate']) {
      expect(wire, `نشتِ «${leak}» درِ payloadِ resolver`).not.toContain(leak);
    }
    // و کنترلِ مثبتِ همان سنسور درِ سمتِ مقابل: داده‌ای که *باید* برود، رفته است
    expect(wire).toContain('"halted":false');
    expect(wire).toContain('sarkhati_pro_rank');
  });

  it('buildPayload فقط کانال‌هایِ اعلام‌شده را می‌برد (app، recent_actions)', async () => {
    const out = await resolveJevRules(
      [{ id: 'sarkhati_hint', question: { type: 'noul', instructions: 'y' } }] as Decision[],
      { app: baseApp({ canTrade: false }), recent_actions: ['pro:risk', 'pro:risk'] });
    expect(Object.keys(out.sent.state).sort()).toEqual(['app', 'recent_actions']);
  });
});
