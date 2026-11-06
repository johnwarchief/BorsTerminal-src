/**
 * frontend-v2/src/features/technical/ui/workspace/__tests__/InspectorRail.test.tsx
 *
 * آزمون‌های ریل بازرس پس از B3:
 * - کارت رویداد فعال از `detectedPatterns` و آخرین الگوی در حال تشکیل ساخته می‌شود
 * - کارت بالای بخش لایه‌ها می‌نشیند (نه در فید)
 * - نبودِ الگوی در حال تشکیل، حالت خالی کارت را نشان می‌دهد
 */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { InspectorRail } from '../InspectorRail';
import { useTechnicalStore } from '../../../model/technicalStore';
import type { ChartPattern } from '../../../model/patterns/types';
import type { FormationEstimate } from '../../../model/types';

const point = (index: number, price = 100) => ({ index, price, timestamp: index * 60_000 });

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

afterEach(cleanup);
beforeEach(() => {
  useTechnicalStore.getState().reset();
});

describe('InspectorRail active event card', () => {
  it('shows the last forming tier-1 pattern while the low-frequency switch is off', () => {
    useTechnicalStore.getState().setDetectedPatterns([
      base({
        id: 'older',
        anchor: point(40),
        formation: { probability: 0.62, successes: 14, failures: 9, resolved: 23, confidence: 'medium', horizon: 10, method: 'same-symbol' },
      }),
      base({
        id: 'newer',
        kind: 'DIAMOND_TOP',
        direction: 'bearish',
        family: 'reversal',
        tier: 2,
        anchor: point(55),
        quality: 72,
        formation: { probability: 0.4, successes: 10, failures: 15, resolved: 25, confidence: 'medium', horizon: 10, method: 'same-symbol' },
      }),
      // تأییدشده هرگز «رویداد فعال» نیست؛ در ریل فقط forming ملاک است.
      base({ id: 'confirmed', status: 'confirmed', anchor: point(60) }),
    ]);

    render(<InspectorRail />);

    const card = screen.getByTestId('pattern-card');
    expect(card.textContent).toContain('پرچم صعودی');
    expect(card.textContent).toContain('۶۲٪');
    expect(card.textContent).toContain('کیفیت ساختار ۶۰');
    expect(card.textContent).toContain('هدف ۱۱۲');
    expect(card.textContent).toContain('حد ضرر ۹۸');
    expect(card.textContent).toContain('کندلِ در حال تشکیل ≠ تأییدشده');
    expect(screen.queryByTestId('pattern-tier-2')).toBeNull();
  });

  it('shows a tier-2 forming pattern only when the low-frequency switch is on', () => {
    useTechnicalStore.getState().setDetectedPatterns([
      base({ id: 'older', anchor: point(40) }),
      base({
        id: 'newer', kind: 'DIAMOND_TOP', direction: 'bearish', family: 'reversal',
        tier: 2, anchor: point(55), quality: 72,
        formation: { probability: 0.4, successes: 10, failures: 15, resolved: 25, confidence: 'medium', horizon: 10, method: 'same-symbol' },
      }),
    ]);
    useTechnicalStore.getState().toggleTier2Patterns();

    render(<InspectorRail />);

    const card = screen.getByTestId('pattern-card');
    expect(card.textContent).toContain('دیاموند سقف');
    expect(card.textContent).toContain('۴۰٪');
    expect(screen.getByTestId('pattern-tier-2').textContent).toContain('کم‌بسامد');
  });

  it('renders the card above the layers section', () => {
    useTechnicalStore.getState().setDetectedPatterns([base()]);
    render(<InspectorRail />);

    const card = screen.getByTestId('pattern-card');
    const layersHeading = screen.getByText('لایه‌ها و قواعد');
    expect(card.compareDocumentPosition(layersHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('keeps the card empty when no pattern is forming', () => {
    useTechnicalStore.getState().setDetectedPatterns([base({ status: 'confirmed' })]);
    render(<InspectorRail />);

    expect(screen.getByTestId('pattern-card').textContent).toContain('الگوی در حال تشکیل نیست');
    expect(screen.queryByTestId('pattern-quality')).toBeNull();
  });
});
