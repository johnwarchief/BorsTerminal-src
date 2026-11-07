// __tests__/fixtures/funnelTechFirst.ts — پاسخِ «تکنیکال‌محور» برایِ تستِ رندر
//
// چرا جدا از FUNNEL_FIXTURE: آن فیکسچر ترتیبِ جزوه را دارد و سنجش‌هایِ پیشین
// رویِ همان ساخته شده‌اند. اینجا همان چهار گام با ترتیبِ عوض‌شده است و هدف،
// ثابت‌کردنِ سه چیز است: (۱) جدولِ تکنیکال اول می‌آید، (۲) هر شرط نتیجه و
// دلیلِ خودش را درِ ردیف دارد، (۳) نبودِ داده «رد» خوانده نمی‌شود.
//
// پنج سرنوشتِ عمدی:
//   فولاد   گیت قبول + ستاپ جت قبول ⇒ عبور؛ بعد تابلو رویِ ماندگان اجرا می‌شود.
//   همراه   گیت رد (هفتگی نزولی) با ستاپ جتِ قبول ⇒ رد. اگر رابط جت را «عبور»
//           بخواند و نه وتوی هفتگی، گیتِ اجباری را دور زده است.
//   خودرو   ریسکِ «سقفِ سوم» ثبت‌شده ⇒ ردِ نقش‌محور: شاهدِ فعال رد می‌کند.
//   شپنا    اسکن داوری نکرده ⇒ «بی‌داده»، نه رد.
//   آبادا   خارج از جامعۀ غربالگری (تعلیق).
//
// اعدادِ وضعیت و دلیل را خودِ این فایل نوشته است؛ فرانت باید عیناً همان را
// نشان دهد. تاریخِ داوری از `scan_as_of` می‌آید و برایِ «شپنا» تهی است ⇒ «—».
import type { ApiPayload } from '@features/master/lib/funnelView';
import { row } from './funnelApi';

const chk = (
  filterId: string, label: string, role: string, column: string,
  status: 'pass' | 'reject' | 'pending' | 'unavailable', value: string | number | null,
  reason: string, source: string,
) => ({
  filter_id: filterId, label, role, column, status, value, source,
  reason_code: `${filterId.toUpperCase()}_${status.toUpperCase()}`,
  human_reason: reason, origin: 'chart',
});

const GATE = 'روندِ هفتگی صعودی';
const JET = 'ستاپ جت';
const FIB = 'ناحیۀ فیبوناتچی ۳۳-۴۰';
const PEAK = 'شاهدِ سقفِ سوم';

export const TECH_FIRST_FIXTURE: ApiPayload = {
  status: 'success',
  engine_version: '1',
  ruleset_version: 'techfirst000001',
  as_of: Math.floor(Date.now() / 1000),
  preset: 'tech_first',
  flow: 'tech_first',
  chain: [],
  technical_chain: ['t_weekly_up', 't_setup_jet', 't_setup_fib_33_40'],
  strategy_settings: { weekly_mode: 'off', daily_mode: 'off',
                       clock_delta_pct: '1' },
  fund_mode: 'standard',
  universe: {
    board: 5, screened: 4, joined: 5, duplicate_rows: 0,
    market: 5, screening: 4, excluded: 1,
    exclusion_counts: { STOPPED: 1 },
    exclusion_labels: { STOPPED: 'متوقف' },
  },
  stages: {
    // گامِ اول: ورودی‌اش کلِ جامعۀ غربالگری است. تابلو بعد می‌آید و ورودی‌اش
    // فقط ماندگانِ تکنیکال (یک نماد) — همان چیزی که درِ UI باید خوانده شود.
    technical: {
      input: 4, matched: 1,
      counts: { pass: 1, reject: 2, pending: 0, unavailable: 1, not_required: 0 },
      chain: ['t_weekly_up', 't_setup_jet', 't_setup_fib_33_40'],
      filter_counts: {
        t_weekly_up: { pass: 2, reject: 1, pending: 0, unavailable: 1 },
        t_setup_jet: { pass: 2, reject: 1, pending: 0, unavailable: 1 },
        t_setup_fib_33_40: { pass: 1, reject: 2, pending: 0, unavailable: 1 },
      },
    },
    tape: { input: 1, matched: 1, removed: 0, steps: [], filter_counts: {} },
    fundamental: {
      input: 1, matched: 1, mode: 'standard',
      counts: { pass: 1, reject: 0, pending: 0, unavailable: 0, not_required: 3 },
    },
    handover: {
      input: 1, matched: 1,
      counts: { pass: 1, reject: 0, pending: 0, unavailable: 0, not_required: 3 },
    },
  },
  entries: {
    technical: [
      row('فولاد', 'فولاد مبارکه اصفهان', {
        status: { technical: 'pass' }, weekly: 'up', daily: 'up',
        branch: 'جت / پولبک', matrix: 'PERMITTED', tech_points: 3, evidence: ['jet'],
        scan_as_of: 1_760_000_000,
        checks: [
          chk('t_weekly_up', GATE, 'gate', 'tech_trend_w', 'pass', 'up',
              'روند هفتگی صعودی', 'docs/چارت-سه.txt:34'),
          chk('t_setup_jet', JET, 'entry', 'tech_jet', 'pass', 1,
              'ستاپ جت: خورده شد', 'docs/چارت-سه.txt:36'),
          // کمربندِ ۳۳-۴۰ با شاهدِ عددی: عمقِ اصلاح و نقاطِ موج (رأیِ مالک)
          { ...chk('t_setup_fib_33_40', FIB, 'entry', 'tech_fib_zone', 'pass', '33-40',
                   'اصلاحِ ۳۵٫۲٪ داخلِ کمربندِ ۳۳-۴۰٪', 'docs/چارت-سه.txt:38'),
            measure: { band_lo: 33, band_hi: 40, retrace_pct: 35.2, where: 'inside',
                       distance_pct: 0,
                       leg: { direction: 'up', from: '2026-06-21', to: '2026-10-17',
                              low: 16080, high: 18928 } } },
        ],
        why: { technical: [{ code: 'WEEKLY_TREND_UP', text: 'روند هفتگی صعودی' }] },
      }),
      row('همراه', 'همراه اول', {
        status: { technical: 'reject' }, weekly: 'down', daily: 'up', matrix: 'REJECT',
        scan_as_of: 1_760_000_000,
        checks: [
          chk('t_weekly_up', GATE, 'gate', 'tech_trend_w', 'reject', 'down',
              'وتوی رسمیِ روند هفتگی', 'docs/چارت-سه.txt:34'),
          chk('t_setup_jet', JET, 'entry', 'tech_jet', 'pass', 1,
              'ستاپ جت: خورده شد', 'docs/چارت-سه.txt:36'),
        ],
        why: { technical: [{ code: 'WEEKLY_TREND_DOWN', text: 'روند هفتگی نزولی — وتوی قطعی' }] },
      }),
      row('خودرو', 'سازمان توسعه‌ای خودروسازی', {
        status: { technical: 'reject' }, weekly: 'up', daily: 'up', matrix: 'PERMITTED',
        scan_as_of: 1_760_000_100,
        checks: [
          chk('t_weekly_up', GATE, 'gate', 'tech_trend_w', 'pass', 'up',
              'روند هفتگی صعودی', 'docs/چارت-سه.txt:34'),
          chk('t_risk_third_peak', PEAK, 'risk', 'tech_exit_signals', 'reject',
              'third_peak,rsi_divergence',
              '«شاهدِ سقفِ سوم» رویِ این نماد ثبت شده — با انتخابِ شما رد می‌شود',
              'docs/چارت-سه.txt:45'),
        ],
        why: {
          technical: [{
            code: 'TECH_RISK_THIRD_PEAK',
            text: '«شاهدِ سقفِ سوم» رویِ این نماد ثبت شده — با انتخابِ شما رد می‌شود',
          }],
        },
      }),
      row('شپنا', 'پالایش نفت شپنا', {
        status: { technical: 'unavailable' }, weekly: null, daily: null, matrix: null,
        scan_as_of: null,
        checks: [
          chk('t_weekly_up', GATE, 'gate', 'tech_trend_w', 'unavailable', null,
              'تکنیکال این نماد سنجیده نشده', 'docs/چارت-سه.txt:34'),
          chk('t_setup_jet', JET, 'entry', 'tech_jet', 'unavailable', null,
              'ستاپ جت — ستونِ tech_jet مقدارِ داوری‌شده ندارد', 'docs/چارت-سه.txt:36'),
        ],
        why: {
          technical: [{ code: 'TECH_NO_HISTORY', text: 'هیچ سابقۀ قیمتی در بانکِ محلی برایِ این نماد نیست' }],
        },
      }),
    ],
    tape: [row('فولاد', 'فولاد مبارکه اصفهان',
               { status: { tape: 'pass' }, patterns: ['مشکوک'] })],
    fundamental: [row('فولاد', 'فولاد مبارکه اصفهان', {
      status: { fundamental: 'pass' }, score: 5,
      inds: { i1: true, i2: true, i3: true, i4: true, i5: true },
    })],
    handover: [row('فولاد', 'فولاد مبارکه اصفهان', { status: { handover: 'pass' }, score: 5 })],
  },
  status_matrix: {
    'فولاد': {
      technical: { status: 'pass', reason_code: 'WEEKLY_TREND_UP', human_reason: 'روند هفتگی صعودی' },
      tape: { status: 'pass', reason_code: 'TAPE_PASSED', human_reason: 'خورده شده: حجم مشکوک' },
      fundamental: { status: 'pass', reason_code: 'FUND_PASSED', human_reason: 'سه بلاکر تأیید است' },
      handover: { status: 'pass', reason_code: 'FINAL_PASS', human_reason: 'قبول در هر چهار در' },
    },
    'همراه': {
      technical: { status: 'reject', reason_code: 'WEEKLY_TREND_DOWN', human_reason: 'روند هفتگی نزولی' },
      tape: {
        status: 'not_required', reason_code: 'NOT_REQUIRED_AFTER_TECHNICAL_REJECT',
        human_reason: 'تکنیکال نماد را رد کرده؛ تابلوخوانی اجرا نمی‌شود',
      },
      fundamental: { status: 'not_required', reason_code: 'NOT_REQUIRED_AFTER_TECHNICAL_REJECT',
                     human_reason: 'تکنیکال رد کرده' },
      handover: { status: 'not_required', reason_code: 'NOT_REQUIRED_AFTER_TECHNICAL_STOP',
                  human_reason: 'گامِ پیشین ایستاده است' },
    },
    'خودرو': {
      technical: { status: 'reject', reason_code: 'TECH_RISK_THIRD_PEAK',
                   human_reason: '«شاهدِ سقفِ سوم» ثبت شده — با انتخابِ شما رد می‌شود' },
      tape: { status: 'not_required', reason_code: 'NOT_REQUIRED_AFTER_TECHNICAL_REJECT',
              human_reason: 'تکنیکال نماد را رد کرده' },
      fundamental: { status: 'not_required', reason_code: 'NOT_REQUIRED_AFTER_TECHNICAL_REJECT',
                     human_reason: 'تکنیکال رد کرده' },
      handover: { status: 'not_required', reason_code: 'NOT_REQUIRED_AFTER_TECHNICAL_STOP',
                  human_reason: 'گامِ پیشین ایستاده است' },
    },
    'شپنا': {
      technical: { status: 'unavailable', reason_code: 'TECH_NO_HISTORY',
                   human_reason: 'هیچ سابقۀ قیمتی در بانکِ محلی نیست' },
      tape: { status: 'not_required', reason_code: 'NOT_REQUIRED_AFTER_TECHNICAL_STOP',
              human_reason: 'حکمِ قطعیِ تکنیکال ساخته نشد؛ تابلو اجرا نمی‌شود' },
      fundamental: { status: 'not_required', reason_code: 'NOT_REQUIRED_AFTER_TECHNICAL_STOP',
                     human_reason: 'تکنیکال حکم نداد' },
      handover: { status: 'not_required', reason_code: 'NOT_REQUIRED_AFTER_TECHNICAL_STOP',
                  human_reason: 'تکنیکال حکم نداد' },
    },
    'آبادا': {
      technical: { status: 'not_in_universe', reason_code: 'STOPPED', human_reason: 'متوقف' },
      tape: { status: 'not_in_universe', reason_code: 'STOPPED', human_reason: 'متوقف' },
      fundamental: { status: 'not_in_universe', reason_code: 'STOPPED', human_reason: 'متوقف' },
      handover: { status: 'not_in_universe', reason_code: 'STOPPED', human_reason: 'متوقف' },
    },
  },
  exclusions: [
    { symbol: 'آبادا', name: 'توليد نيروي برق آبادان', sector: 'برق', last: 11450,
      reason_code: 'STOPPED', human_reason: 'متوقف: مشمول فرایند تعلیق',
      st_code: null, st_title: null, stop_state: 'مشمول فرایند تعلیق', is_live: true },
  ],
  timeline: {},
  coverage: {
    technical: { pass: 1, reject: 2, pending: 0, unavailable: 1, not_required: 0, not_in_universe: 1 },
    tape: { pass: 1, reject: 0, pending: 0, unavailable: 0, not_required: 3, not_in_universe: 1 },
    fundamental: { pass: 1, reject: 0, pending: 0, unavailable: 0, not_required: 3, not_in_universe: 1 },
    handover: { pass: 1, reject: 0, pending: 0, unavailable: 0, not_required: 3, not_in_universe: 1 },
  },
  tech_scan: { pending_symbols: 0, running: false, queued: 0, done: 4, failed: 0 },
  handover: [{ symbol: 'فولاد', final: 'pass', exception: false, fund_score: 5,
               tech_points: 3, backend_rank: 1, display_rank: 1 }],
};
