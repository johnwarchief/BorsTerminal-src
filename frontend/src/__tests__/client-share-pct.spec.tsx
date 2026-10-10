// __tests__/client-share-pct.spec.tsx — بند ۲ مأموریت: درصدِ حقیقی/حقوقی درِ رابط.
// سه چیز باید ثابت بماند: (۱) رابط هیچ کسرِ دومی نمی‌سازد — همان ستون‌هایِ
// بک‌اند را می‌نویسد، (۲) خرید و فروش دو عددِ مستقل‌اند و هیچ‌وقت یکی جای
// دیگری نمی‌نشیند، (۳) نبودِ ارزش ⇒ «نامشخص»، هرگز ۰٪ و هرگز سهمِ حجم.
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ClientShareInline, ClientSharePct, type ClientShareFields } from '@shared/components/ClientSharePct';

// همان ردیفِ زنده: GetClientTypeHistoryِ نشست 20261007 (پروبِ 1405-07-20) که
// بک‌اند از آن 87.8 و 81.1 ساخته است.
const ok: ClientShareFields = {
  retail_buy_pct: 87.8, legal_buy_pct: 12.2,
  retail_sell_pct: 81.1, legal_sell_pct: 18.9,
  pct_basis: 'value', ctv_d: 20261007, pct_is_current: 0,
};

const txt = (id: string) => screen.getByTestId(id).textContent ?? '';

describe('ClientSharePct', () => {
  it('دو سمت با برچسبِ کاملِ «سهم از ارزش خرید / فروش» و همان درصدهایِ بک‌اند', () => {
    render(<ClientSharePct row={ok} />);
    expect(txt('client-share-buy')).toContain('سهم از ارزش خرید');
    expect(txt('client-share-buy')).toContain('۸۷.۸٪');
    expect(txt('client-share-buy')).toContain('۱۲.۲٪');
    expect(txt('client-share-sell')).toContain('سهم از ارزش فروش');
    expect(txt('client-share-sell')).toContain('۸۱.۱٪');
    expect(txt('client-share-sell')).toContain('۱۸.۹٪');
    expect(screen.getByTestId('client-share').getAttribute('data-basis')).toBe('value');
  });

  it('درصدِ خرید هرگز جای درصدِ فروش نمی‌نشیند (دو کسرِ مستقل)', () => {
    render(<ClientSharePct row={{ ...ok, retail_sell_pct: 5.0, legal_sell_pct: 95.0 }} />);
    expect(txt('client-share-buy')).toContain('۸۷.۸٪');
    expect(txt('client-share-buy')).not.toContain('۵.۰٪');
    expect(txt('client-share-sell')).toContain('۵.۰٪');
  });

  it('بی‌ردیفِ مبدأ ⇒ «نامشخص»، بی‌صفر و بی‌عددِ حجم', () => {
    render(<ClientSharePct row={{}} testId="cs-none" />);
    expect(txt('cs-none-buy')).toContain('نامشخص');
    expect(txt('cs-none-sell')).toContain('نامشخص');
    expect(txt('cs-none-buy')).not.toMatch(/۰٪/);
    expect(screen.getByTestId('cs-none').getAttribute('data-has-data')).toBe('0');
    const reason = screen.getByTestId('cs-none').getAttribute('title') ?? '';
    expect(reason).toContain('نامشخص');
    expect(reason).toContain('ضربِ حجم');
  });

  it('یک سمتِ نصفه‌نیمه: فروش نامشخص می‌ماند و خرید درست می‌آید', () => {
    render(<ClientSharePct row={{ retail_buy_pct: 75.0, legal_buy_pct: 25.0,
                                  pct_basis: 'value', ctv_d: 20261007 }} testId="cs-half" />);
    expect(txt('cs-half-buy')).toContain('۷۵.۰٪');
    expect(txt('cs-half-sell')).toContain('نامشخص');
  });

  it('عددِ نشستِ پیشین با تاریخِ خودش خوانده می‌شود، نه به‌عنوان زنده', () => {
    render(<ClientSharePct row={ok} testId="cs-old" />);
    const note = screen.getByTestId('cs-old-buy').getAttribute('title') ?? '';
    expect(note).toContain('۱۴۰۵/۰۷/۱۵');
    expect(note).toContain('هنوز منتشر نکرده');
  });

  it('همان نشستِ تابلو: «از نشستِ همان روزِ تابلو» با تاریخ', () => {
    render(<ClientSharePct row={{ ...ok, pct_is_current: 1 }} testId="cs-cur" />);
    expect(screen.getByTestId('cs-cur-buy').getAttribute('title'))
      .toContain('از نشستِ همان روزِ تابلو');
  });

  it('نسخۀِ تک‌خط: دو مقدارِ مستقل درِ buy و sell، و بی‌داده ⇒ نامشخص', () => {
    render(<div>
      <ClientShareInline row={ok} side="buy" testId="ci-buy" />
      <ClientShareInline row={ok} side="sell" testId="ci-sell" />
      <ClientShareInline row={{}} side="sell" testId="ci-none" />
    </div>);
    expect(txt('ci-buy')).toContain('۸۷.۸٪');
    expect(txt('ci-buy')).toContain('۱۲.۲٪');
    expect(txt('ci-sell')).toContain('۸۱.۱٪');
    expect(txt('ci-sell')).not.toContain('۸۷.۸٪');
    expect(txt('ci-none')).toBe('نامشخص');
    expect(screen.getByTestId('ci-none').getAttribute('data-state')).toBe('unknown');
  });

  it('مقدارِ بی‌اعتبارِ فرستاده‌شده (NaN/null) عدد نمی‌سازد', () => {
    render(<ClientSharePct row={{ retail_buy_pct: null, legal_buy_pct: 12.2,
                                  retail_sell_pct: Number.NaN, legal_sell_pct: 0,
                                  pct_basis: 'value' }} testId="cs-bad" />);
    expect(txt('cs-bad-buy')).toContain('نامشخص');
    expect(txt('cs-bad-sell')).toContain('نامشخص');
  });
});
