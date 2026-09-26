// @vitest-environment jsdom
// __tests__/assembly-badge-table.spec.tsx — برچسب «مجمع نزدیک» در جدول بنیادی
// این برچسب پیش‌تر کاملاً نوشته شده بود (lib/assemblyEvent.ts + AssemblyBadge) ولی
// هیچ‌جا به جدول وصل نبود؛ تست‌ها هم مستقیم کامپوننت را می‌سنجیدند پس وصل‌نبودنِ
// آن به صفحه دیده نشد. اینجا مسیرِ واقعیِ دادهٔ انبوه تا رندرِ ردیف سنجیده می‌شود.
import { describe, it, expect } from 'vitest';
import { groupBySymbol } from '@features/fundamental/api/useCalendarUpcoming';
import { pickAssemblyBadge } from '@features/fundamental/lib/assemblyEvent';

/** امروزِ آزمون ثابت است تا نتیجه با گذشت زمان عوض نشود */
const NOW = new Date('2026-09-26T12:00:00+03:30');

describe('مسیر انبوهٔ تقویم → برچسب ردیف', () => {
  it('پاسخِ تختِ /api/calendar/upcoming به نقشهٔ نماد→رویداد تبدیل می‌شود', () => {
    const map = groupBySymbol([
      { symbol: 'داریک بازار', date: '2026-09-26', cat: 'assembly', title: 'آگهی دعوت به مجمع' },
      { symbol: ' سرآمد بازار ', date: '2026-10-06', cat: 'assembly', title: 'آگهی دعوت به مجمع' },
      { symbol: '', date: '2026-10-06', cat: 'assembly', title: 'بی‌نماد' },
    ]);
    expect(Object.keys(map)).toEqual(['داریک بازار', 'سرآمد بازار']);
    expect(map['سرآمد بازار'][0]).toMatchObject({ date: '2026-10-06', cat: 'assembly' });
  });

  it('نمادی که ده روز بعد مجمع دارد برچسب «نزدیک» می‌گیرد', () => {
    const map = groupBySymbol([
      { symbol: 'خفولا', date: '2026-10-06', cat: 'assembly', title: 'آگهی دعوت به مجمع عادی' },
    ]);
    const badge = pickAssemblyBadge(map['خفولا'], NOW);
    expect(badge).not.toBeNull();
    expect(badge?.kind).toBe('near');
    expect(badge?.testId).toBe('assembly-near-badge');
    expect(badge?.jalali).toMatch(/^۱۴۰/);
  });

  it('مجمعِ بیرونِ پنجرهٔ «نزدیک» برچسب نمی‌گیرد — تاریخِ دور ساخته نمی‌شود', () => {
    const map = groupBySymbol([
      { symbol: 'فلان', date: '2026-12-28', cat: 'assembly', title: 'آگهی دعوت به مجمع' },
    ]);
    expect(pickAssemblyBadge(map['فلان'], NOW)).toBeNull();
  });

  it('لغو/تعویق مجمع برچسبِ تغییر می‌گیرد نه تاریخِ مجمعِ باطل‌شده', () => {
    const map = groupBySymbol([
      { symbol: 'بهمان', date: '2026-09-28', cat: 'assembly', title: 'برگزاری مجمع' },
      { symbol: 'بهمان', date: '2026-09-27', cat: 'assemblyChange', title: 'لغو برگزاری مجمع' },
    ]);
    const badge = pickAssemblyBadge(map['بهمان'], NOW);
    expect(badge?.kind).toBe('change');
    expect(badge?.testId).toBe('assembly-change-badge');
  });

  it('بدون رویداد هیچ برچسبی نیست', () => {
    expect(pickAssemblyBadge([], NOW)).toBeNull();
    expect(pickAssemblyBadge(undefined, NOW)).toBeNull();
  });
});
