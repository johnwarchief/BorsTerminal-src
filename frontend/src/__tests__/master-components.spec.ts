// تست اجزای مستر: نوار سهم، شدت تضاد، سن سیگنال
import { describe, expect, it } from 'vitest';
import { MasterVerdict } from '@contracts/master';
import { contribBarWidth } from '@features/master/ui/MasterVerdictCard';
import { conflictSeverity } from '@features/master/ui/ConflictBanner';
import { signalAgeLabel } from '@features/master/ui/AgentMatrix';

const NOW = 1_726_000_000_000;

describe('نوار سهم MasterVerdictCard', () => {
  it('سهم صفر حداقل عرض دارد', () => {
    expect(contribBarWidth(0, 80)).toBe(2);
  });

  it('سهم برابر بیشینه عرض کامل دارد', () => {
    expect(contribBarWidth(80, 80)).toBe(100);
  });

  it('سهم منفی با قدر مطلق اندازه گیری می شود', () => {
    expect(contribBarWidth(-40, 80)).toBe(50);
  });

  it('بیشینه صفر همیشه حداقل می دهد', () => {
    expect(contribBarWidth(50, 0)).toBe(0);
  });
});

describe('شدت تضاد ConflictBanner', () => {
  it('شکاف کم شدت کم دارد', () => {
    expect(conflictSeverity(30)).toBe('low');
  });

  it('شکاف میانی شدت متوسط دارد', () => {
    expect(conflictSeverity(80)).toBe('medium');
  });

  it('شکاف کامل شدت زیاد دارد', () => {
    expect(conflictSeverity(160)).toBe('high');
  });
});

describe('سن سیگنال AgentMatrix', () => {
  it('کمتر از یک ساعت لحظه ای است', () => {
    expect(signalAgeLabel(NOW - 30 * 60_000, NOW)).toBe('لحظه ای');
  });

  it('ساعت به فارسی و округ شده است', () => {
    expect(signalAgeLabel(NOW - 5 * 3600_000, NOW)).toBe('۵ ساعت پیش');
  });

  it('بیشتر از ۲۴ ساعت به روز تبدیل می شود', () => {
    expect(signalAgeLabel(NOW - 3 * 24 * 3600_000, NOW)).toBe('۳ روز پیش');
  });
});

describe('قرارداد برآیند با نوار سهم', () => {
  it('verdict معتبر با مشارکت دو ایجنت پاس می شود', () => {
    const v = MasterVerdict.parse({
      symbol: 'شپنا',
      ts: NOW,
      compositeScore: 20,
      finalAction: 'hold',
      contributions: [
        { agentId: 'fundamental', score: 60, signalCount: 1, confidence: 'high' },
        { agentId: 'technical', score: -20, signalCount: 1, confidence: 'medium' },
      ],
      dissent: [],
      usedSignalIds: ['a', 'b'],
      discardedSignalIds: [],
      hasConflict: false,
    });
    const maxAbs = 60;
    expect(contribBarWidth(v.contributions[0].score, maxAbs)).toBe(100);
    expect(contribBarWidth(v.contributions[1].score, maxAbs)).toBeCloseTo(33.3, 0);
  });
});
