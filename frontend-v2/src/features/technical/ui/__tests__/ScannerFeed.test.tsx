/**
 * frontend-v2/src/features/technical/ui/__tests__/ScannerFeed.test.tsx
 *
 * آزمون‌های فیدِ واحدِ اسکنر (ادغام تب «الگوها» در «اسکنر الگوها»):
 * - فهرست الگوها با فیلتر خانواده و فوکوس روی چارت
 * - برچسب ردهٔ ۲ («کم‌بسامد») در فهرست
 * - ردیف‌های پولبک/CHoCH با testidهای پایدار
 * - کتاب قواعد از PATTERN_CONFIG
 * - بدونِ کارت رویداد فعال؛ کارت در ریل بازرس می‌نشیند (B3)
 *
 * آزمون‌های کارت به ActiveEventCard.test.tsx منتقل شده‌اند.
 */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { ScannerFeed } from '../ScannerFeed';
import { useTechnicalStore } from '../../model/technicalStore';
import type { ChartPattern } from '../../model/patterns/types';
import type { CHoCHSignal, FormationEstimate, PullbackSignal } from '../../model/types';

const point = (index: number, price = 100) => ({ index, price, timestamp: index * 60_000 });

// `formation` می‌تواند null هم باشد (یعنی تخمینی نیست)؛ بقیهٔ فیلدها همان ChartPattern هستند.
type PatternOverrides = Partial<Omit<ChartPattern, 'formation'>> & {
  formation?: FormationEstimate | null;
};

const base = (over: PatternOverrides = {}): ChartPattern => ({
  id: 'p1', kind: 'FLAG_BULL', direction: 'bullish', family: 'continuation', tier: 1,
  anchor: point(40, 105), points: [], upper: { from: point(30, 106), to: point(40, 106) },
  lower: { from: point(30, 104), to: point(40, 104) },
  target: 112, stopLoss: 98, quality: 60, status: 'forming', ...over,
  formation: over.formation ?? undefined,
});

const flag = () => base({ id: 'FLAG_BULL:1' });
const diamond = (over: PatternOverrides = {}) => base({
  id: 'DIAMOND_TOP:1', kind: 'DIAMOND_TOP', direction: 'bearish', family: 'reversal', tier: 2,
  anchor: point(50, 105), ...over,
});

const pullback = (): PullbackSignal => ({
  id: 'pullback-1', type: 'BULLISH', index: 42, timestamp: 42 * 60_000, price: 101,
  superTrendPrice: 99, qualityScore: 77,
});

const choch = (): CHoCHSignal => ({
  id: 'choch-1', type: 'CHoCH', isBullish: false, index: 44, timestamp: 44 * 60_000,
  levelPrice: 100, brokenPrice: 98,
});

const renderFeed = (
  patterns: ChartPattern[],
  pullbacks: PullbackSignal[] = [],
  chochs: CHoCHSignal[] = [],
) => render(<ScannerFeed patterns={patterns} pullbacks={pullbacks} chochs={chochs} />);

afterEach(cleanup);
beforeEach(() => {
  useTechnicalStore.setState({ focusPatternId: null });
});

describe('ScannerFeed', () => {
  it('renders patterns and existing scanner events in one feed', () => {
    render(<ScannerFeed patterns={[flag()]} pullbacks={[pullback()]} chochs={[choch()]} />);
    expect(screen.getByTestId('pattern-row-FLAG_BULL:1')).toBeTruthy();
    expect(screen.getByTestId('scanner-event-pullback-1')).toBeTruthy();
    expect(screen.getByTestId('scanner-event-choch-1')).toBeTruthy();
  });

  it('badges tier-2 patterns in the list and leaves the active card to the rail', () => {
    render(<ScannerFeed patterns={[diamond({ formation: null }), flag()]} pullbacks={[]} chochs={[]} />);
    expect(screen.getByTestId('pattern-row-DIAMOND_TOP:1').textContent).toContain('کم‌بسامد');
    // testidهای کارت فقط در ریل بازرس وجود دارند.
    expect(screen.queryByTestId('pattern-tier-2')).toBeNull();
    expect(screen.queryByTestId('pattern-card')).toBeNull();
  });

  it('renders no active event card even when a formation estimate exists', () => {
    renderFeed([base({
      formation: {
        probability: 0.62, successes: 14, failures: 9, resolved: 23,
        confidence: 'medium', horizon: 10, method: 'same-symbol',
      },
    })]);
    expect(screen.queryByTestId('pattern-card')).toBeNull();
    expect(screen.queryByTestId('pattern-quality')).toBeNull();
    // درصد در ردیف فهرست می‌ماند؛ فقط کارت منتقل شده است.
    expect(screen.getByTestId('pattern-row-p1').textContent).toContain('۶۲٪');
  });

  it('lists recent patterns with stable row testids and filters by family', () => {
    renderFeed([
      base({ id: 'a' }),
      base({ id: 'b', kind: 'HEAD_SHOULDERS', family: 'reversal', direction: 'bearish', status: 'confirmed' }),
    ]);
    expect(screen.getByTestId('pattern-row-a')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('فیلتر خانواده'), { target: { value: 'reversal' } });
    expect(screen.queryByTestId('pattern-row-a')).toBeNull();
    expect(screen.getByTestId('pattern-row-b')).toBeTruthy();
  });

  it('labels pullback and CHoCH rows with kind, direction and bar index', () => {
    renderFeed([], [pullback()], [choch()]);
    const pb = screen.getByTestId('scanner-event-pullback-1');
    expect(pb.textContent).toContain('پولبک');
    expect(pb.textContent).toContain('صعودی');
    expect(pb.textContent).toContain('کندل ۴۲');
    const ch = screen.getByTestId('scanner-event-choch-1');
    expect(ch.textContent).toContain('CHoCH');
    expect(ch.textContent).toContain('نزولی');
    expect(ch.textContent).toContain('کندل ۴۴');
  });

  it('renders the rule book from PATTERN_CONFIG', () => {
    renderFeed([]);
    const rules = screen.getByTestId('pattern-rules');
    expect(rules.textContent).toContain('۳');
    expect(rules.textContent).toContain('۳۵');
    expect(rules.textContent).toContain('۸');
  });

  it('renders every config key added after the brief in the rule book', () => {
    renderFeed([]);
    const rules = screen.getByTestId('pattern-rules').textContent ?? '';
    // touchToleranceAtr
    expect(rules).toContain('تحمل لمس ۰٫۵×ATR');
    // flag.minLegBars
    expect(rules).toContain('حداقل لگ ۳ کندل');
    // triangle.minSpan
    expect(rules).toContain('حداقل طول ۳ کندل');
    // expiryGraceBars
    expect(rules).toContain('مهلت تمدید ۱ کندل');
    // expiryMinPoints
    expect(rules).toContain('حداقل نقاط تمدید ۵');
    // reversal.minSpanBars
    expect(rules).toContain('حداقل طول بازگشتی ۶ کندل');
    // neutralMinTargetAtr
    expect(rules).toContain('حداقل هدف خنثی ۰٫۵×ATR');
    // returnsMinSamples
    expect(rules).toContain('حداقل نمونهٔ بازده ۵');
    // overlapWindowBars
    expect(rules).toContain('پنجرهٔ هم‌پوشانی ۳ کندل');
  });

  it('renders the convergence, tolerance, pivot, ATR and per-family window keys', () => {
    renderFeed([]);
    const rules = screen.getByTestId('pattern-rules').textContent ?? '';
    // pennant.convergenceMin
    expect(rules).toContain('پنانت: لگ ≥ ۳×ATR · همگرایی ≥ ۳۵٪');
    // wedge.convergenceMin
    expect(rules).toContain('گُوه: همگرایی ≥ ۳۰٪');
    // minTouchesPerLine
    expect(rules).toContain('حداقل لمس هر خط ۲');
    // hs.headAboveShouldersAtr / hs.shouldersToleranceAtr
    expect(rules).toContain('سر و شانه: سر ≥ ۰٫۵×ATR بالاتر · شانه‌ها ±۰٫۶×ATR');
    // triple.levelToleranceAtr
    expect(rules).toContain('سه‌قلو: تحمل سطح ۰٫۵×ATR');
    // pivLeft / pivRight
    expect(rules).toContain('پیوت ۵ چپ / ۴ راست');
    // atrPeriod
    expect(rules).toContain('دورهٔ ATR ۱۴');
    // maxBars هر خانواده
    expect(rules).toContain('پرچم ۴۰');
    expect(rules).toContain('پنانت ۳۰');
    expect(rules).toContain('مثلث ۶۰');
    expect(rules).toContain('مستطیل ۸۰');
    expect(rules).toContain('گُوه ۶۰');
    expect(rules).toContain('سر و شانه ۱۲۰');
    expect(rules).toContain('سه‌قلو ۱۲۰');
  });

  it('sets the focused pattern id when a row is clicked (spec §7.3)', () => {
    renderFeed([base({ id: 'focus-me' })]);
    fireEvent.click(screen.getByTestId('pattern-row-focus-me'));
    expect(useTechnicalStore.getState().focusPatternId).toBe('focus-me');
  });

  it('renders no raw enum names for the new kinds', () => {
    const kinds = ['CUP_HANDLE', 'DIAMOND_TOP', 'THREE_FALLING_PEAKS', 'ROUNDING_BOTTOM', 'BROADENING_TOP'];
    renderFeed(kinds.map((kind, i) => base({ id: kind, kind: kind as never, anchor: point(60 + i) })));
    const text = screen.getByTestId('pattern-list').textContent ?? '';
    expect(text).not.toMatch(/[A-Z_]{4,}/);
    expect(text).toContain('کاپ‌هندل');
    expect(text).toContain('دیاموند سقف');
  });

  it('caps the scanner event list at 20 and shows the newest first', () => {
    const pullbacks = Array.from({ length: 25 }, (_, i) => ({
      ...pullback(), id: 'pb-' + i, index: 10 + i, timestamp: (10 + i) * 60_000,
    }));
    renderFeed([], pullbacks, []);
    const rows = screen.getAllByTestId(/^scanner-event-/);
    expect(rows.length).toBe(20);
    expect(rows[0]!.getAttribute('data-testid')).toBe('scanner-event-pb-24');
  });

});
