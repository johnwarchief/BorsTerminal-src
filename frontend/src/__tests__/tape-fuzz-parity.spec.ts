// __tests__/tape-fuzz-parity.spec.ts -- برابریِ تفاضلیِ پنج فیلتر با مرجعِ پایتون
//
// سنجشِ زنده رویِ یک اسنپ‌شات (۱۴۰۵-۰۷-۰۷) ثابت کرد چیپ = بج = فیلترنویسِ سایت.
// آن یک اسنپ‌شات بود؛ «وقتی بازار باز است و اعداد هی عوض می‌شوند» یعنی هزاران
// حالتِ میانی که هیچ‌کدام درِ آن ساعت دیده نمی‌شوند. این‌جا همان ردیف‌هایِ واقعی
// با ضریب‌هایِ تعیین‌شده به‌هم ریخته‌اند (tools/tape_parity_fuzz.py) و پنج پرچم
// دو بار خوانده می‌شود: tape_flags.py (مرجعِ عینِ ExecFilterِ سایت) و
// tapeFilterVerdict() درِ فرانت. اختلافِ این‌جا همان اختلافی است که فردا صبح
// درِ تابلو دیده می‌شود.
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { DEFAULT_TAPE_FILTER_CONFIG, tapeFilterVerdict } from '@features/market/lib/tapeAlgorithms';

const FLAGS = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh'] as const;

type Corpus = {
  seed: number;
  count: number;
  rows: Record<string, string | number | boolean | null>[];
  expected: Record<(typeof FLAGS)[number], boolean[]>;
};

// کورپوس از /api/marketِ زنده رویِ PC ساخته می‌شود (tools/tape_parity_fuzz.py) و
// `_audit/*.json` عمداً در گیت نیست؛ پس این گیتِ PC است، نه CI. بی‌کورپوس صریح
// skip می‌شود تا «اجرا نشد» با «سبز شد» قاطی نشود — نه اینکه ادعا حذف شود.
const CORPUS_PATH = resolve(process.cwd(), '../_audit/tape_parity_fuzz.json');
const hasCorpus = existsSync(CORPUS_PATH);
if (!hasCorpus) {
  console.warn(`[tape-fuzz-parity] SKIPPED — corpus نیست (${CORPUS_PATH}); `
    + 'بساز: python tools/tape_parity_fuzz.py --rows 140 --out _audit/tape_parity_fuzz.json');
}
const corpus: Corpus = hasCorpus
  ? (JSON.parse(readFileSync(CORPUS_PATH, 'utf8')) as Corpus)
  : { seed: 0, count: 0, rows: [], expected: {} as Corpus['expected'] };

describe.skipIf(!hasCorpus)('برابریِ تفاضلیِ پنج فیلترِ تابلو', () => {
  it('هیچ حالتی از ۷۳۲ حالتِ به‌هم‌ریخته میانِ فرانت و مرجعِ پایتون فرق نمی‌کند', () => {
    const diffs: string[] = [];
    corpus.rows.forEach((row, i) => {
      for (const f of FLAGS) {
        const got = tapeFilterVerdict(row as unknown as MarketRow, f, DEFAULT_TAPE_FILTER_CONFIG);
        if (got !== corpus.expected[f][i]) {
          diffs.push(`#${i} ${f}: frontend=${got} python=${corpus.expected[f][i]} symbol=${String(row.symbol ?? '')}`);
        }
      }
    });
    expect(diffs.slice(0, 10)).toEqual([]);
    expect(diffs).toHaveLength(0);
  });

  // بدیهی‌سازی: اگر خدای‌نکرده مرجع همه را false بدهد، آزمونِ بالا سبزِ دروغین
  // می‌شود. پس هر پنج پرچم باید درِ بدنه آزمون دستِ‌کم یک «آری» داشته باشد.
  it('بدنۀ آزمون برای هر پنج فیلد مثبت دارد (سبزِ بی‌محتوا ممنوع)', () => {
    expect(corpus.count).toBeGreaterThan(500);
    for (const f of FLAGS) {
      expect(corpus.expected[f].filter(Boolean).length).toBeGreaterThan(5);
    }
  });
});
