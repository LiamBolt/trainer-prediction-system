import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table';
import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react';
import { cn } from '@/lib/cn';
import { Skeleton, EmptyState, ErrorState } from '@/components/ui';

/**
 * DataTable — headless TanStack Table v8 (D1), styled to the §5.2 padding law:
 * cells 12px vertical / 16px horizontal, first & last cells 24px to align with
 * card padding, header row identical horizontal padding, rows exactly 52px.
 * Ships loading (shaped skeleton), empty, and error states (§5.7).
 */
export interface DataTableProps<T> {
  columns: ColumnDef<T, unknown>[];
  data: T[];
  isLoading?: boolean;
  isError?: boolean;
  onRetry?: () => void;
  empty?: { title: string; description?: string; action?: React.ReactNode };
  sorting?: SortingState;
  onSortingChange?: (updater: SortingState | ((old: SortingState) => SortingState)) => void;
  onRowClick?: (row: T) => void;
  getRowId?: (row: T) => string;
  className?: string;
}

const CELL = 'px-4 first:pl-6 last:pr-6';

export function DataTable<T>({
  columns,
  data,
  isLoading,
  isError,
  onRetry,
  empty,
  sorting,
  onSortingChange,
  onRowClick,
  getRowId,
  className,
}: DataTableProps<T>) {
  const table = useReactTable({
    data,
    columns,
    state: sorting ? { sorting } : undefined,
    onSortingChange: onSortingChange as never,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getRowId,
    manualPagination: true,
  });

  return (
    <div className={cn('overflow-hidden rounded-md border border-hairline bg-surface', className)}>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b border-hairline">
                {hg.headers.map((header) => {
                  const canSort = header.column.getCanSort();
                  const sorted = header.column.getIsSorted();
                  return (
                    <th
                      key={header.id}
                      className={cn(
                        CELL,
                        'h-12 whitespace-nowrap text-left align-middle font-mono text-label uppercase text-text-muted',
                        header.column.columnDef.meta && (header.column.columnDef.meta as { align?: string }).align === 'right' && 'text-right',
                      )}
                    >
                      {header.isPlaceholder ? null : canSort ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          className="inline-flex items-center gap-1 uppercase hover:text-ink"
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          {sorted === 'asc' ? (
                            <ArrowUp size={12} className="shrink-0" />
                          ) : sorted === 'desc' ? (
                            <ArrowDown size={12} className="shrink-0" />
                          ) : (
                            <ChevronsUpDown size={12} className="shrink-0 opacity-50" />
                          )}
                        </button>
                      ) : (
                        flexRender(header.column.columnDef.header, header.getContext())
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {isLoading &&
              Array.from({ length: 8 }).map((_, i) => (
                <tr key={`sk-${i}`} className="border-b border-hairline last:border-b-0">
                  {columns.map((_c, j) => (
                    <td key={j} className={cn(CELL, 'h-row')}>
                      <Skeleton className="h-4 w-40" />
                    </td>
                  ))}
                </tr>
              ))}

            {!isLoading &&
              !isError &&
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                  className={cn(
                    'border-b border-hairline last:border-b-0',
                    onRowClick && 'cursor-pointer transition-colors hover:bg-surface-sunken',
                  )}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className={cn(
                        CELL,
                        // whitespace-nowrap keeps every row at exactly 52px (§5.3);
                        // the table scrolls horizontally rather than growing taller.
                        'h-row whitespace-nowrap align-middle text-body text-ink',
                        (cell.column.columnDef.meta as { align?: string })?.align === 'right' && 'text-right tabular-nums',
                      )}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {!isLoading && isError && (
        <ErrorState onRetry={onRetry} />
      )}
      {!isLoading && !isError && data.length === 0 && (
        <EmptyState title={empty?.title ?? 'Nothing to show'} description={empty?.description} action={empty?.action} />
      )}
    </div>
  );
}
