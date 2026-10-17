// shared/components/ExportRowsControl.tsx — دامنه + ستون + دو فرمت، در یک نوارِ باریک
//
// الگو از `DownloadRowsButton` می‌آید (عرضِ ثابت ⇒ عوض‌شدنِ متنِ خطا layout shift
// نمی‌سازد؛ صفرِ ردیف ⇒ غیرفعال نه فایلِ خالی). دو چیز اضافه شد: **دامنه** و
// **Excel**. Excel سمتِ سرور ساخته می‌شود (`POST /api/export` با openpyxl) چون
// سلول باید *عددِ واقعی* باشد و کتابخانۀ جدید برایِ این کار درِ پروژه مجاز نیست؛
// CSV سمتِ کلاینت می‌ماند چون «آنچه می‌بینی همان است که دانلود می‌شود» فقط اینجا
// معلوم است (فیلتر + انتخابِ ردیف‌ها).
import { useCallback, useRef, useState } from 'react';
import { httpBlob } from '@shared/api/http';
import { toFaDigits } from '@shared/lib/fmt';
import { downloadCsvWithMeta, saveBlob, stampedName, type ExportTable } from '@shared/lib/tableExport';

export type ExportMeta = readonly (readonly [string, string])[];
export type ExportTableWithMeta = ExportTable & { meta?: ExportMeta };
export type ExportChoice<T extends string> = { id: T; label: string; count: number; hint?: string };

const BTN = 'inline-flex min-w-[68px] shrink-0 items-center justify-center gap-1 rounded-lg border px-2 py-1 '
  + 'text-2xs font-bold transition-colors';
const IDLE = 'border-border-c/70 bg-bg-card/60 text-text-secondary hover:border-accent-green hover:text-accent-green';
const BUSY = 'border-border-c/70 bg-bg-card/40 text-text-muted cursor-wait';
const BAD = 'border-accent-red/50 bg-accent-red/10 text-accent-red';
const SELECT = 'rounded-lg border border-border-c bg-bg-card px-1.5 py-1 text-2xs font-bold text-text-secondary outline-none';

export function ExportRowsControl<T extends string, C extends string>({
  base,
  scope,
  scopes,
  onScope,
  colset,
  colsets,
  onColset,
  getTable,
  testId = 'export-rows-control',
}: {
  /** پیشوندِ نامِ فایل — نامِ خودِ جدول، نه «export» */
  base: string;
  scope: T;
  scopes: ExportChoice<T>[];
  onScope: (v: T) => void;
  colset: C;
  colsets: ExportChoice<C>[];
  onColset: (v: C) => void;
  /** دقیقاً لحظۀ کلیک خوانده می‌شود تا خروجی از فیدِ روی‌صفحه عقب نماند */
  getTable: () => ExportTableWithMeta;
  testId?: string;
}) {
  const [busy, setBusy] = useState<'csv' | 'xlsx' | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fail = useCallback((m: string) => {
    setErr(m);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setErr(null), 4000);
  }, []);

  const current = scopes.find((s) => s.id === scope);
  const disabled = (current?.count ?? 0) === 0;

  const onCsv = useCallback(() => {
    setBusy('csv');
    try {
      const t = getTable();
      downloadCsvWithMeta(base, { columns: t.columns, rows: t.rows }, t.meta ?? []);
      setErr(null);
    } catch {
      fail('CSV ساخته نشد');
    } finally {
      setBusy(null);
    }
  }, [base, fail, getTable]);

  const onXlsx = useCallback(async () => {
    setBusy('xlsx');
    try {
      const t = getTable();
      const rows = [[...t.columns], ...t.rows.map((r) => [...r])];
      const reply = await httpBlob('/api/export', {
        fmt: 'xlsx',
        title: base,
        rows,
        meta: (t.meta ?? []).map(([k, v]) => [k, v]),
      });
      saveBlob(reply.blob, reply.filename ?? `${stampedName(base)}.xlsx`);
      setErr(null);
    } catch (e) {
      fail(e instanceof Error && e.message.includes('413') ? 'خروجی از سقفِ سرور بزرگ‌تر است' : 'Excel ساخته نشد');
    } finally {
      setBusy(null);
    }
  }, [base, fail, getTable]);

  return (
    <div
      className="flex min-w-0 flex-wrap items-center gap-1.5"
      data-testid={testId}
      data-scope={scope}
      data-colset={colset}
      data-count={current?.count ?? 0}
    >
      <label className="flex items-center gap-1 text-3xs text-text-muted" title={current?.hint}>
        دامنه
        <select
          className={SELECT}
          data-testid={`${testId}-scope`}
          value={scope}
          onChange={(e) => onScope(e.target.value as T)}
        >
          {scopes.map((s) => (
            <option key={s.id} value={s.id}>{s.label} ({toFaDigits(s.count)})</option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-1 text-3xs text-text-muted">
        ستون‌ها
        <select
          className={SELECT}
          data-testid={`${testId}-colset`}
          value={colset}
          onChange={(e) => onColset(e.target.value as C)}
        >
          {colsets.map((c) => (
            <option key={c.id} value={c.id}>{c.label}</option>
          ))}
        </select>
      </label>
      <button
        type="button"
        onClick={onCsv}
        disabled={disabled || busy !== null}
        data-testid={`${testId}-csv`}
        aria-label="دانلود CSV"
        className={`${BTN} ${busy === 'csv' ? BUSY : err && err.includes('CSV') ? BAD : IDLE}`}
      >
        CSV
      </button>
      <button
        type="button"
        onClick={onXlsx}
        disabled={disabled || busy !== null}
        data-testid={`${testId}-xlsx`}
        aria-label="دانلود Excel"
        className={`${BTN} ${busy === 'xlsx' ? BUSY : err && err.includes('Excel') ? BAD : IDLE}`}
      >
        Excel
      </button>
      {err ? <span className="text-3xs text-accent-red" data-testid={`${testId}-error`}>{err}</span> : null}
    </div>
  );
}
