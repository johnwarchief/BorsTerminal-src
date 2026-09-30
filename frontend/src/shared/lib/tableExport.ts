// shared/lib/tableExport.ts -- خروجیِ CSV از **فقطِ ردیف‌های دیدۀ** یک جدول
// چرا سمتِ کلاینت: «آنچه می‌بینی همان است که دانلود می‌شود» تنها درِ فرانت معلوم
// است (فیلتر + جستجو + مرتب‌سازی + دامنهٔ نوعِ دارایی همه اینجا نشسته‌اند)؛ POST
// /api/export همان ردیف‌ها را به سرور می‌فرستد تا برگرداند — بی‌هیچ ارزشِ افزوده.
// بی‌وابستگی: یک رشته + Blob. رقم‌ها همان چیزی است که کاربر می‌بیند (فارسی)،
// چون منبعش همین سلول‌های رندرشدگی‌اند؛ هیچ عددِ تازه‌ای ساخته نمی‌شود.
// جداکننده: ویرگولِ عمودی + خطِ راهنمایِ sep برای Excelِ فارسی (رأیِ pilot: C،
// اطمینان ۰٫۲۷، ریسک ۰٫۲۷ — گزینهٔ «ویرگولِ معمولی» ۰٫۰۴ رد شد).

export type ExportCell = string | number | null | undefined;

export type ExportTable = {
  columns: readonly string[];
  rows: readonly (readonly ExportCell[])[];
};

export const CSV_SEP = ';';
/** راهنمایِ Excel: با این خط، جداکننده فرقی با تنظیماتِ سامانه نمی‌کند */
export const CSV_SEP_HINT = `sep=${CSV_SEP}`;

/** همان قاعدهٔ RFC 4180، فقط با جداکنندهٔ عوض‌شده */
export function csvCell(v: ExportCell): string {
  const s = v == null ? '' : String(v);
  return /[",;\n\r]/.test(s) || s !== s.trim() ? `"${s.replace(/"/g, '""')}"` : s;
}

export function csvText(table: ExportTable): string {  const lines = [CSV_SEP_HINT, table.columns.map(csvCell).join(CSV_SEP)];
  for (const r of table.rows) {
    const row = [...r];
    while (row.length < table.columns.length) row.push('');
    lines.push(row.slice(0, table.columns.length).map(csvCell).join(CSV_SEP));
  }
  return lines.join('\r\n') + '\r\n';
}

/** سرِ جدولِ خروجی از همان سرستون‌هایِ خودِ جدول + نگاشتِ هر ردیف به سلول‌هایِ
 *  متنی‌اش. ستون‌ها در یک جا تعریف می‌مانند (COLS/HEADERSِ کامپوننت) تا فهرستِ
 *  دومِ سرستون‌ها ساخته نشود. */
export function toExportTable<T>(
  columns: readonly string[],
  rows: readonly T[],
  cells: (row: T) => readonly ExportCell[],
): ExportTable {
  return { columns, rows: rows.map(cells) };
}

/** BOM + متن — بی BOM، Excelِ فارسی یونیکد را می‌سوزاند */
export function csvBlobParts(text: string): BlobPart[] {
  return ['\ufeff' + text];
}

/** نامِ فایل: برچسبِ فارسیِ جدول + زمانِ محلی؛ `:` و `/` در نامِ فایلِ ویندوز ممنوع‌اند */
export function csvFilename(base: string, d: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, '0');
  const stamp = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}_${p(d.getHours())}-${p(d.getMinutes())}`;
  return `${base.replace(/[\\/:*?"<>|]/g, '')}-${stamp}.csv`;
}

/** دانلودِ بی‌فرم: یک لینکِ موقت که همان لحظه از DOM برداشته می‌شود */
export function downloadCsv(base: string, table: ExportTable, d: Date = new Date()): void {
  const blob = new Blob(csvBlobParts(csvText(table)), { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = csvFilename(base, d);
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
  // بی‌تأخیر revoke در بعضی مرورگرها فایل را نصفه می‌گذارد؛ یک تیکِ تایمر کافی است
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
