// src/__tests__/watch-export.spec.tsx — گاردِ خروجیِ دیدهبان (مرحلۀ ۸ مأموریت)
//
// پنج چیز که باید ثابت بمانند، چون رابطِ دیگری نمی‌تواند جلوی‌شان را بگیرد:
//  ۱) هر سرستونِ دیدنیِ جدول درِ خروجی هست (ستونی به‌خاطرِ دشواریِ mapping حذف
//     نمی‌شود) — با متنِ `<th>`هایِ رندرشدۀ خودِ `WatchTable`.
//  ۲) عدد، عدد است و نبودِ داده `null` — نه صفر، نه «۱٬۲۳۴»ِ فارسی.
//  ۳) دامنه‌ها واقعی‌اند: انتخاب‌شده ⊂ فیلترشده ⊂ کلِ دیدهبان، و «کل» یعنی هر
//     ۶۰ نمادِ فهرستِ رصد، بی‌بریدگیِ پنهانی (این جدول صفحه‌بندی ندارد).
//  ۴) واحد درِ سرستون نوشته شده (ریال/تومان/٪/سهم/نفر).
//  ۵) ردپایِ منشأ و زمانِ snapshot درِ فایل هست و هیچ رازِ نشستی جا نمی‌شود.
import path from 'node:path';
import { readFileSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render } from '@testing-library/react';
import { ExportRowsControl } from '@shared/components/ExportRowsControl';
import {
  COLSET_LABEL, TABLE_HEADER_ALIAS, WATCH_COLUMNS, buildWatchTable, columnsFor,
  scopeCount, scopeItems, toExportRows, type WatchExportItem,
} from '@features/portfolio/lib/watchExport';
import { csvFilename, csvText, csvTextWithMeta } from '@shared/lib/tableExport';
import type { MarketRow } from '@shared/types/marketRow';
import { normalizeFa } from '@shared/lib/normalizeFa';

// دانلودِ واقعی درِ jsdom نشدنی است (URL.createObjectURL پیاده‌سازی نشده)؛ آنچه
// می‌سنجیم «چه بلابی با چه نامی» ساخته می‌شود، نه این‌که مرورگر آن را رویِ دیسک
// می‌ریزد — آن درِ چکِ زندۀ مرورگر ثابت می‌شود.
const blobs: Blob[] = [];
const names: string[] = [];
const httpBlobMock = vi.fn();
vi.mock('@shared/api/http', () => ({
  httpBlob: (...a: unknown[]) => httpBlobMock(...a),
  HttpError: class extends Error {},
}));

const U = URL as unknown as { createObjectURL?: unknown; revokeObjectURL?: unknown };
const A = HTMLAnchorElement.prototype as unknown as { click?: unknown };
const saved = { create: U.createObjectURL, revoke: U.revokeObjectURL, click: A.click };

beforeEach(() => {
  blobs.length = 0;
  names.length = 0;
  httpBlobMock.mockReset();
  U.createObjectURL = (b: unknown) => { blobs.push(b as Blob); return 'blob:mock'; };
  U.revokeObjectURL = () => {};
  A.click = function (this: HTMLAnchorElement) { names.push(this.download); };
});
afterEach(() => {
  U.createObjectURL = saved.create;
  U.revokeObjectURL = saved.revoke;
  A.click = saved.click;
});

const TABLE_SRC = readFileSync(
  path.resolve(import.meta.dirname, '../features/portfolio/components/WatchTable.tsx'), 'utf8');

/** متنِ `<th>`هایِ خودِ جدول — همان چیزی که کاربر می‌بیند. */
function tableHeaders(): string[] {
  return [...TABLE_SRC.matchAll(/<th className=[^>]*>([^<{]+)<\/th>/g)].map((m) => m[1].trim());
}

const row = (over: Partial<MarketRow> = {}): MarketRow => ({
  symbol: 'فولاد',
  name: 'فولاد مبارکه اصفهان',
  ins_code: '46348559193224090',
  sector_name: 'فلزات اساسی',
  p_last: 4540,
  p_closing: 4540,
  p_first: 4280,
  p_max: 4540,
  p_min: 4280,
  percent_change: 2.95,
  q_tot_tran: 1479239170,
  z_tot_tran: 12438,
  q_tot_cap: 6715745831800,
  mcap: 8784900000000000,
  buy_q1_vol: 2619286667,
  buy_q1_px: 4540,
  sell_q1_px: 0,
  sell_q1_vol: 0,
  row_h: 124530,
  ...over,
} as unknown) as MarketRow;

const item = (symbol: string, r: MarketRow | null): WatchExportItem =>
  ({ symbol, row: r ? { ...r, symbol } : null });

const build = (items: WatchExportItem[], o: Partial<Parameters<typeof buildWatchTable>[0]> = {}) =>
  buildWatchTable({
    items, scope: 'all', selected: new Set<string>(), query: '', colset: 'full',
    cfg: null, exportedAt: '2026-10-14 13:20',
    meta: [['منبع داده', 'TSETMC GetMarketWatch'], ['زمانِ گرفتنِ خروجی', '2026-10-14 13:20']],
    ...o,
  });

describe('خروجیِ دیدهبان — سرستون‌ها', () => {
  it('هر سرستونِ دیدنیِ جدول نگاشتِ خروجی دارد (چیزِ حذف‌شده‌ای نیست)', () => {
    const seen = tableHeaders();
    expect(seen.length).toBeGreaterThanOrEqual(16);
    const unmapped = seen.filter((h) => !Object.hasOwn(TABLE_HEADER_ALIAS, h));
    // «کندل روز» به چهار قیمت می‌شکند و «حذف» اکشن است، نه داده
    expect(unmapped.sort()).toEqual(['حذف', 'کندل روز'].sort());
  });

  it('هر کلیدِ TABLE_HEADER_ALIAS هم ستونی درِ دستۀ دیدنی و هم همان متنِ جدول است', () => {
    const board = new Map(columnsFor('board').map((c) => [c.key, c.label]));
    const seen = new Set(tableHeaders());
    for (const [header, key] of Object.entries(TABLE_HEADER_ALIAS)) {
      expect(seen.has(header), `سرستونِ «${header}» دیگر درِ جدول رندر نمی‌شود`).toBe(true);
      expect(board.has(key), `ستونِ خروجیِ «${key}» درِ دستۀ board نیست`).toBe(true);
    }
  });

  it('کندلِ روز به چهار قیمتِ سازندهٔ خودش می‌شکند، نه یکِ رشتهٔ توصیفی', () => {
    const labels = columnsFor('board').map((c) => c.label);
    for (const need of ['اولین قیمت (ریال)', 'بیشترین قیمتِ معامله‌شده (ریال)',
      'کمترین قیمتِ معامله‌شده (ریال)', 'آخرین معامله (ریال)']) {
      expect(labels, need).toContain(need);
    }
  });

  it('دستۀ «full» همان board به‌علاوهٔ شناسه، تفکیکِ حقیقی/حقوقی و ردپاست', () => {
    const full = new Set(columnsFor('full').map((c) => c.label));
    for (const c of columnsFor('board')) expect(full.has(c.label), c.label).toBe(true);
    for (const need of ['سهم حقیقی از ارزش خرید (٪)', 'سرانه خرید (سهم به ازای هر نفر)',
      'شناسۀ پایدار (insCode)', 'منبع ارزش بازار', 'زمانِ گرفتنِ خروجی', 'منبع داده']) {
      expect(full.has(need), need).toBe(true);
    }
    expect(Object.keys(COLSET_LABEL).sort()).toEqual(['board', 'full']);
  });

  it('واحد درِ سرستون هست — ریال، میلیارد ریال، میلیارد تومان، ٪، سهم، نفر مبهم نمی‌مانند', () => {
    const TEXT_KEYS = new Set(['symbol', 'name', 'ins_code', 'sector', 'board', 'in_feed', 'status',
      'st_title', 'badges', 'tech', 'fund', 'mcap_src', 'pct_basis', 'ctv_kind', 'is_live',
      'source', 'exported_at', 'row_h', 'pct_is_current']);
    for (const c of WATCH_COLUMNS) {
      if (TEXT_KEYS.has(c.key)) continue;
      const hasUnit = /ریال|میلیارد|٪|سهم|نفر|سفارش|عدد|برابر|YYYYMMDD|P\/E|بورس|بی‌واحد/.test(c.label);
      expect(hasUnit, c.label).toBe(true);
    }
  });
});

describe('خروجیِ دیدهبان — تایپِ مقدار', () => {
  it('عددها عدد می‌مانند (برایِ Excel)، نه رشتهٔ فارسیِ قالب‌بندی‌شده', () => {
    const t = build([item('فولاد', row())]);
    expect(t.rows[0][t.columns.indexOf('حجم (سهم)')]).toBe(1479239170);
    expect(t.rows[0][t.columns.indexOf('ارزش بازار (ریال)')]).toBe(8784900000000000);
    expect(t.rows[0][t.columns.indexOf('ارزش بازار (میلیارد تومان)')]).toBe(878490);
    expect(t.rows[0][t.columns.indexOf('ارزش معاملات (میلیارد ریال)')]).toBeCloseTo(6715.7458318, 6);
  });

  it('صفرِ واقعیِ تابلو با «بی‌داده» یکی نمی‌شود', () => {
    const t = build([item('فولاد', row())]);
    expect(t.rows[0][t.columns.indexOf('قیمت صف اول فروش (ریال)')]).toBe(0);
    const g = build([item('نامعلوم', null)]);
    expect(g.rows[0][g.columns.indexOf('قیمت صف اول فروش (ریال)')]).toBeNull();
    expect(g.rows[0][g.columns.indexOf('در فیدِ تابلو؟')]).toBe('نیست');
  });

  it('هیچ خانۀ بی‌داده‌ای صفر نمی‌شود (ردیفِ بی‌فید کامل null است)', () => {
    const g = build([item('نامعلوم', null)]);
    for (const label of ['حجم (سهم)', 'تعداد معاملات (عدد)', 'آخرین معامله (ریال)', 'ارزش بازار (ریال)',
      'تغییر پایانی (٪)', 'قیمت صف اول خرید (ریال)']) {
      expect(g.rows[0][g.columns.indexOf(label)], label).toBeNull();
    }
    // وضعیتِ بی‌ردیف رشتهٔ «بی‌ردیف» است، نه صفر و نه خالی
    expect(g.rows[0][g.columns.indexOf('وضعیت معاملاتی')]).toBe('بی‌ردیف');
  });

  it('صفرِ سه خانۀ بازۀ روز «قیمت» نیست: درِ فایل تهی می‌ماند', () => {
    // تابلو تا پیش از مبادله (یا تا پیش از نهایۀ منبع) `pf/pmx/pmn = 0` می‌فرستد؛
    // سنجشِ ۱۴۰۵-۰۷-۲۲: ۱٬۳۴۰ و ۱٬۳۶۳ ردیفِ صفر در همین نشست.
    const z = build([item('خاور', row({ q_tot_tran: 0, p_first: 0, p_max: 0, p_min: 0 }))]);
    for (const label of ['اولین قیمت (ریال)', 'بیشترین قیمتِ معامله‌شده (ریال)', 'کمترین قیمتِ معامله‌شده (ریال)']) {
      expect(z.rows[0][z.columns.indexOf(label)], label).toBeNull();
    }
    // و قیمتِ پایانیِ معتبر دست‌نخورده می‌ماند (صفرِ آن معنا ندارد، ولی اینجا عدد است)
    expect(z.rows[0][z.columns.indexOf('قیمت پایانی (ریال)')]).toBe(4540);
  });

  it('ساعتِ ردیف به HH:MMِ لاتین می‌نشیند تا درِ Excel قابلِ مرتب‌سازی بماند', () => {
    const t = build([item('فولاد', row())]);
    expect(t.rows[0][t.columns.indexOf('ساعتِ خودِ ردیف (HH:MM)')]).toBe('12:45');
  });

  it('درصدِ نشستِ پیشین به‌عنوانِ درصدِ امروز جا نمی‌زند (ctv_d + پرچمِ تازگی)', () => {
    const t = build([item('فولاد', row({ ctv_d: 20261013, pct_is_current: 0, retail_buy_pct: 89.6 }))]);
    expect(t.rows[0][t.columns.indexOf('نشستِ عددِ درصد (YYYYMMDD)')]).toBe(20261013);
    expect(t.rows[0][t.columns.indexOf('درصد از نشستِ خودِ تابلو؟')]).toBe('نیست');
    expect(t.rows[0][t.columns.indexOf('سهم حقیقی از ارزش خرید (٪)')]).toBe(89.6);
  });

  it('منبع ارزش بازار و P/E هم درِ فایل هستند (شاخص ۴ قابلِ ردیابی)', () => {
    const t = build([item('فولاد', row({ mcap_src: 'tse_board_calc', pe: 8.8 }))]);
    expect(t.rows[0][t.columns.indexOf('منبع ارزش بازار')]).toBe('tse_board_calc');
    expect(t.rows[0][t.columns.indexOf('P/E')]).toBe(8.8);
  });
});

describe('خروجیِ دیدهبان — دامنه‌ها', () => {
  const many = Array.from({ length: 60 }, (_, i) => item(`نماد${i}`, row({ p_last: 100 + i })));

  it('«کلِ دیدهبان» هر ۶۰ ردیف را می‌دهد، حتی وقتی فیلتر روشن است', () => {
    expect(scopeItems(many, 'visible', new Set<string>(), 'نماد1').length).toBe(11);
    expect(build(many, { query: 'نماد1', scope: 'all' }).rows.length).toBe(60);
  });

  it('«نتایجِ فیلترشده» فقط دیدنی‌ها، و «انتخاب‌شده» زیرمجموعۀ همان است', () => {
    const sel = new Set(['نماد1', 'نماد12'].map(normalizeFa));
    const vis = scopeItems(many, 'visible', sel, 'نماد1');
    const picks = scopeItems(many, 'selected', sel, 'نماد1');
    expect(vis.length).toBe(11);
    expect(picks.map((p) => p.symbol)).toEqual(['نماد1', 'نماد12']);
    for (const p of picks) expect(vis).toContainEqual(p);
  });

  it('انتخابِ خالی با دامنهٔ «انتخاب‌شده» = صفر ردیف (نه فایلِ کامل)', () => {
    expect(scopeItems(many, 'selected', new Set<string>(), '').length).toBe(0);
    expect(scopeCount(many, 'selected', new Set<string>(), '').shown).toBe(0);
    expect(scopeCount(many, 'all', new Set<string>(), '').total).toBe(60);
  });

  it('فیلتر با نامِ شرکت هم کار می‌کند (نامِ فارسی درِ همان ستون است)', () => {
    const its = [item('فولاد', row()), item('خودرو', row({ symbol: 'خودرو', name: 'خودرو سازان' }))];
    expect(scopeItems(its, 'visible', new Set<string>(), 'سازان').map((i) => i.symbol)).toEqual(['خودرو']);
  });
});

describe('خروجیِ دیدهبان — CSV و ردپا', () => {
  it('CSV با sep=; باز می‌شود و سرستون‌هایِ فارسی می‌مانند', () => {
    const t = build([item('فولاد', row())], { colset: 'board' });
    const text = csvText(t);
    expect(text.startsWith('sep=;')).toBe(true);
    expect(text).toContain('آخرین معامله (ریال)');
    expect(text.trim().split('\r\n').length).toBe(3);   // sep= + سرِ ستون + یکِ ردیف
    expect(text.charCodeAt(0)).not.toBe(0xfeff);        // BOM کارِ saveBlob است، نه csvText
  });

  it('ردپا بعد از جدول می‌آید و ردیف‌هایِ داده را دست نمی‌دهد', () => {
    const t = build([item('فولاد', row())]);
    const text = csvTextWithMeta(t, t.meta);
    const dataLines = text.trim().split('\r\n').filter((l) => l !== '' && !l.startsWith('#'));
    // sep= + سرِ ستون + ردیف‌هایِ داده — ردپا هیچ‌کدام را زیاد یا کم نمی‌کند
    expect(dataLines.length).toBe(t.rows.length + 2);
    expect(text).toContain('# منبع داده');
    expect(text).toContain('# زمانِ گرفتنِ خروجی');
  });

  it('نامِ فایل برچسبِ جدول + تاریخ/زمان دارد و کاراکترِ ممنوعِ ویندوز نمی‌گیرد', () => {
    expect(csvFilename('دیدهبان-بازار/تابلو', new Date(2026, 9, 14, 13, 20)))
      .toBe('دیدهبان-بازارتابلو-2026-10-14_13-20.csv');
  });

  it('payloadِ Excel سطرِ سرِ ستون + دادهٔ تایپ‌شده + meta است', () => {
    const t = build([item('فولاد', row())], { colset: 'board' });
    const rows = toExportRows(t);
    expect(rows.length).toBe(t.rows.length + 1);
    expect([...rows[0]]).toEqual([...t.columns]);
    expect(typeof rows[1][rows[0].indexOf('حجم (سهم)')]).toBe('number');
    expect(t.meta.length).toBeGreaterThan(0);
  });

  it('هیچ نشان، رمز یا شناسۀ نشستِ کاربر درِ توصیفِ ستون‌ها جا نمی‌شود', () => {
    const joined = WATCH_COLUMNS.map((c) => `${c.key} ${c.label}`).join('\n').toLowerCase();
    for (const forbidden of ['token', 'cookie', 'password', 'secret', 'session_id', 'authorization', 'apikey']) {
      expect(joined, forbidden).not.toContain(forbidden);
    }
  });
});

describe('کنترلِ خروجی — مسیرِ واقعیِ دانلود', () => {
  const scopes = [
    { id: 'selected', label: 'انتخابی', count: 0 },
    { id: 'all', label: 'کل', count: 2 },
  ] as const;
  const colsets = [
    { id: 'board', label: 'دیدنی', count: 0 },
    { id: 'full', label: 'همه', count: 0 },
  ] as const;
  const twoRows = () =>
    build([item('فولاد', row()), item('همراه', row({ symbol: 'همراه' }))], { colset: 'board' });
  const control = () => (
    <ExportRowsControl
      base="دیدهبان-بازار"
      scope="all" onScope={() => {}}
      colset="board" onColset={() => {}}
      getTable={twoRows}
      scopes={scopes.map((s) => ({ ...s }))}
      colsets={colsets.map((c) => ({ ...c }))}
      testId="ctl"
    />
  );

  it('CSV همان جدولِ دامنه‌شده را با BOM و نامِ stamped بیرون می‌دهد', async () => {
    const { getByTestId } = render(control());
    fireEvent.click(getByTestId('ctl-csv'));
    expect(blobs.length).toBe(1);
    const bytes = new Uint8Array(await blobs[0].arrayBuffer());
    // Excelِ فارسی بی‌BOMِ UTF-8 یونیکد را می‌سوزاند — و text() آن را می‌بلعد،
    // پس چیزی که می‌سنجیم بایتِ اولِ فایل است نه رشتهٔ دیکدشده.
    expect([...bytes.slice(0, 3)]).toEqual([0xef, 0xbb, 0xbf]);
    const csv = await blobs[0].text();
    expect(csv.startsWith('sep=;')).toBe(true);
    expect(names[0]).toMatch(/^دیدهبان-بازار-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.csv$/);
    expect(blobs[0].type).toBe('text/csv;charset=utf-8');
  });

  it('Excel با POSTِ عددی به /api/export می‌رود و نامِ سرور را نگه می‌دارد', async () => {
    httpBlobMock.mockResolvedValue({ blob: new Blob(['xlsx-mock']), filename: 'دیدهبان-بازار.xlsx' });
    const { getByTestId } = render(control());
    fireEvent.click(getByTestId('ctl-xlsx'));
    await vi.waitFor(() => expect(httpBlobMock).toHaveBeenCalledTimes(1));
    const [url, body] = httpBlobMock.mock.calls[0] as [string, Record<string, unknown>];
    expect(url).toBe('/api/export');
    expect(body.fmt).toBe('xlsx');
    expect(body.title).toBe('دیدهبان-بازار');
    const rows = body.rows as (readonly unknown[])[];
    expect(rows.length).toBe(3);                       // سرِ ستون + دو ردیفِ دیدهبان
    expect(typeof rows[1][(rows[0] as string[]).indexOf('حجم (سهم)')]).toBe('number');
    expect((body.meta as unknown[][]).length).toBeGreaterThan(0);
    await vi.waitFor(() => expect(names.length).toBe(1));
    expect(names[0]).toBe('دیدهبان-بازار.xlsx');
  });

  it('سرریزِ پاسخِ سرور ⇒ متنِ خطا درِ همان جایِ ثابت (بی‌layout shift)', async () => {
    httpBlobMock.mockRejectedValue(new Error('boom'));
    const { getByTestId, findByTestId } = render(control());
    fireEvent.click(getByTestId('ctl-xlsx'));
    const msg = await findByTestId('ctl-error');
    expect(msg.textContent).toContain('Excel');
    expect(getByTestId('ctl-xlsx')).not.toBeDisabled();  // خطا دکمه را نمی‌کُشد
  });

  it('دامنۀ خالی ⇒ دکمه‌ها غیرفعال‌اند، نه فایلِ خالی', () => {
    const { getByTestId } = render(
      <ExportRowsControl
        base="دیدهبان-بازار"
        scope="selected" onScope={() => {}}
        colset="board" onColset={() => {}}
        getTable={() => build([])}
        scopes={[{ id: 'selected', label: 'انتخابی', count: 0 }]}
        colsets={[{ id: 'board', label: 'دیدنی', count: 0 }]}
        testId="ctl0"
      />,
    );
    expect(getByTestId('ctl0-csv')).toBeDisabled();
    expect(getByTestId('ctl0-xlsx')).toBeDisabled();
  });
});
