// تستِ خروجیِ CSVِ «فقطِ ردیف‌های دیدنی» (Download Table) — بی‌وابستگی، RTL-safe
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { CSV_SEP, CSV_SEP_HINT, csvCell, csvFilename, csvText, toExportTable } from '@shared/lib/tableExport';
import { FtsScreenTable, screenRowCells } from '@features/fundamental/ui/FtsScreenTable';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';

/** رقمِ فارسی با chr ساخته می‌شود: ویرایشِ اسکریپتیِ رقم در متنِ فارسی رقم را می‌دزدد */
const fa = (...ds: number[]) => ds.map((d) => String.fromCharCode(0x06f0 + d)).join('');
const FA_TSEP = String.fromCharCode(0x066c);
const FA_DSEP = String.fromCharCode(0x066b);
const FA_PCT = String.fromCharCode(0x066a);
const BOM = String.fromCharCode(0xfeff);

const mk = (symbol: string, score: number): FtsScreenRow =>
  ({
    symbol,
    name: symbol,
    sector_name: 'صنعت',
    pricing_mode: 'free',
    rev_growth: 10,
    gross_margin: 20,
    sales_to_mcap: 1,
    profit_potential_pct: 30,
    eps_series: [1, 2],
    eps_last: 2,
    eps_data_gap: false,
    score,
  }) as unknown as FtsScreenRow;

/** نوعِ mock بی‌پارامتر است؛ آرگومانِ واقعی (Blob) این‌جا خوانده می‌شود */
function blobArg(spy: ReturnType<typeof vi.fn>): Blob {
  const calls = spy.mock.calls as unknown as unknown[][];
  return calls[0][0] as Blob;
}

const body = (blob: Blob) =>
  blob.text().then((t) => t.replace(BOM, '').split('\r\n').filter(Boolean));

describe('قواعدِ CSV', () => {
  it('جداکننده ویرگولِ عمودی است و خطِ اول راهنمایِ Excel', () => {
    expect(CSV_SEP).toBe(';');
    const lines = csvText({ columns: ['a', 'b'], rows: [['x', 'y']] }).split('\r\n');
    expect(lines[0]).toBe(CSV_SEP_HINT);
    expect(lines[1]).toBe('a;b');
    expect(lines[2]).toBe('x;y');
  });

  it('ارقام و جداکننده‌های فارسی عیناً می‌مانند (هیچ عددی ساخته یا یکسان‌سازی نمی‌شود)', () => {
    const vol = fa(1, 4, 8, 9) + FA_TSEP + fa(3, 0);
    const pct = '+' + fa(2, 5, 8) + FA_DSEP + fa(5, 8) + FA_PCT;
    const out = csvText({ columns: ['a', 'b'], rows: [[vol, pct]] });
    expect(out).toContain(vol + ';' + pct);
  });

  it('فاصله‌ویرگول و نقلون‌قول گارد می‌شوند؛ ویرگولِ انگلیسی تنها نه', () => {
    expect(csvCell('a;b')).toBe('"a;b"');
    expect(csvCell('a"b')).toBe('"a""b"');
    expect(csvCell('line1\nline2')).toBe('"line1\nline2"');
    expect(csvCell(' padded ')).toBe('" padded "');
    // ویرگولِ انگلیسی هم نقلون‌قول می‌گیرد: با جداکنندۀ «;» لازم نیست، ولی بی‌ضرر و
    // برایِ مصرف‌کننده‌ای که جداکننده را عوض می‌کند امن‌تر است.
    expect(csvCell('plain, text')).toBe('"plain, text"');
    expect(csvCell('')).toBe('');
  });

  it('null/undefined تهی می‌شود و طولِ ردیف با سرستون قفل می‌ماند', () => {
    const lines = csvText({ columns: ['a', 'b', 'c'], rows: [[null, undefined, 1], ['x']] }).split('\r\n');
    expect(lines[2]).toBe(';;1');
    expect(lines[3]).toBe('x;;');
    expect(csvText(toExportTable(['a', 'b'], [{ n: 1 }], (r) => [r.n, 'x', 'drop'])).split('\r\n')[2]).toBe('1;x');
  });

  it('نامِ فایل بی‌کاراکترِ ممنوعِ ویندوز و با زمانِ محلی', () => {
    expect(csvFilename('a/b:c*d', new Date(2026, 8, 30, 9, 5))).toBe('abcd-2026-09-30_09-05.csv');
  });
});

describe('دکمۀ «دانلود» در جدولِ بنیادی', () => {
  const createObjectURL = vi.fn(() => 'blob:x');
  const revokeObjectURL = vi.fn();
  vi.stubGlobal('URL', { ...globalThis.URL, createObjectURL, revokeObjectURL });
  HTMLAnchorElement.prototype.click = vi.fn();

  it('همان ردیف‌هایِ دیدنی، به همان ترتیبِ مرتب‌سازی', async () => {
    render(<FtsScreenTable rows={[mk('A', 5), mk('B', 2), mk('C', 4)]} onSelect={() => {}} />);
    const btn = screen.getByTestId('download-screen-rows');
    expect(btn.getAttribute('data-count')).toBe('3');
    fireEvent.click(btn);
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    const lines = await body(blobArg(createObjectURL));
    expect(lines).toHaveLength(5); // راهنما + سرستون + سه ردیف
    expect(lines[1].split(';')).toHaveLength(7);
    expect(lines[2].startsWith('A')).toBe(true);
    expect(lines[3].startsWith('C')).toBe(true);
    expect(lines[4].startsWith('B')).toBe(true);
    await new Promise((r) => setTimeout(r, 0));
    expect(revokeObjectURL).toHaveBeenCalled();
  });

  it('جستجو ⇒ فقطِ نتیجهٔ فیلترشده؛ بی‌نتیجه ⇒ دکمه غیرفعال', async () => {
    createObjectURL.mockClear();
    render(<FtsScreenTable rows={[mk('A', 5), mk('B', 2)]} onSelect={() => {}} />);
    fireEvent.change(screen.getAllByTestId('fts-search')[0], { target: { value: 'B' } });
    fireEvent.click(screen.getByTestId('download-screen-rows'));
    const lines = await body(blobArg(createObjectURL));
    expect(lines).toHaveLength(3);
    expect(lines[2].startsWith('B')).toBe(true);

    fireEvent.change(screen.getAllByTestId('fts-search')[0], { target: { value: 'zzz' } });
    const btn = screen.getByTestId('download-screen-rows');
    expect(btn.getAttribute('data-count')).toBe('0');
    expect(btn).toBeDisabled();
  });

  it('نگاشتِ ردیف هفت ستون دارد و «بی‌داده» را تهی نمی‌گذارد', () => {
    const cells = screenRowCells(mk('A', 5));
    expect(cells).toHaveLength(7);
    expect(cells[0]).toContain('A');
    expect(screenRowCells({ ...mk('A', 5), eps_series: [] } as unknown as FtsScreenRow)[2]).toContain('—');
  });
});
