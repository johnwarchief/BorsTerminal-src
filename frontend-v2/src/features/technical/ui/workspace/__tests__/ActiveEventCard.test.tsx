/**
 * frontend-v2/src/features/technical/ui/workspace/__tests__/ActiveEventCard.test.tsx
 *
 * آزمون‌های کارت رویداد فعالِ ریل (منتقل‌شده از ScannerFeed.test.tsx، بدون تغییر رفتار):
 * - دروازهٔ درصد: هیچ عددی زیر آستانهٔ نمونهٔ حل‌شده دیده نمی‌شود (R-PAT-24/R-PA-17)
 * - سرصفحه و بازهٔ ویلسون یک واحد دارند؛ نمونه، کیفیت هندسی، سطوح و بازده‌ها
 * - برچسب ردهٔ ۲ («کم‌بسامد») و جهت فارسی
 * - حالت خالی وقتی الگویی در حال تشکیل نیست
 */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { ActiveEventCard } from '../ActiveEventCard';
import type { ChartPattern } from '../../../model/patterns/types';
import type { FormationEstimate } from '../../../model/types';

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

afterEach(cleanup);

describe('ActiveEventCard', () => {
  it('shows the percentage only when a formation estimate exists', () => {
    render(<ActiveEventCard pattern={base({
      formation: {
        probability: 0.62, successes: 14, failures: 9, resolved: 23,
        confidence: 'medium', horizon: 10, method: 'same-symbol',
        intervalLow: 0.48, intervalHigh: 0.73,
      },
      returns: { h1: 1.2, h3: 2.1, h5: null },
    })} />);
    const card = screen.getByTestId('pattern-card');
    // R-PAT-24: احتمال ۰..۱ است؛ کارت باید آن را در ۱۰۰ ضرب و «۶۲٪» نشان دهد.
    expect(card.textContent).toContain('۶۲٪');
    // سرصفحه و بازهٔ ویلسون باید یک واحد داشته باشند: ۰٫۴۸–۰٫۷۳ → «۴۸٪–۷۳٪».
    expect(card.textContent).toContain('۴۸٪–۷۳٪');
    expect(card.textContent).toContain('۲۳');
    expect(card.textContent).toContain('کندلِ در حال تشکیل');
  });

  it('renders a 0.5 rate as ۵۰٪, not as ۱٪', () => {
    render(<ActiveEventCard pattern={base({
      formation: { probability: 0.5, successes: 5, failures: 4, resolved: 9, confidence: 'medium', horizon: 10, method: 'same-symbol' },
    })} />);
    const card = screen.getByTestId('pattern-card');
    expect(card.textContent).toContain('۵۰٪');
    expect(card.textContent).not.toContain('۱٪');
  });

  it('shows the Persian direction next to the kind', () => {
    render(<ActiveEventCard pattern={base({ direction: 'neutral' })} />);
    expect(screen.getByTestId('pattern-card').textContent).toContain('خنثی');
  });

  it('says the sample is not enough instead of showing a number', () => {
    render(<ActiveEventCard pattern={base({
      formation: { probability: null, successes: 2, failures: 1, resolved: 3, confidence: 'none', horizon: 10, method: 'same-symbol' },
    })} />);
    expect(screen.getByTestId('pattern-card').textContent).toContain('نمونهٔ کافی نیست');
    expect(screen.getByTestId('pattern-card').textContent).not.toMatch(/تشکیل\s*[۰-۹]+٪/);
  });

  it('keeps the 8-sample gate even if a probability leaks through', () => {
    render(<ActiveEventCard pattern={base({
      formation: { probability: 0.62, successes: 4, failures: 3, resolved: 7, confidence: 'low', horizon: 10, method: 'same-symbol' },
    })} />);
    const card = screen.getByTestId('pattern-card');
    expect(card.textContent).toContain('نمونهٔ کافی نیست');
    expect(card.textContent).not.toMatch(/[۰-۹]+٪/);
  });

  it('keeps the percent gate closed at 7 resolved samples', () => {
    render(<ActiveEventCard pattern={base({
      formation: { probability: 0.6, successes: 6, failures: 1, resolved: 7, confidence: 'none', horizon: 10, method: 'same-symbol' },
    })} />);
    expect(screen.getByTestId('pattern-card').textContent).toContain('نمونهٔ کافی نیست');
  });

  it('shows the geometric quality and the measured levels', () => {
    render(<ActiveEventCard pattern={flag()} />);
    const card = screen.getByTestId('pattern-card');
    expect(card.textContent).toContain('کیفیت ساختار ۶۰');
    expect(card.textContent).toContain('هدف ۱۱۲');
    expect(card.textContent).toContain('حد ضرر ۹۸');
  });

  it('shows the 1/3/5-bar returns and the forming-not-confirmed caveat', () => {
    render(<ActiveEventCard pattern={base({
      returns: { h1: 1.2, h3: 2.1, h5: null },
    })} />);
    const card = screen.getByTestId('pattern-card');
    expect(card.textContent).toContain('کندل ۱: ۱٫۲٪');
    expect(card.textContent).toContain('کندل ۳: ۲٫۱٪');
    expect(card.textContent).toContain('کندل ۵: —٪');
    expect(card.textContent).toContain('کندلِ در حال تشکیل ≠ تأییدشده');
  });

  it('badges tier-2 patterns and keeps the percent gate', () => {
    render(<ActiveEventCard pattern={diamond({ formation: null })} />);
    expect(screen.getByTestId('pattern-tier-2').textContent).toContain('کم‌بسامد');
    expect(screen.getByTestId('pattern-quality').textContent).toContain('کیفیت ساختار');
    expect(screen.getByTestId('pattern-card').textContent).not.toMatch(/[۰-۹]+٪/);
  });

  it('renders the empty state when no pattern is forming', () => {
    render(<ActiveEventCard />);
    const card = screen.getByTestId('pattern-card');
    expect(card.textContent).toContain('الگوی در حال تشکیل نیست');
    expect(screen.queryByTestId('pattern-quality')).toBeNull();
    expect(screen.queryByTestId('pattern-tier-2')).toBeNull();
  });
});
