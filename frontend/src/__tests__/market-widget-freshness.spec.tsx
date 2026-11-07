// تستِ برچسبِ تازگیِ **به‌ازایِ ویجت** درِ «وضعیت بازار» (فاز D، بندِ ۱ مأموریت)
//
// چرا لازم شد: تازگی تا این دور یک ساعتِ سراسری داشت (پنلِ `MarketStatusPanel` از
// `/api/live-stats`)، ولی هشت بخشِ اینِ صفحه از هشت کوئریِ جدا می‌آیند و هر کدام
// پنجرۀِ پاسخِ خودشان. یکِ برچسبِ سراسری یعنی نقشۀِ بازاری که سه دورِ پیش خوانده
// شده، باِ «لحظاتی پیش» خوانده شود — وِ این همان چیزی است که قاعدۀ «بی‌داده ≠ صفر»
// وِ «اتصال ≠ تازگی» ردّش می‌کند.
//
// سه قاعدۀِ بسته‌شدہ درِ اینِ فایل:
// ۱) سنِ *دریافت* از خودِ همانِ کوئری خوانده می‌شود (`dataUpdatedAt`، ساعتِ کلاینت)
//    وِ از حدسِ رابط ساخته نمی‌شود.
// ۲) هیچ آستانۀِ «کهنه» اختراع نمی‌شود: ریتمِ pollingِ هر ویجت درِ اینِ فایلِ سنجش
//    نیست، پس وضعیت فقط از `statusِ` واقعی (success/error/loading) می‌آید. هر
//    آستانۀِ ساختگی یکِ دروغِ تازه درِ رابط است.
// ۳) اگر منبعِ داده زمانِ خودِ عدد را گزارش نکند (`sourceAsOf` نبود)، رابط همان را
//    صریح می‌گوید — نه ساعتِ ساختگی، نه صفر، نه سکوت.
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  WidgetFreshness,
  freshnessOf,
  type WidgetFreshInput,
} from '@features/market/components/WidgetFreshness';

const NOW = 1_700_000_000_000;

const base: WidgetFreshInput = { status: 'success', dataUpdatedAt: NOW, now: NOW };

describe('تازگیِ به‌ازایِ ویجت (فاز D)', () => {
  it('سنِ دریافت را از خودِ کوئری می‌خواند و با رقمِ فارسی می‌گوید', () => {
    const f = freshnessOf({ ...base, dataUpdatedAt: NOW - 5 * 60_000 });
    expect(f.ageText).toContain('۵');
    expect(f.ageText).toContain('دقیقه پیش');
    expect(f.state).toBe('ok');
  });

  it('بی‌پاسخ را «بی‌پاسخ» می‌گوید و سنِ داده‌شده را پنهان نمی‌کند', () => {
    const f = freshnessOf({ ...base, status: 'error', error: true });
    expect(f.state).toBe('error');
    expect(f.label).toContain('بی‌پاسخ');
    // آخرینِ پاسخِ موفق هنوز درِ حافظه هست ⇒ سنِ آن باید دیده شود، نه اینکه
    // «لحظاتی پیش» بشود: خطا نمی‌تواند تازگیِ جعلی بسازد.
    expect(f.ageText).toBe('لحظاتی پیش');
  });

  it('هنوز-بی‌داده را «در حالِ خواندن» می‌گوید و عددِ سن نمی‌سازد', () => {
    const f = freshnessOf({ ...base, status: 'pending', dataUpdatedAt: 0 });
    expect(f.state).toBe('pending');
    expect(f.ageText).toBeNull();
    expect(f.label).toContain('در حالِ خواندن');
  });

  it('وقتی منبع زمانِ داده را گزارش نمی‌کند، نبودنش صریح گفته می‌شود', () => {
    const f = freshnessOf({ ...base, sourceAsOf: null });
    expect(f.sourceText).toContain('زمانِ داده از منبع نیامد');
    expect(f.sourceText).not.toMatch(/[۰-۹]/);      // هیچ ساعتِ ساختگی نیست
  });

  it('زمانِ منبع را عیناً نشان می‌دهد وِ بازنویسیِ ساعتی انجام نمی‌دهد', () => {
    const f = freshnessOf({ ...base, sourceAsOf: '۱۱:۰۶' });
    expect(f.sourceText).toContain('۱۱:۰۶');
  });

  it('رنگ‌ها از لایۀ tone می‌آیند، نه از کلاسِ اختصاصیِ تازه', () => {
    render(<WidgetFreshness label="نقشۀ بازار" input={{ ...base, status: 'error', error: true }} />);
    const el = screen.getByTestId('widget-freshness');
    expect(el.className).toContain('text-tone-err');
    expect(el.className).not.toMatch(/#[0-9a-fA-F]{3,6}/);
    render(<WidgetFreshness label="نقشۀ بازار" input={{ ...base, status: 'pending', dataUpdatedAt: 0 }} />);
    expect(screen.getAllByTestId('widget-freshness')[1].className).toContain('text-tone-unknown');
  });

  it('برچسبِ ویجت را می‌برد تا دو بخش باِ هم یکی نشوند', () => {
    render(<WidgetFreshness label="طلا، سکه و صندوق طلا" input={base} />);
    expect(screen.getByTestId('widget-freshness').textContent).toContain('طلا');
  });

  it('صفحه‌خوان سلسله‌مراتبِ بی‌داده را با aria-hidden نمی‌بندد', () => {
    render(<WidgetFreshness label="نمای کلی" input={{ ...base, status: 'error', error: true }} />);
    const el = screen.getByTestId('widget-freshness');
    expect(el.getAttribute('aria-hidden')).toBeNull();
    expect(el.textContent).toContain('بی‌پاسخ');
  });
});
