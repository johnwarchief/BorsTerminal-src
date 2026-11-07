// src/__tests__/jev-ui-compat.spec.tsx — سازگاریِ واقعیِ jev-ui با این SPA
//
// چرا این فایل هست: مالک خواسته ادغامِ jev-ui از روی سورس و تستِ واقعی اثبات
// شود، نه از روی مستنداتِ Next.js. پس اینجا هیچ Next.js و هیچ Server Action و
// هیچ کلیدِ API نیست؛ فقط همان چیزی که درِ این پروژه ممکن است: تابعِ `resolve`
// تزریق‌شده به `JevProvider`. چهار چیز سنجیده می‌شود:
//  ۱) بسته درِ Vite/jsdom با React ۱۸ قابلِ import و رندر است (دستورِ
//     `'use client'` رویِ سرتاسرِ ماژول‌ها برایِ باندلر بی‌اثر است).
//  ۲) سه حالتِ داوری (choice / score / noul) از همان resolve می‌آیند و به
//     Branch، Rank، Gate و useScore می‌رسند.
//  ۳) fallback قطعی است: خطایِ resolver، پاسخِ ناشناس، و اطمینانِ پایین هیچ‌وقت
//     «حذفِ محتوا» نمی‌شوند؛ حالتِ اولیهٔ خودشان برمی‌گردد.
//  ۴) هیچ درخواستِ شبکه‌ای ساخته نمی‌شود (fetchِ کاذب اگر صدا زده شود، تست قرمز
//     است).
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Branch, Gate, JevProvider, Option, Rank, useScore } from 'jev-ui';
import type { Answer, BaseState, Decision, ResolveOutcome } from 'jev-ui';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

const choice = (c: string, probabilities: Record<string, number>, confidence = 0.9): Answer =>
  ({ type: 'choice', choice: c, probabilities, confidence });
const noul = (v: number): Answer => ({ type: 'noul', noul: v });
const scored = (v: number, confidence = 0.9): Answer =>
  ({ type: 'score', score: v, probabilities: {}, confidence });

/** پاسخ‌ها را آرایه‌ایِ کنترل‌شده می‌دهیم: تصمیمِ تست، نه تصمیمِ مدل. */
function fallbackAnswer(d: Decision): Answer {
  if (d.question.type === 'choice') return choice('__none__', {}, 0);
  if (d.question.type === 'score') return scored(0);
  return noul(0);
}
function resolverFor(answers: Record<string, Answer>, onCall?: (d: Decision[], b: BaseState) => void) {
  return async (decisions: Decision[], base: BaseState): Promise<ResolveOutcome> => {
    onCall?.(decisions, base);
    return {
      answers: Object.fromEntries(decisions.map((d) => [d.id, answers[d.id] ?? fallbackAnswer(d)])),
      meta: { transport: 'test-controlled', requests: 1, decisions: decisions.length, ms: 3 },
      sent: { state: {}, questions: Object.fromEntries(decisions.map((d) => [d.id, d.question])) },
    };
  };
}

const throwing = (message: string) => async () => { throw new Error(message); };

describe('jev-ui در این پروژه: رندر، داوری، و fallback', () => {
  it('Gate یک affordance را «اضافه» می‌کند و هیچ‌چیز را از primary نمی‌گیرد', async () => {
    render(
      <JevProvider resolve={resolverFor({ hint: noul(0.91) })}>
        <p data-testid="primary">فرمِ سفارش همیشه اینجاست</p>
        <Gate id="hint" ask="آیا کاربر به راهنماییِ همین قدم نیاز دارد؟" otherwise={null}>
          <p data-testid="added">راهنما: اولِ اتصال را بررسی کن</p>
        </Gate>
      </JevProvider>,
    );
    expect(screen.getByTestId('primary')).toBeTruthy();
    // بسته_while_resolving: درِ pending راهنما نباید چشمک بزند
    expect(screen.queryByTestId('added')).toBeNull();
    await waitFor(() => expect(screen.getByTestId('added')).toBeTruthy());
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('Gate با احتمالِ پایین باز نمی‌شود، ولی صفحه کامل می‌ماند', async () => {
    render(
      <JevProvider resolve={resolverFor({ hint: noul(0.2) })}>
        <Gate id="hint" ask="راهنمایی لازم است؟" otherwise={<p data-testid="closed">بدونِ راهنما</p>}>
          <p data-testid="added">راهنما</p>
        </Gate>
      </JevProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('closed')).toBeTruthy());
    expect(screen.queryByTestId('added')).toBeNull();
  });

  it('Branch زیردرختِ انتخاب‌شده را رندر می‌کند', async () => {
    render(
      <JevProvider resolve={resolverFor({ step: choice('symbol', { symbol: 0.8, order: 0.2 }) })}>
        <Branch id="step" ask="کاربر درِ کدام قدم است؟"
          pending={<p data-testid="pend">درِ حالِ داوری</p>}>
          <Option k="connect" when="هنوز اتصالِ راستی‌آزمایی‌شده ندارد">اتصال</Option>
          <Option k="symbol" when="اتصال دارد ولی نماد انتخاب نکرده">نماد</Option>
          <Option fallback>متنِ پیش‌فرضِ قدم</Option>
        </Branch>
      </JevProvider>,
    );
    expect(screen.getByTestId('pend')).toBeTruthy();
    await waitFor(() => expect(screen.getByText('نماد')).toBeTruthy());
    expect(screen.queryByText('متنِ پیش‌فرضِ قدم')).toBeNull();
  });

  it('Branch با اطمینانِ پایین یا پاسخِ ناشناس به fallback می‌رود، نه به حدس', async () => {
    const low = render(
      <JevProvider resolve={resolverFor({ step: choice('symbol', { symbol: 0.5 }, 0.2) })}>
        <Branch id="step" ask="قدم؟" minConfidence={0.6}>
          <Option k="symbol" when="نماد انتخاب نشده">نماد</Option>
          <Option fallback>متنِ پیش‌فرضِ قدم</Option>
        </Branch>
      </JevProvider>,
    );
    await waitFor(() => expect(low.getByText('متنِ پیش‌فرضِ قدم')).toBeTruthy());
    expect(low.queryByText('نماد')).toBeNull();

    const unknown = render(
      <JevProvider resolve={resolverFor({ step: choice('something_else', { something_else: 1 }) })}>
        <Branch id="step" ask="قدم؟">
          <Option k="symbol" when="نماد انتخاب نشده">نماد</Option>
          <Option fallback>متنِ پیش‌فرضِ دو</Option>
        </Branch>
      </JevProvider>,
    );
    await waitFor(() => expect(unknown.getByText('متنِ پیش‌فرضِ دو')).toBeTruthy());
  });

  it('Rank پنل‌هایِ ثانویه را مرتب می‌کند و pinTop ترتیبِ عادت را برمی‌گرداند', async () => {
    const items = [{ id: 'schedule' }, { id: 'risk' }, { id: 'monitor' }];
    const answers = { pro: choice('monitor', { schedule: 0.1, risk: 0.2, monitor: 0.7 }) };
    const pinned = render(
      <JevProvider resolve={resolverFor(answers)}>
        <Rank id="pro" items={items} ask="کدام ابزارِ حرفه‌ای الان مرتبط‌تر است؟"
          idOf={(i) => i.id} labelOf={(i) => i.id} pinTop={1}>
          {(ranked) => <p data-testid="p">{ranked.map((r) => r.id).join(',')}</p>}
        </Rank>
      </JevProvider>,
    );
    await waitFor(() => expect(pinned.getByTestId('p').textContent).toBe('schedule,monitor,risk'));

    // کنترلِ منفی: بی pinTop همان داوری ترتیبِ عادت را می‌شکند؛ پس پین کارِ خودش را کرده
    const free = render(
      <JevProvider resolve={resolverFor(answers)}>
        <Rank id="pro" items={items} ask="کدام ابزارِ حرفه‌ای الان مرتبط‌تر است؟"
          idOf={(i) => i.id} labelOf={(i) => i.id}>
          {(ranked) => <p data-testid="f">{ranked.map((r) => r.id).join(',')}</p>}
        </Rank>
      </JevProvider>,
    );
    await waitFor(() => expect(free.getByTestId('f').textContent).toBe('monitor,risk,schedule'));
  });

  it('Rank با take کوتاه می‌کند، و درِ خطایِ resolver ترتیبِ خام برمی‌گردد', async () => {
    const items = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];
    const short = render(
      <JevProvider resolve={resolverFor({ r: choice('c', { a: 0.1, b: 0.2, c: 0.7 }) })}>
        <Rank id="r" items={items} ask="مرتبط‌ترین؟" idOf={(i) => i.id} labelOf={(i) => i.id} take={2}>
          {(ranked) => <p data-testid="t">{ranked.map((x) => x.id).join(',')}</p>}
        </Rank>
      </JevProvider>,
    );
    await waitFor(() => expect(short.getByTestId('t').textContent).toBe('c,b'));

    const broken = render(
      <JevProvider resolve={throwing('resolver down')}>
        <Rank id="r" items={items} ask="مرتبط‌ترین؟" idOf={(i) => i.id} labelOf={(i) => i.id}>
          {(ranked, { status }) => (
            <p data-testid="err" data-status={status}>{ranked.map((x) => x.id).join(',')}</p>
          )}
        </Rank>
      </JevProvider>,
    );
    await waitFor(() => expect(broken.getByTestId('err').getAttribute('data-status')).toBe('error'));
    // خطایِ داوری نباید لیست را خالی کند: همان ترتیبِ کاندیداها می‌ماند
    expect(broken.getByTestId('err').textContent).toBe('a,b,c');
  });

  it('useScore فقط props را می‌راند؛ سطحِ چگالی از همان normalize می‌آید', async () => {
    function DensityProbe() {
      const { status, level, normalized } = useScore({
        id: 'density', ask: "کاربر چقدر با این صفحه آشناست؟",
        levels: ['آشنا نیست', 'کمی آشناست', 'آشناست'],
      });
      return <p data-testid="d" data-status={status} data-level={level} data-n={normalized.toFixed(2)} />;
    }
    render(
      <JevProvider resolve={resolverFor({ density: scored(2) })}>
        <DensityProbe />
      </JevProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('d').getAttribute('data-level')).toBe('آشناست'));
    expect(screen.getByTestId('d').getAttribute('data-n')).toBe('1.00');
  });

  it('بدونِ JevProvider هر چهار قابلیت خطایِ روشن می‌دهند، نه رندرِ نیمه', () => {
    // useJev عمداً throw می‌کند: بی‌Provider رندرِ نیمه نداریم، خطا نام دارد
    expect(() => render(<Gate id="g" ask="?" otherwise={null}>x</Gate>)).toThrow(/JevProvider/);
  });

  it('کانال‌هایِ state فقط واژه‌هایِ banded‌اند؛ عددِ خام به resolve نمی‌رسد', async () => {
    const seen: BaseState[] = [];
    render(
      <JevProvider
        state={{ app: { step: 'symbol', mode: 'dry_run' } }}
        track={{ cap: 4 }}
        resolve={resolverFor({ h: noul(0.6), time_spent: noul(0.6) }, (_d, b) => seen.push(b))}>
        <Gate id="h" ask="راهنما؟" otherwise={null}>x</Gate>
      </JevProvider>,
    );
    await waitFor(() => expect(seen.length).toBeGreaterThan(0));
    expect(seen[0].app).toEqual({ step: 'symbol', mode: 'dry_run' });
    expect(seen[0].recent_actions ?? []).toEqual([]);
    expect(JSON.stringify(seen[0])).not.toMatch(/price|quantity|symbolValue/);
  });
});
