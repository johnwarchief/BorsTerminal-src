// src/__tests__/route-title-guard.spec.ts — هرِ مقصد باید عنوانِ خودش را داشته باشد
//
// چرا: نوارِ بالا برایِ نشانیِ بی‌ثبت رویِ «ترمینال بورس» می‌ماند. سه مقصد
// (/sarkhati، /notifications، /engine-lab) دقیقاً همین نقص را داشتند — صفحه
// باز می‌شد وِ هیچ‌جا نوشته نبود کدامِ صفحه است. اینِ گاردِ جدول را ازِ خودِ
// routeها می‌خواند، پسِ مقصدِ تازه بی‌عنوان نمی‌تواند بی‌صدا وارد شود.
import { describe, expect, it } from 'vitest';
import { mainRoutes } from '../routes';
import { TITLES } from '@app/components/Topbar';

const SKIP = new Set(['', '*']);

describe('عنوانِ هر مقصد', () => {
  it('هر route درِ TITLES نشانیِ ثبت‌شده دارد', () => {
    const paths = mainRoutes
      .map((r) => String(r.path ?? '').split('/')[0])
      .filter((p) => !SKIP.has(p));
    expect(paths.length).toBeGreaterThan(6);
    const missing = paths.filter((p) => !(`/` + p in TITLES || p in TITLES));
    expect(missing, `بی‌عنوان: ${missing.join('، ')}`).toEqual([]);
  });

  it('هیچِ عنوانی بی‌مقصد نمانده (دفترِ دروغین نباشد)', () => {
    const paths = new Set(mainRoutes
      .map((r) => String(r.path ?? '').split('/')[0])
      .filter((p) => !SKIP.has(p)));
    const stale = Object.keys(TITLES)
      .map((k) => k.replace(/^\//, ''))
      .filter((k) => !paths.has(k));
    expect(stale, `درِ TITLES ولی نه درِ routeها: ${stale.join('، ')}`).toEqual([]);
  });
});
