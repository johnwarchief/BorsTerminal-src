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
  universe: { board: 4, screened: 3, joined: 4, duplicate_rows: 0 },
  stages: {
    tape: {
      input: 4, matched: 3, removed: 1,
      steps: [
        { stage: 'tape', seq: 1, filter_id: 'f_susp', label: 'حجم مشکوک', input_count: 4,
          matched_count: 3, removed_count: 1, unmeasured_count: 0,
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
    technical: { matched: 2, counts: { pass: 2, reject: 1, pending: 0, unavailable: 0, not_required: 1 } },
    fundamental: { matched: 1, mode: 'standard',
                   counts: { pass: 1, reject: 0, pending: 1, unavailable: 0, not_required: 2 } },
    handover: { matched: 1, counts: { pass: 1, reject: 2, pending: 1, unavailable: 0, not_required: 0 } },
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
  /** وضعیتِ هر چهار گام برایِ هر چهار نماد — همان چیزی که بک‌اند از
   *  `status_matrix` می‌دهد. چهار نمادِ این فیکسچر چهار سرنوشتِ متفاوت‌اند:
   *  عبورِ کامل، ردِ تکنیکال، ردِ تابلو، و بنیادیِ در انتظار. */
  status_matrix: {
    'فولاد': {
      tape: { status: 'pass', reason_code: 'TAPE_PASSED', human_reason: 'همۀ فیلترهایِ زنجیره را خورده شده' },
      technical: { status: 'pass', reason_code: 'WEEKLY_TREND_UP', human_reason: 'روند هفتگی صعودی' },
      fundamental: { status: 'pass', reason_code: 'FUND_PASSED', human_reason: 'سه بلاکر تأیید است' },
      handover: { status: 'pass', reason_code: 'FINAL_PASS', human_reason: 'قبول در هر چهار در', display_rank: 1 },
    },
    'همراه': {
      tape: { status: 'pass', reason_code: 'TAPE_PASSED', human_reason: 'همۀ فیلترهایِ زنجیره را خورده شده' },
      technical: { status: 'reject', reason_code: 'WEEKLY_TREND_DOWN', human_reason: 'روند هفتگی نزولی — وتوی قطعی' },
      fundamental: { status: 'not_required', reason_code: 'NOT_REQUIRED_AFTER_TECHNICAL_STOP',
                     human_reason: 'تکنیکال نماد را رد کرده؛ بنیادی اجرا نمی‌شود' },
      handover: { status: 'reject', reason_code: 'NOT_ELIGIBLE_AFTER_PRIOR_REJECT',
                  human_reason: 'در گامِ پیشین رد شده' },
    },
    'سپ': {
      tape: { status: 'reject', reason_code: 'TAPE_F_SUSP_NO_MATCH',
              human_reason: 'حجم مشکوک — نشانه در این نماد نیست' },
      technical: { status: 'not_required', reason_code: 'NOT_REQUIRED_AFTER_TAPE_REJECT',
                   human_reason: 'تابلو نماد را رد کرده؛ تکنیکال اجرا نمی‌شود' },
      fundamental: { status: 'not_required', reason_code: 'NOT_REQUIRED_AFTER_TAPE_REJECT',
                     human_reason: 'تابلو نماد را رد کرده؛ بنیادی اجرا نمی‌شود' },
      handover: { status: 'reject', reason_code: 'NOT_ELIGIBLE_AFTER_PRIOR_REJECT',
                  human_reason: 'در گامِ پیشین رد شده' },
    },
    'شپنا': {
      tape: { status: 'pass', reason_code: 'TAPE_PASSED', human_reason: 'همۀ فیلترهایِ زنجیره را خورده شده' },
      technical: { status: 'pass', reason_code: 'WEEKLY_TREND_UP', human_reason: 'روند هفتگی صعودی' },
      fundamental: { status: 'pending', reason_code: 'FUND_I1_MISSING',
                     human_reason: 'I1 رشد فروش گزارشش نرسیده — رد نیست، سنجیده نشده' },
      handover: { status: 'pending', reason_code: 'WAITING_FOR_DATA', human_reason: 'در انتظارِ داده/گزارش' },
    },
  },
  coverage: {
    tape: { pass: 3, reject: 1, pending: 0, unavailable: 0, not_required: 0 },
    technical: { pass: 2, reject: 1, pending: 0, unavailable: 0, not_required: 1 },
    fundamental: { pass: 1, reject: 0, pending: 1, unavailable: 0, not_required: 2 },
    handover: { pass: 1, reject: 2, pending: 1, unavailable: 0, not_required: 0 },
  },
  // اسکنِ تکنیکال درِ پس‌زمینه است؛ پاسخِ همین لحظه می‌گوید چند نماد هنوز
  // داوریِ ساخته‌شد ندارند (باید درِ UI دیده شود، نه اینکه غیب باشد).
  tech_scan: { pending_symbols: 2, running: true, queued: 2, done: 18, failed: 0 },
  handover: [{ symbol: 'فولاد', final: 'pass', exception: false, fund_score: 5,
               tech_points: 2, backend_rank: 1, display_rank: 1 }],
};

/** رجیستریِ دستی — همان هفت فیلترِ `funnel_registry.py`، با دستِ خودِ این فایل.
 *  تستِ Custom باید ثابت کند چیپ‌ها از *رجیستری* می‌آیند، نه از arrayِ پنج‌تاییِ
 *  پیشین؛ پس «پول هوشمند» و «کد به کد» هم درِ این فهرست می‌آیند. */
export const REGISTRY_FIXTURE = {
  registry_version: '7',
  ruleset_version: 'deadbeefcafe',
  filters: [
    { filter_id: 'f_clock', name: 'الگوی ساعت', description: 'دو ساعتِ اولِ پرحجم',
      source_file: 'docs/الگوی ساعت.txt', source_hash: '6637192e4d10a73d',
      formula_version: 'txt-1', backend_impl: 'tape_flags.clock_flag',
      availability: 'backend', status: 'canonical', params: [{ param_id: 'start', label: 'شروع', value: 1 }] },
    { filter_id: 'f_susp', name: 'حجم مشکوک', description: 'سه برابرِ میانگینِ سی نشست',
      source_file: 'docs/حجم مشکوک.txt', source_hash: 'b8a185c4168be33e',
      formula_version: 'txt-1', backend_impl: 'tape_flags.suspicious_flag',
      availability: 'backend', status: 'canonical',
      params: [{ param_id: 'vol_mult', label: 'ضریبِ حجم', value: 3 },
               { param_id: 'min_trades', label: 'حداقلِ معامله', value: 50 }] },
    { filter_id: 'f_jet', name: 'جت', description: 'بسته‌شدنِ شکافِ قیمتی',
      source_file: 'docs/جت.txt', source_hash: 'e93cab46073567c0',
      formula_version: 'txt-1', backend_impl: 'tape_flags.jet_flag',
      availability: 'backend', status: 'canonical', params: [] },
    { filter_id: 'f_roobi', name: 'کف‌روبی', description: 'کف‌روبیِ خریدار',
      source_file: 'docs/کفروبی.txt', source_hash: '053a12a7c96b6e4f',
      formula_version: 'txt-1', backend_impl: 'tape_flags.roobi_flag',
      availability: 'backend', status: 'canonical', params: [] },
    { filter_id: 'f_noqteh', name: 'نقطه زنی', description: 'تک‌معامله‌هایِ نقطه‌ای',
      source_file: 'docs/نقطه زنی.txt', source_hash: 'e5d4fd99a6811443',
      formula_version: 'txt-1', backend_impl: 'tape_flags.noqteh_flag',
      availability: 'backend', status: 'canonical', params: [] },
    { filter_id: 'f_smart', name: 'ورود پول هوشمند', description: 'تغییرِ مالکیتِ محسوس',
      source_file: 'docs/پول هوشمند.txt', source_hash: '590e52a23c78166f',
      formula_version: 'txt-1', backend_impl: 'tape_flags.smart_money_flag',
      availability: 'backend', status: 'canonical', params: [] },
    { filter_id: 'f_legal', name: 'کد به کد', description: 'انتقالِ کدِ حقیقی به حقوقی',
      source_file: 'docs/کد به کد.txt', source_hash: '92adf93e9d5e1df4',
      formula_version: 'txt-1', backend_impl: 'tape_flags.legal_transfer_flag',
      availability: 'backend', status: 'canonical', params: [] },
  ],
  presets: [],
  unimplemented_filters: [],
  gates: {},
};

/** جایگزینِ fetch درِ تست‌هایِ رندر: هر `/api/funnel` همین پاسخ را می‌گیرد. */
export function installFunnelApi(payload: ApiPayload = FUNNEL_FIXTURE) {
  const real = globalThis.fetch;
  globalThis.fetch = async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/funnel/registry')) {
      return new Response(JSON.stringify(REGISTRY_FIXTURE), {
        status: 200, headers: { 'content-type': 'application/json' },
      });
    }
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
