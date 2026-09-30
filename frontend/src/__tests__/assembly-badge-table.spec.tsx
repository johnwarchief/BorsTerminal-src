// @vitest-environment jsdom
// __tests__/assembly-badge-table.spec.tsx — برچسب «مجمع نزدیک» در جدول بنیادی
// این برچسب پیش‌تر کاملاً نوشته شده بود (lib/assemblyEvent.ts + AssemblyBadge) ولی
// هیچ‌جا به جدول وصل نبود؛ تست‌ها هم مستقیم کامپوننت را می‌سنجیدند پس وصل‌نبودنِ
// آن به صفحه دیده نشد. اینجا مسیرِ واقعیِ دادهٔ انبوه تا رندرِ ردیف سنجیده می‌شود.
import { describe, it, expect } from 'vitest';
import { groupBySymbol } from '@features/fundamental/api/useCalendarUpcoming';
import { isCapitalIncreaseEvent, pickAssemblyBadge, pickCapitalBadge } from '@features/fundamental/lib/assemblyEvent';

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

/**
 * «افزایش سرمایه» (#59) — از همان یک درخواستِ انبوه، کلیدِ `capital`.
 * قاعده‌ها: فقط برچسب است (وتو نمی‌سازد)، عنوان‌محور است تا اطلاعیه‌ای که هم
 * مجمع است هم افزایشِ سرمایه، هر دو برچسب را بگیرد، و بیرونِ افق چیزی نیست.
 */
describe('برچسب «افزایش سرمایه» از پاسخِ انبوه', () => {
  it('دعوۀ مجمع با موضوعِ افزایشِ سرمایه هر دو برچسب را می‌گیرد', () => {
    const evs = [
      { symbol: 'خزکو', date: '2026-10-06', cat: 'assemblyExtra', title: 'آگهی دعوت به مجمع فوق العاده جهت افزایش سرمایه' },
    ];
    const map = groupBySymbol(evs);
    expect(pickAssemblyBadge(map['خزکو'], NOW)?.kind).toBe('near');
    expect(pickCapitalBadge(map['خزکو'], NOW)).not.toBeNull();
    expect(isCapitalIncreaseEvent(map['خزکو'][0])).toBe(true);
  });

  it('برچسبِ افزایشِ سرمایه با تاریخِ جلالی و شمارِ روز', () => {
    const map = groupBySymbol([
      { symbol: 'ولغیر', date: '2026-10-01', cat: 'capitalIncrease', title: 'افزایش سرمایه از محل سود انباشته' },
    ]);
    const b = pickCapitalBadge(map['ولغیر'], NOW);
    expect(b?.testId).toBe('capital-increase-badge');
    expect(b?.label).toContain('افزایش سرمایه');
    expect(b?.days).toBe(5);
  });

  it('بیرونِ افق و رویدادِ بی‌ربط ⇒ هیچ برچسبی', () => {
    const far = groupBySymbol([
      { symbol: 'الف', date: '2026-12-28', cat: 'capitalIncrease', title: 'افزایش سرمایه' },
    ]);
    expect(pickCapitalBadge(far['الف'], NOW)).toBeNull();
    const other = groupBySymbol([
      { symbol: 'ب', date: '2026-09-20', cat: 'dividend', title: 'پرداخت سود نقدی' },
    ]);
    expect(pickCapitalBadge(other['ب'], NOW)).toBeNull();
    expect(isCapitalIncreaseEvent(other['ب'][0])).toBe(false);
  });
});
