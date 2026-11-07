// __tests__/fts-fundamental-badges.spec.tsx — گاردِ تفکیکِ بج‌های تبِ بنیادی
// حکمِ ردیفِ این تب از ۵ شاخص، وضعیتِ داده، مجمع/افزایش سرمایه و فیلترهای
// ریسک ساخته می‌شود. بج‌های تکنیکال (ساعت شنی، جت، وتوی روند، کاندیدِ قیف)
// جای دیگری دارند و نباید در این جدول رندر شوند؛ فیلدهایشان در
// useFtsScreen.ts می‌ماند چون تبِ تکنیکال مصرف‌کنندهٔ آن‌هاست.
import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const src = fs.readFileSync(
  path.resolve(process.cwd(), 'src/features/fundamental/ui/FtsScreenTable.tsx'),
  'utf8',
);

describe('fundamental tab badge separation', () => {
  it('does not render technical badges', () => {
    expect(src).not.toMatch(/استراتژی ساعت شنی FTS فعال/);
    expect(src).not.toMatch(/ستاپ جت FTS/);
    expect(src).not.toMatch(/ممنوعیت ورود FTS/);
    expect(src).not.toMatch(/هر سه گامِ قیف/);
  });

  it('does not read technical row fields', () => {
    expect(src).not.toMatch(/tech_hourglass_active/);
    expect(src).not.toMatch(/tech_jet/);
    expect(src).not.toMatch(/tech_matrix_decision/);
    expect(src).not.toMatch(/funnel_candidate/);
  });

  it('keeps assembly and capital increase', () => {
    // شناسه‌هایِ واقعیِ سمتِ «نگه‌داشتن» — نه واژه‌هایِ عمومی که با نامِ prop هم
    // جور می‌شوند: ساختِ بجِ مجمع/افزایش سرمایه و test-idهایِ ردیف باید بمانند.
    expect(src).toContain('pickAssemblyBadge');
    expect(src).toContain('pickCapitalBadge');
    expect(src).toContain('row-assembly-veto-badge');
    expect(src).toContain('افزایش سرمایه');
  });

  it('does not render the removed funnel-candidate row badge', () => {
    expect(src).not.toMatch(/data-testid="row-funnel-candidate"/);
  });
});
