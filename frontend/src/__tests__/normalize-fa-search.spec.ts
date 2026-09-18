import { describe, expect, it } from 'vitest';
import { normalizeFa, matchFa } from '@shared/lib/normalizeFa';
import { filterWatchlist } from '@features/technical/api/useWatchlist';
import type { MarketRow } from '@shared/types/marketRow';

describe('نرمال‌سازی نوشتار فارسی/عربی در جستجوی نمادها (رفع باگ عدم نمایش فملی)', () => {
  it('یکسان‌سازی ي عربی و ی فارسی در نماد فملی', () => {
    const arSymbol = 'فملي'; // Arabic Yeh \u064A
    const faSymbol = 'فملی'; // Persian Yeh \u06CC
    expect(normalizeFa(arSymbol)).toBe(normalizeFa(faSymbol));
  });

  it('تطابق دوطرفه با matchFa برای فملی و فملي', () => {
    expect(matchFa('فملي', 'فملی')).toBe(true);
    expect(matchFa('فملی', 'فملي')).toBe(true);
  });

  it('تطابق کلمات با فاصله و نیم‌فاصله در نام شرکت مس', () => {
    const dbName = 'ملي‌ صنايع‌ مس‌ ايران‌';
    expect(matchFa(dbName, 'ملی مس')).toBe(true);
    expect(matchFa(dbName, 'فملی')).toBe(false);
    expect(matchFa(dbName, 'صنایع مس')).toBe(true);
  });

  it('یکدست‌سازی ارقام فارسی و انگلیسی (فملی ۲ vs فملي2)', () => {
    expect(matchFa('فملي2', 'فملی ۲')).toBe(true);
  });

  it('فیلتر دیده‌بان نماد فملي را با جستجوی فارسی فملی پیدا می‌کند', () => {
    const mockRows: MarketRow[] = [
      {
        ins_code: '35425587644337450',
        symbol: 'فملي', // ذخیره‌شده در دیتابیس با ي عربی
        name: 'ملي‌ صنايع‌ مس‌ ايران‌',
        p_closing: 6200,
        p_last: 6250,
        q_tot_tran: 1000000,
        percent_change: 2.1,
        is_live: true,
      },
      {
        ins_code: '12345',
        symbol: 'فولاد',
        name: 'فولاد مبارکه اصفهان',
        p_closing: 5100,
        is_live: true,
      }
    ];

    const result = filterWatchlist(mockRows, 'فملی');
    expect(result.length).toBe(1);
    expect(result[0].symbol).toBe('فملي');
  });
});
