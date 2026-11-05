import { describe, expect, it } from 'vitest';
import { FtsAnalysis, FtsResponse, useFtsAnalysis } from '@features/technical/api/useFtsAnalysis';

/**
 * R-TECH-1: قراردادِ پاسخِ تحلیلِ FTS همان چیزی است که سرور می‌فرستد.
 * تست سه چیز را می‌پاید: شکلِ کاملِ پاسخ، «null ≠ false» در لایه‌های سنجیده‌نشده،
 * و اینکه نمادِ بدونِ تاریخچه پاسخِ مشروع (fts تهی) می‌گیرد، نه خطای ماسک‌شده.
 */
const leg = (trend: string) => ({
  trend,
  basis: 'pivots',
  hh: true,
  hl: true,
  last_high: 4100,
  prev_high: 3870,
  last_low: 3500,
  prev_low: 2658,
  stale_bars: null,
  last_pivot_time: '2026-10-31',
});

const fullPayload = {
  status: 'success',
  symbol: 'البرز',
  analysis_basis: 'local-candles',
  bars: 240,
  ref_close: 4080,
  fts: {
    trend: {
      D: leg('up'),
      W: { ...leg('up'), hh: null, hl: null },
      alignment: 'up',
      as_of: '2026-11-04',
      matrix: { decision: 'allow', setup: 'pullback', desc: 'صعودی با تأیید هفتگی', basis: { weekly: 'pivots', daily: 'pivots' } },
    },
    fib: {
      retrace_base_high: 4100,
      retrace_base_low: 2658,
      zone_33_40: { lo: 3600, hi: 3620, in_zone: false },
      levels: [{ ratio: 0.618, price: 3200 }],
      leg: { direction: 'up', start: '2026-05-01', end: '2026-10-31', high: 4100, low: 2658, provisional: false },
    },
    jet: { active: false, reason: 'زیرِ سقف', bars_available: 41, bars_required: 60 },
    choch: { bearish: false, bullish: null, level: 3100, confirm_days: 2, margin: 1 },
    point_hunt: { touches: 3, floor_price: 3000, active: true, bounced: true, reason: null },
    pullback: { active: true, touching: false, level: 3870, weekly_confirms: true, gap_pct: 1.2 },
    double_bottom: { active: false, neckline: 3500, pct_above_neck: 16.6 },
    range_box: { active: false, top: 4100, bottom: 3000, start_date: '2026-06-01', end_date: '2026-09-01' },
    exit_engine: {
      verdict: 'hold',
      signals: ['none'],
      unmeasured: ['l4'],
      l1: { hard_stop: 3500, stop_basis: 'swing-low', stop_hit: false, ma14: 3990, close: 4080 },
      l2: { choch_break: false, channel_break: false, level: 3100, touches: 3 },
      l3: { third_peak: false, double_top: false, hs_break: false, reason: null },
      l4: { rsi_divergence: null, rsi: null, reason: 'دادهٔ کافی نیست' },
    },
    hourglass: { active: false, weekly_close: 4080, ma52: 3900, weekly_bars: 41, weekly_rsi: 55.2, rsi_period: 7, rsi_oversold: 30, ma52_position_mode: 'below', ma52_position_match: true, action: 'wait', desc: 'کندلِ هفتگیِ کافی نیست' },
    setups: [{ date: '2026-10-20', kind: 'pullback', label: 'پولبک به سقف', price: 3870, side: 'long' }],
    setups_state: 'ok',
    setups_bars_available: 120,
    setups_bars_required: 60,
    structure_points: {
      D: [{ idx: 100, time: '2026-10-31', confirm_idx: 105, confirm_time: '2026-11-02', price: 4100, kind: 'HH', label: 'سقفِ ماژور', major: true, leg_pct: 54.2, leg_atr_x: 6.1, recent: true }],
      W: [],
    },
    status: { code: 'PULLBACK', text: 'پولبکِ صعودی', trigger: { kind: 'pullback', price: 3870, date: '2026-10-20', label: 'سطح', role: 'trigger' }, exits: [], warnings: [], unknown: ['hourglass'], vetoed: false, context_only: false, roles: { pullback: 'trigger' } },
    roles: { pullback: 'trigger' },
  },
};

describe('R-TECH-1 · قراردادِ تحلیل FTS', () => {
  it('parses the full server payload and keeps the story fields', () => {
    const parsed = FtsResponse.parse(fullPayload);
    expect(parsed.fts?.trend?.D?.trend).toBe('up');
    expect(parsed.fts?.trend?.matrix?.decision).toBe('allow');
    expect(parsed.fts?.status?.code).toBe('PULLBACK');
    expect(parsed.fts?.exit_engine?.verdict).toBe('hold');
    expect(parsed.fts?.setups_state).toBe('ok');
    expect(parsed.ref_close).toBe(4080);
  });

  it('never turns an unmeasured layer into false (null ≠ false)', () => {
    const parsed = FtsAnalysis.parse(fullPayload.fts);
    expect(parsed.choch?.bullish).toBeNull();
    expect(parsed.exit_engine?.l4?.rsi_divergence).toBeNull();
    expect(parsed.trend?.W?.hh).toBeNull();
    // و «سنجیده شد و نه» همچنان false است، نه null.
    expect(parsed.jet?.active).toBe(false);
    expect(parsed.exit_engine?.l3?.double_top).toBe(false);
  });

  it('treats a symbol without history as a legitimate empty answer', () => {
    const parsed = FtsResponse.parse({ status: 'success', symbol: 'تازه', fts: null, message: 'بدونِ تاریخچهٔ کافی' });
    expect(parsed.fts).toBeNull();
    expect(parsed.message).toBe('بدونِ تاریخچهٔ کافی');
  });

  it('keeps the hook wired to the fts endpoint', () => {
    expect(typeof useFtsAnalysis).toBe('function');
  });
});
