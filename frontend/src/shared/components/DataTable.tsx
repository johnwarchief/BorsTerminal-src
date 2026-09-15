// shared/components/DataTable.tsx -- جدول پایه روی TanStack Table
import { flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type ColumnDef } from '@tanstack/react-table';
import { EmptyState } from './EmptyState';

export function DataTable<T>({
  columns,
  data,
  emptyTitle = 'داده ای نیست',
  emptyHint,
}: {
  columns: ColumnDef<T, unknown>[];
  data: T[];
  emptyTitle?: string;
  emptyHint?: string;
}) {
  const table = useReactTable({
    columns,
    data,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (data.length === 0) return <EmptyState title={emptyTitle} hint={emptyHint} />;

  return (
    <div className="max-xl:max-h-[70vh] overflow-auto rounded-2xl border border-border-c">
      <table className="w-full border-collapse text-sm">
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id} className="bg-bg-card">
              {hg.headers.map((h) => (
                <th
                  key={h.id}
                  className="sticky top-0 z-[1] border-b border-border-c bg-bg-card px-3 py-2 text-right text-xs font-bold text-text-secondary"
                  onClick={h.column.getCanSort() ? h.column.getToggleSortingHandler() : undefined}
                  style={h.column.getCanSort() ? { cursor: 'pointer' } : undefined}
                >
                  {flexRender(h.column.columnDef.header, h.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="odd:bg-bg-secondary even:bg-bg-primary hover:bg-bg-card/60">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="border-b border-border-c/50 px-3 py-2 text-text-primary">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
