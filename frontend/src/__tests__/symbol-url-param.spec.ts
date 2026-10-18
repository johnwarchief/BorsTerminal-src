// تستِ قاعدۀ «URL برندۀ store» برایِ نماد (فاز D، بندِ ۲ وِ ۵ مأموریت)
//
// چرا اینِ فایل هست: درخت استراتژی **هر دو** شکلِ نشانی را می‌شناسد — نوارِ کناریِ
// نماد `/strategy-tree/<symbol>` را می‌سازد (`SymbolContextStrip.tsx:37`) وِ stepper
// همان را به شکلِ `?symbol=` می‌سازد (`StrategyTreeStepper`). خودِ صفحه‌ها فقط `params.get('symbol')`
// را می‌خوانند، پس آدرسِ «فولاد» بی‌سروصدا بهِ نمادِ ذخیره‌شدۀِ پیشین می‌افتد: کاربر
// فولاد را می‌زند وِ شپنا را می‌بیند. اینِ همانِ نقصِ «واگراییِ استور ازِ URL» است که
// فاز C برایِ تب‌ها بست، وِ قاعدۀِ درستِ آنِ جا اینجا هم حاکم است: نشانی برنده است.
import { describe, expect, it } from 'vitest';
import { mainRoutes } from '../routes';
import { SYMBOL_ROUTES, symbolInPath } from '@shared/stores/workspaceStore';
import { resolveSymbolParam } from '@shared/lib/symbolParam';

describe('اولویتِ نماد: نشانی بر store', () => {
  it('پارامترِ مسیر برنده است، حتی وقتیِ استور پر است', () => {
    expect(resolveSymbolParam({ path: 'فولاد', query: null, stored: 'شپنا' })).toBe('فولاد');
  });

  it('پارامترِ query اگرِ مسیر خالی بود خوانده می‌شود (لینکِ stepper نمی‌شکند)', () => {
    expect(resolveSymbolParam({ path: null, query: 'فملی', stored: 'شپنا' })).toBe('فملی');
  });

  it('هرِ دو نشانی خالی ⇒ همانِ استور، بدونِ ساختنِ نمادِ جعلی', () => {
    expect(resolveSymbolParam({ path: null, query: null, stored: 'خودرو' })).toBe('خودرو');
    expect(resolveSymbolParam({ path: '', query: '', stored: '' })).toBe('');
  });

  it('نشانه‌هایِ بی‌معنا (`-`، `undefined`) نماد شمرده نمی‌شوند', () => {
    expect(resolveSymbolParam({ path: '-', query: 'فولاد', stored: 'شپنا' })).toBe('فولاد');
    expect(resolveSymbolParam({ path: 'null', query: undefined, stored: 'شپنا' })).toBe('شپنا');
  });

  it('نمونِ encodeشدۀِ نشانیِ مسیر بازخوانی می‌شود (هش‌روتر آن را encode می‌کند)', () => {
    expect(resolveSymbolParam({ path: '%D9%81%D9%88%D9%84%D8%A7%D8%AF', query: null, stored: '' })).toBe('فولاد');
  });
});

describe('آدرس‌پذیریِ نماد درِ جدولِ مسیرها', () => {
  it('درختِ استراتژی وِ پرتفوی هر دو `:symbol?` دارند', () => {
    const paths = mainRoutes.map((r) => r.path);
    expect(paths).toContain('strategy-tree/:symbol?');
    expect(paths).toContain('portfolio/:symbol?');
  });

  it('هرِ دو مسیر درِ شمارندۀِ تب‌ها نماد‌بر شمرده می‌شوند تاِ برچسبِ تب گم نشود', () => {
    expect(SYMBOL_ROUTES).toContain('strategy-tree');
    expect(SYMBOL_ROUTES).toContain('portfolio');
    expect(symbolInPath('/portfolio/فولاد')).toBe('فولاد');
    expect(symbolInPath('/strategy-tree/شپنا')).toBe('شپنا');
    // وِ مسیرِ بی‌نماد همانِ صفحه را بی‌نماد می‌دهد، نه `undefined` به‌عنوانِ نماد
    expect(symbolInPath('/portfolio')).toBe('');
  });
});
