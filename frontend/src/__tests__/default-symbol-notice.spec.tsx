// آزمونِ «دیدنی‌کردنِ فولبک» (فاز D، بندِ ۵)
//
// سه صفحۀِ برنامه نمادِ پیش‌فرض دارند که **عمدی**اند وِ درِ کامنتِ خودِ فایل دفاع شده
// (صفحۀِ بی‌انتخاب برایِ تازه‌وارد خاموش نماند، وِ نمادِ جعلی درِ استورِ سراسری نوشته
// نشود: `TechnicalPage.tsx:59`، `MarketChartSection`، `WatchMarketWorkspace:117`).
// نقصِ واقعی سکوتِ رابط بود: «فولاد» نشان داده می‌شد وِ کاربر آن را انتخابِ خودِ می‌خواند.
//
// نکتۀِ ظریفی که اینِ فایل قفل می‌کند: پرسشِ «فولبک بود یاِ نه» باِ مقایسهِٔ دوِ رشته
// جواب نمی‌دهد. `/technical/فملی` وقتی استور «فولاد» است، آدرسِ خودِ کاربر است؛ اگر
// `shown !== stored` سنجیده شود، برچسبِ «پیش‌فرض» دروغ می‌گوید. پس **منبعِ مقدار**
// خوانده می‌شود، نه اختلافِ متن.
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DefaultSymbolNotice, isDefaultDisplay } from '@shared/components/DefaultSymbolNotice';

describe('مرزِ «فولبک دیده شود» — ازِ دیدِ منبعِ مقدار', () => {
  it('نه آدرس وِ نه استور ⇒ صحنه ازِ فولبک آمده', () => {
    expect(isDefaultDisplay({ shown: 'فولاد', url: null, stored: '' })).toBe(true);
  });

  it('استور پر است ⇒ انتخابِ خودِ کاربر، بی‌برچسب', () => {
    expect(isDefaultDisplay({ shown: 'فولاد', stored: 'فولاد' })).toBe(false);
  });

  it('آدرس برنده است، حتی وقتیِ استور چیزِ دیگری می‌گوید (قاعدۀِ فاز C)', () => {
    expect(isDefaultDisplay({ shown: 'فملی', url: 'فملی', stored: 'فولاد' })).toBe(false);
  });

  it('فاصله‌یِ اضافی درِ آدرس شرط را نمی‌شکند', () => {
    expect(isDefaultDisplay({ shown: 'شپنا', url: ' شپنا ' })).toBe(false);
  });

  it('بی‌نمادِ رویِ صحنه ⇒ برچسبی نیست (نه «پیش‌فرض: » خالی)', () => {
    expect(isDefaultDisplay({ shown: '', url: null, stored: '' })).toBe(false);
    expect(isDefaultDisplay({ shown: '', stored: 'فولاد' })).toBe(false);
  });
});

describe('رندرِ برچسب', () => {
  it('فقط درِ حالتِ فولبک دیده می‌شود وِ نامِ نماد را می‌گوید', () => {
    const { unmount } = render(<DefaultSymbolNotice shown="فولاد" />);
    const el = screen.getByTestId('default-symbol-notice');
    expect(el.textContent).toContain('فولاد');
    expect(el.textContent).toContain('انتخابِ شما نبود');
    unmount();

    render(<DefaultSymbolNotice shown="فولاد" stored="فولاد" />);
    expect(screen.queryByTestId('default-symbol-notice')).toBeNull();
  });

  it('رنگ‌ها ازِ لایۀ tone می‌آیند (بی‌کلاسِ اختصاصیِ تازه)', () => {
    render(<DefaultSymbolNotice shown="خودرو" />);
    const cls = screen.getByTestId('default-symbol-notice').className;
    expect(cls).toContain('text-tone-warn');
    expect(cls).toContain('border-tone-warn/40');
  });

  it('testId قابلِ تنظیم است تاِ سه صفحۀِ متفاوت باِ هم نیفتند', () => {
    render(<DefaultSymbolNotice shown="فولاد" testId="watch-default-symbol" />);
    expect(screen.getByTestId('watch-default-symbol')).toBeInTheDocument();
  });
});
