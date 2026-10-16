// تستِ جمع‌بندیِ تازگی (بازطراحیِ صفحات، فاز G)
//
// چرا لازم شد: فازِ D برچسبِ تازگیِ به‌ازایِ ویجت را آورد، ولی گرفتنیِ ۱۳۶×۷۶۸ نشان
// داد چهارِ برچسبِ کامل درِ یکِ بخش خودشان بهِ دیوارِ چیپ تبدیل می‌شوند. جمع‌بندی
// باید همانِ صداقت را باِ کمترینِ تکرار بگوید، پس اینِ قواعد آزمون می‌شوند:
// ۱) هرِ ویجت باِ نامِ خودش خوانده می‌شود — ادغام فقط برایِ وضعیت‌هایِ یکسان.
// ۲) ساعتِ منبعِ هرِ پنل ازِ خودِ همانِ پنل است؛ نه ازِ همسایه، نه صفر، نه سکوت.
// ۳) هیچِ آستانه‌ای اختراع نمی‌شود: سه‌ساعت ازِ پاسخِ سالم همان «سالم» می‌ماند.
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  FreshnessSummary,
  summarizeFreshness,
  type FreshItem,
} from '@features/market/components/WidgetFreshness';

const NOW = 1_800_000_000_000;
const ok = (label: string, ageMs: number, sourceAsOf: string | null = null): FreshItem => ({
  label,
  input: { status: 'success', dataUpdatedAt: NOW - ageMs, sourceAsOf, now: NOW },
});
const pending = (label: string): FreshItem => ({
  label,
  input: { status: 'pending', dataUpdatedAt: 0, now: NOW },
});
const failed = (label: string, ageMs: number): FreshItem => ({
  label,
  input: { status: 'error', error: true, dataUpdatedAt: NOW - ageMs, now: NOW },
});

const allLabels = (sum: ReturnType<typeof summarizeFreshness>) => sum.groups.map((g) => g.labels.join('، ')).join(' | ');

describe('summarizeFreshness', () => {
  it('وضعیت‌هایِ یکسان درِ یکِ گروه ادغام می‌شوند، ولی هرِ نام باقی می‌ماند', () => {
    const sum = summarizeFreshness(
      [ok('کارت‌های شاخص', 5_000), ok('توزیعِ درصد', 5_000), ok('فازهای نشست', 5_000)],
      NOW,
    );
    expect(sum.groups).toHaveLength(1);
    expect(sum.groups[0].labels).toEqual(['کارت‌های شاخص', 'توزیعِ درصد', 'فازهای نشست']);
    expect(sum.ok).toBe(3);
  });

  it('ساعتِ منبعِ متفاوت ⇒ گروهِ جدا (دانشِ هرِ پنل ازِ خودِ پاسخِ خودش می‌آید)', () => {
    const sum = summarizeFreshness(
      [ok('کارت‌های شاخص', 5_000, '۰۲:۴۳:۵۰'), ok('توزیعِ درصد', 5_000), ok('فازهای نشست', 5_000)],
      NOW,
    );
    expect(sum.groups).toHaveLength(2);
    const withSource = sum.groups.find((g) => g.view.sourceText.includes('ساعتِ منبع'));
    expect(withSource?.labels).toEqual(['کارت‌های شاخص']);
    expect(allLabels(sum)).toContain('توزیعِ درصد');
    expect(allLabels(sum)).toContain('فازهای نشست');
  });

  it('نخوانده وِ بی‌پاسخ ازِ سالم جدا می‌مانند وِ نامِ خودشان را نگه می‌دارند', () => {
    const sum = summarizeFreshness([ok('کارت‌های شاخص', 5_000), pending('تفکیکِ مشتری'), failed('فازهای نشست', 90_000)], NOW);
    const states = sum.groups.map((g) => g.view.state).sort();
    expect(states).toEqual(['error', 'ok', 'pending']);
    expect(allLabels(sum)).toContain('تفکیکِ مشتری');
  });

  it('آستانه اختراع نمی‌کند: پاسخِ سه‌ساعتۀِ سالم همان «سالم» می‌ماند', () => {
    const sum = summarizeFreshness([ok('نقشۀ بازار', 3 * 60 * 60 * 1000)], NOW);
    expect(sum.ok).toBe(1);
    expect(sum.groups.every((g) => g.view.state === 'ok')).toBe(true);
  });
});

describe('<FreshnessSummary />', () => {
  it('بی‌هیچ‌ویجتی چیزی render نمی‌کند', () => {
    const { container } = render(<FreshnessSummary items={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('چهارِ ویجتِ هم‌وضعیت ⇒ یکِ برچسب، وِ هرِ چهار نام درِ آن', () => {
    render(<FreshnessSummary items={[
      ok('کارت‌های شاخص', 5_000), ok('توزیعِ درصد', 5_000), ok('تفکیکِ مشتری', 5_000), ok('فازهای نشست', 5_000),
    ]} />);
    const chips = screen.getAllByTestId('widget-freshness');
    expect(chips).toHaveLength(1);
    expect(chips[0].textContent).toContain('کارت‌های شاخص');
    expect(chips[0].textContent).toContain('فازهای نشست');
    expect(screen.getByTestId('freshness-summary')).toHaveAttribute('data-state', 'all-ok');
  });

  it('نخوانده «زمانِ داده از منبع نیامد» را صریح می‌گوید، نه ساعتِ همسایه', () => {
    render(<FreshnessSummary items={[ok('کارت‌های شاخص', 5_000, '۰۲:۴۳:۵۰'), pending('تفکیکِ مشتری')]} />);
    const chips = screen.getAllByTestId('widget-freshness');
    const mine = chips.find((c) => (c.textContent || '').includes('تفکیکِ مشتری'));
    expect(mine?.textContent).toContain('زمانِ داده از منبع نیامد');
    expect(mine?.textContent).not.toContain('۰۲:۴۳:۵۰');
  });

  it('بی‌پاسخِ رویِ دادهٔ پیشین همان دو کلمه را نگه می‌دارد', () => {
    render(<FreshnessSummary items={[failed('فازهای نشست', 90_000)]} />);
    expect(screen.getByTestId('widget-freshness').textContent).toContain('بی‌پاسخ (دادهٔ پیشین)');
  });
});
