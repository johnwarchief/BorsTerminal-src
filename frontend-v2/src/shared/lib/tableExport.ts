export type ExportCell = string | number | null | undefined;

export type ExportTable = {
  columns: readonly string[];
  rows: readonly (readonly ExportCell[])[];
};

export const CSV_SEP = ';';
export const CSV_SEP_HINT = `sep=${CSV_SEP}`;

export function csvCell(value: ExportCell): string {
  const text = value == null ? '' : String(value);
  const safe = typeof value === 'string' && /^[\s\u0000-\u001f]*[=+\-@]/.test(text)
    ? `'${text}`
    : text;
  return /[",;\n\r]/.test(safe) || text !== text.trim()
    ? `"${safe.replace(/"/g, '""')}"`
    : safe;
}

export function csvText(table: ExportTable): string {
  const lines = [CSV_SEP_HINT, table.columns.map(csvCell).join(CSV_SEP)];
  for (const input of table.rows) {
    const row = [...input];
    while (row.length < table.columns.length) row.push('');
    lines.push(row.slice(0, table.columns.length).map(csvCell).join(CSV_SEP));
  }
  return `${lines.join('\r\n')}\r\n`;
}

export function toExportTable<T>(
  columns: readonly string[],
  rows: readonly T[],
  cells: (row: T) => readonly ExportCell[],
): ExportTable {
  return { columns, rows: rows.map(cells) };
}

export function csvBlobParts(text: string): BlobPart[] {
  return [`\ufeff${text}`];
}

export function stampedName(base: string, date: Date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, '0');
  const stamp = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}_${pad(date.getHours())}-${pad(date.getMinutes())}`;
  return `${base.replace(/[\\/:*?"<>|]/g, '')}-${stamp}`;
}

export function csvFilename(base: string, date: Date = new Date()): string {
  return `${stampedName(base, date)}.csv`;
}

export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = 'noopener';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function downloadCsv(base: string, table: ExportTable, date: Date = new Date()): void {
  saveBlob(new Blob(csvBlobParts(csvText(table)), { type: 'text/csv;charset=utf-8' }), csvFilename(base, date));
}

export function csvTextWithMeta(
  table: ExportTable,
  meta: readonly (readonly [string, string])[],
): string {
  const head = csvText(table);
  if (!meta.length) return head;
  const lines = meta.map(([key, value]) => [`# ${key}`, value].map(csvCell).join(CSV_SEP));
  return `${head}\r\n${lines.join('\r\n')}\r\n`;
}

export function downloadCsvWithMeta(
  base: string,
  table: ExportTable,
  meta: readonly (readonly [string, string])[],
  date: Date = new Date(),
): void {
  saveBlob(
    new Blob(csvBlobParts(csvTextWithMeta(table, meta)), { type: 'text/csv;charset=utf-8' }),
    csvFilename(base, date),
  );
}
