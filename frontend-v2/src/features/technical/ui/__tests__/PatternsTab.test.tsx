import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { PatternsTab } from '../PatternsTab';
import { useTechnicalStore } from '../../model/technicalStore';
import type { ChartPattern } from '../../model/patterns/types';

const point = (index: number, price: number) => ({ index, price, timestamp: index * 60_000 });
const base = (over: Partial<ChartPattern>): ChartPattern => ({
  id: 'p1', kind: 'FLAG_BULL', direction: 'bullish', family: 'continuation',
  anchor: point(40, 105), points: [], upper: { from: point(30, 106), to: point(40, 106) },
  lower: { from: point(30, 104), to: point(40, 104) },
  target: 112, stopLoss: 98, quality: 60, status: 'forming', ...over,
});

afterEach(cleanup);
beforeEach(() => {
  useTechnicalStore.setState({ focusPatternId: null });
});

describe('PatternsTab', () => {
  it('shows the percentage only when a formation estimate exists', () => {
    render(<PatternsTab patterns={[base({
      formation: {
        probability: 0.62, successes: 14, failures: 9, resolved: 23,
        confidence: 'medium', horizon: 10, method: 'same-symbol',
        intervalLow: 0.48, intervalHigh: 0.73,
      },
      returns: { h1: 1.2, h3: 2.1, h5: null },
    })]} />);
    const card = screen.getByTestId('pattern-card');
    // R-PAT-24: احتمال ۰..۱ است؛ کارت باید آن را در ۱۰۰ ضرب و «۶۲٪» نشان دهد.
    expect(card.textContent).toContain('۶۲٪');
    // سرصفحه و بازهٔ ویلسون باید یک واحد داشته باشند: ۰٫۴۸–۰٫۷۳ → «۴۸٪–۷۳٪».
    expect(card.textContent).toContain('۴۸٪–۷۳٪');
    expect(card.textContent).toContain('۲۳');
    expect(card.textContent).toContain('کندلِ در حال تشکیل');
  });

  it('renders a 0.5 rate as ۵۰٪, not as ۱٪', () => {
    render(<PatternsTab patterns={[base({
      formation: { probability: 0.5, successes: 5, failures: 4, resolved: 9, confidence: 'medium', horizon: 10, method: 'same-symbol' },
    })]} />);
    const card = screen.getByTestId('pattern-card');
    expect(card.textContent).toContain('۵۰٪');
    expect(card.textContent).not.toContain('۱٪');
  });

  it('shows the Persian direction next to the kind', () => {
    render(<PatternsTab patterns={[base({ direction: 'neutral' })]} />);
    expect(screen.getByTestId('pattern-card').textContent).toContain('خنثی');
  });

  it('says the sample is not enough instead of showing a number', () => {
    render(<PatternsTab patterns={[base({
      formation: { probability: null, successes: 2, failures: 1, resolved: 3, confidence: 'none', horizon: 10, method: 'same-symbol' },
    })]} />);
    expect(screen.getByTestId('pattern-card').textContent).toContain('نمونهٔ کافی نیست');
    expect(screen.getByTestId('pattern-card').textContent).not.toMatch(/تشکیل\s*[۰-۹]+٪/);
  });

  it('lists recent patterns with stable row testids and filters by family', () => {
    render(<PatternsTab patterns={[
      base({ id: 'a' }),
      base({ id: 'b', kind: 'HEAD_SHOULDERS', family: 'reversal', direction: 'bearish', status: 'confirmed' }),
    ]} />);
    expect(screen.getByTestId('pattern-row-a')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('فیلتر خانواده'), { target: { value: 'reversal' } });
    expect(screen.queryByTestId('pattern-row-a')).toBeNull();
    expect(screen.getByTestId('pattern-row-b')).toBeTruthy();
  });

  it('renders the rule book from PATTERN_CONFIG', () => {
    render(<PatternsTab patterns={[]} />);
    const rules = screen.getByTestId('pattern-rules');
    expect(rules.textContent).toContain('۳');
    expect(rules.textContent).toContain('۳۵');
    expect(rules.textContent).toContain('۸');
  });

  it('renders every config key added after the brief in the rule book', () => {
    render(<PatternsTab patterns={[]} />);
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
    render(<PatternsTab patterns={[]} />);
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
    render(<PatternsTab patterns={[base({ id: 'focus-me' })]} />);
    fireEvent.click(screen.getByTestId('pattern-row-focus-me'));
    expect(useTechnicalStore.getState().focusPatternId).toBe('focus-me');
  });
});
