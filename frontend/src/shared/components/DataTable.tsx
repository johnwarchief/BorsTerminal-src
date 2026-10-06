// shared/components/DataTable.tsx -- جدول پایه روی TanStack Table و UI Primitives
import { flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type ColumnDef } from '@tanstack/react-table';
import { EmptyState } from './EmptyState';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@shared/components/ui/table';

export function DataTable<T>({
  columns,
  data,
  emptyTitle = 'داده ای نیست',
  emptyHint,
  dense = false,
  onRowClick,
}: {
  columns: ColumnDef<T, unknown>[];
  data: T[];
  emptyTitle?: string;
  emptyHint?: string;
  dense?: boolean;
  onRowClick?: (row: T) => void;
}) {
  const table = useReactTable({
    columns,
    data,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (data.length === 0) return <EmptyState title={emptyTitle} hint={emptyHint} />;

  return (
    <div className="max-xl:max-h-[70vh] overflow-auto rounded-xl border border-border-c/70 bg-bg-card/40 backdrop-blur-xs">
      <Table dense={dense}>
        <TableHeader>
          {table.getHeaderGroups().map((hg) => (
            <TableRow key={hg.id} className="bg-bg-card/90">
              {hg.headers.map((h) => {
                const canSort = h.column.getCanSort();
                const isSorted = h.column.getIsSorted();
                return (
                  <TableHead
                    key={h.id}
                    onClick={canSort ? h.column.getToggleSortingHandler() : undefined}
                    className={canSort ? 'cursor-pointer select-none hover:text-text-primary' : undefined}
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {canSort && (
                        <span className="text-3xs text-text-muted">
                          {isSorted === 'asc' ? '↑' : isSorted === 'desc' ? '↓' : '↕'}
                        </span>
                      )}
                    </div>
                  </TableHead>
                );
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow
              key={row.id}
              onClick={onRowClick ? () => onRowClick(row.original) : undefined}
              onKeyDown={
                onRowClick
                  ? (e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onRowClick(row.original);
                      }
                    }
                  : undefined
              }
              tabIndex={onRowClick ? 0 : undefined}
              className={`odd:bg-bg-secondary/30 even:bg-bg-primary/40 ${onRowClick ? 'cursor-pointer hover:bg-bg-card/70' : ''}`}
            >
              {row.getVisibleCells().map((cell) => (
                <TableCell key={cell.id} className="text-text-primary">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
