// تستِ کاتالوگِ اندیکاتورهای FTS (مرحلۀ ۴-۵)
// کاتالوگ باید سه چیز را ثابت نگه دارد: شناسه‌ها یکتا باشند، هر سوییچِ اعلان‌شده
// واقعاً درِ PatternPrefs یا flagهایِ چارت وجود داشته باشد، و دهانۀ payloadِ
// هر سطر درِ قراردادِ Zodِ `/api/fts` زنده باشد (رجیستریِ ادعاییِ مرده نداریم).
import { describe, expect, it } from 'vitest';
import {
  CATALOG_GROUPS,
  FTS_INDICATOR_CATALOG,
  catalogEntry,
  catalogForGroup,
} from '@features/technical/lib/ftsIndicatorCatalog';
import { PATTERN_PREFS_DEFAULT } from '@features/technical/lib/patternOverlays';
import { FtsAnalysis } from '@features/technical/api/useFtsAnalysis';

describe('کاتالوگِ اندیکاتور FTS', () => {
  it('شناسه‌ها یکتا و گروه‌ها ثبت‌شدده‌اند', () => {
    const ids = FTS_INDICATOR_CATALOG.map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const e of FTS_INDICATOR_CATALOG) {
      expect(CATALOG_GROUPS[e.group]).toBeTruthy();
    }
  });

  it('هر toggleِ اعلامی یا کلیدِ PatternPrefs است یا flagِ شناخته‌شده', () => {
    const FLAGS = new Set(['showFibLevels', 'showHistoryEvents', 'showCorporateActions']);
    for (const e of FTS_INDICATOR_CATALOG) {
      if (e.toggle === null) continue;
      const isPref = e.toggle in PATTERN_PREFS_DEFAULT;
      const isFlag = FLAGS.has(e.toggle);
      expect(isPref || isFlag, `${e.id} → ${String(e.toggle)}`).toBe(true);
    }
  });

  it('ریشۀ دهانۀ هر سطر درِ قراردادِ payload هست (رجیستریِ ادعایِ مرده ندارد)', () => {
    const shape = FtsAnalysis.shape as Record<string, unknown>;
    for (const e of FTS_INDICATOR_CATALOG) {
      if (!e.source.startsWith('(')) {
        const root = e.source.split('.')[0];
        expect(shape[root], `${e.id} → source=${e.source}`).toBeTruthy();
      }
    }
  });

  it('ستارۀ ساختار و پولبک درِ هر دو موتور رسم می‌شوند (دورِ مأموریت)', () => {
    expect(catalogEntry('structure-points')?.engines).toEqual({ klinecharts: true, ffc: true });
    expect(catalogEntry('pullback')?.engines).toEqual({ klinecharts: true, ffc: true });
  });

  it('گروه‌بندیِ legend کامل است: حداقل یک لایه در هر گروه غیر از پنل', () => {
    for (const g of Object.keys(CATALOG_GROUPS) as (keyof typeof CATALOG_GROUPS)[]) {
      const list = catalogForGroup(g);
      expect(list.length, g).toBeGreaterThan(0);
    }
  });
});
