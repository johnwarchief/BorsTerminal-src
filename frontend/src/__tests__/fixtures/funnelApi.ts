// __tests__/fixtures/funnelApi.ts — جوابِ دستیِ /api/funnel برایِ تستِ رندر
//
// چرا دستی (نه تولیدشده با موتور): اگر فیکسچر را از خودِ موتور بگیریم، تستِ
// فرانت فقط بازتابِ بک‌اند می‌شود و دیگر چیزی را اثبات نمی‌کند. اینجا عددِ
// وضعیت و دلیل را *ما* نوشته‌ایم؛ فرانت باید دقیقاً همان را نشان دهد — و اگر
// جایی دوباره داوری کند، همین تضادها او را می‌گیرند:
//   «همراه» درِ تابلو نشانه دارد و اسکرینرش پنج‌امتیاز است، ولی پاسخ می‌گوید
//    تکنیکالش رد شده ⇒ جدول باید رد نشان دهد، نه قبول.
//   «شپنا» پاسخِ بنیادی‌اش pending است ⇒ نباید درِ تحویل ظاهر شود.
import type { ApiPayload } from '@features/master/lib/funnelView';

const row = (
  symbol: string, name: string, over: Record<string, unknown> = {},
) => ({
  symbol, name, sector: 'فلزات اساسي', last: 1000, closing: 990, change_pct: 1.0,
  vol_ratio: 1.4, patterns: [] as string[], status: {}, why: {}, chain: [] as string[],
  score: null, primary_score: null, weekly: null, daily: null, branch: null,
  matrix: null, tech_status: null, tech_points: null, evidence: [] as string[],
  fib_zone: null, hourglass: null, inds: {}, ind_values: {}, pricing_mode: 'آزاد',
  excluded: false, exclusion_reasons: '', assembly_veto: false, assembly_why: '',
  as_of: 1_760_000_000, is_live: true, rank: null, ...over,
});

export const FUNNEL_FIXTURE: ApiPayload = {
  status: 'success',
  engine_version: '1',
  ruleset_version: 'deadbeefcafe',
  as_of: Math.floor(Date.now() / 1000),
  preset: 'custom',
  chain: ['f_susp', 'f_noqteh'],
  fund_mode: 'standard',
  universe: { board: 5865, screened: 922, joined: 922 },
  stages: {
    tape: {
      input: 922, matched: 3, removed: 919,
      steps: [
        { stage: 'tape', seq: 1, filter_id: 'f_susp', label: 'حجم مشکوک', input_count: 922,
          matched_count: 3, removed_count: 919, unmeasured_count: 0,
          parameter_set: { vol_mult: 3, min_trades: 50 },
          source_ref: 'docs/حجم مشکوک.txt#b8a185c4168be33e', formula_version: 'txt-1',
          backend_impl: 'tape_flags.suspicious_flag' },
        { stage: 'tape', seq: 2, filter_id: 'f_noqteh', label: 'نقطه زنی', input_count: 3,
          matched_count: 2, removed_count: 1, unmeasured_count: 0,
          parameter_set: { max_dist: 3, min_trades: 5 },
          source_ref: 'docs/نقطه زنی.txt#e5d4fd99a6811443', formula_version: 'txt-1',
          backend_impl: 'tape_flags.noqteh_flag' },
      ],
    },
    technical: { input: 3, matched: 2, counts: { pass: 2, reject: 1, pending: 0, unavailable: 0 } },
    fundamental: { input: 2, matched: 1, mode: 'standard',
                   counts: { pass: 1, reject: 0, pending: 1, unavailable: 0 } },
    handover: { input: 1, matched: 1, counts: { pass: 1, reject: 0, pending: 0, unavailable: 0 } },
  },
  entries: {
    tape: [
      row('فولاد', 'فولاد مبارکه اصفهان', { patterns: ['مشکوک', 'نقطه'],
        status: { tape: 'pass' }, rank: 1 }),
      row('همراه', 'همراه اول', { patterns: ['مشکوک'], score: 5,
        status: { tape: 'pass' }, rank: 2 }),
      row('سپ', 'اصلاح سپ', { patterns: ['نقطه'], status: { tape: 'reject' },
        why: { tape: [{ code: 'TAPE_F_SUSP_NO_MATCH', text: 'حجم مشکوک — نشانه در این نماد نیست' }] },
        rank: 3 }),
    ],
    technical: [
      row('فولاد', 'فولاد مبارکه اصفهان', { patterns: ['مشکوک', 'نقطه'],
        status: { tape: 'pass', technical: 'pass' }, weekly: 'up', daily: 'down',
        branch: 'فیبوناچی / CHoCH', matrix: 'PERMITTED', evidence: ['choch_bull'],
        tech_points: 2, score: 5, primary_score: 3, rank: 1 }),
      row('همراه', 'همراه اول', { patterns: ['مشکوک'], score: 5,
        status: { tape: 'pass', technical: 'reject' }, weekly: 'down', daily: 'up',
        matrix: 'REJECT', rank: 2,
        why: { technical: [{ code: 'WEEKLY_TREND_DOWN', text: 'روند هفتگی نزولی — وتوی قطعی' }] } }),
    ],
    fundamental: [
      row('فولاد', 'فولاد مبارکه اصفهان', { status: { tape: 'pass', technical: 'pass', fundamental: 'pass' },
        weekly: 'up', daily: 'down', branch: 'فیبوناچی / CHoCH', score: 5, primary_score: 3,
        inds: { i1: true, i2: true, i3: true, i4: true, i5: true },
        ind_values: { i1: 52, i2: 318, i3: 26, i4: 0.41 }, rank: 1 }),
      row('شپنا', 'شاخص فولاد شپنا', { status: { tape: 'pass', technical: 'pass', fundamental: 'pending' },
        weekly: 'up', daily: 'up', matrix: 'PERMITTED', score: 4, primary_score: 2,
        inds: { i1: null, i2: true, i3: true, i4: true, i5: true }, rank: 4,
        why: { fundamental: [{ code: 'FUND_I1_MISSING', text: 'I1 رشد فروش گزارشش نرسیده — رد نیست، سنجیده نشده' }] } }),
    ],
    handover: [
      row('فولاد', 'فولاد مبارکه اصفهان', { status: { tape: 'pass', technical: 'pass',
        fundamental: 'pass', handover: 'pass' }, weekly: 'up', daily: 'down',
        branch: 'فیبوناچی / CHoCH', score: 5, primary_score: 3,
        inds: { i1: true, i2: true, i3: true, i4: true, i5: true },
        ind_values: { i1: 52, i2: 318, i3: 26, i4: 0.41 }, rank: 1 }),
    ],
  },
  timeline: {
    'فولاد': [
      { stage: 'universe', status: 'pass', reason_code: 'IN_UNIVERSE', human_reason: 'در جامعۀ این نشست',
        input_count: 922, output_count: 922, source: 'api/market' },
      { stage: 'tape:f_susp', status: 'pass', reason_code: 'TAPE_PASSED', human_reason: 'حجم مشکوک — خورده شد',
        input_count: 922, output_count: 3, source: 'docs/حجم مشکوک.txt#b8a185c4168be33e',
        formula_version: 'txt-1', filter_id: 'f_susp', label: 'حجم مشکوک' },
      { stage: 'technical', status: 'pass', reason_code: 'WEEKLY_TREND_UP', human_reason: 'روند هفتگی صعودی' },
      { stage: 'fundamental', status: 'pass', reason_code: '', human_reason: '' },
      { stage: 'handover', status: 'pass', reason_code: '', human_reason: '' },
    ],
  },
  handover: [{ symbol: 'فولاد', final: 'pass', exception: false, fund_score: 5,
               tech_points: 2, backend_rank: 1, display_rank: 1 }],
};

/** جایگزینِ fetch درِ تست‌هایِ رندر: هر `/api/funnel` همین پاسخ را می‌گیرد. */
export function installFunnelApi(payload: ApiPayload = FUNNEL_FIXTURE) {
  const real = globalThis.fetch;
  globalThis.fetch = async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/funnel')) {
      return new Response(JSON.stringify(payload), {
        status: 200, headers: { 'content-type': 'application/json' },
      });
    }
    // هر چیزِ دیگر (تابلو، اسکرینر، سبد) درِ این تست‌ها خالی می‌ماند: قیف باید
    // بی‌آن‌ها هم درست نمایش دهد، پس بی‌صدا ۴۰۴ نه کرش.
    return new Response(JSON.stringify({ status: 'no_data' }), {
      status: 404, headers: { 'content-type': 'application/json' },
    });
  };
  return () => { globalThis.fetch = real; };
}
