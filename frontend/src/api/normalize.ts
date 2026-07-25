import type { Paginated } from '@/types/api';

/**
 * Normalise a list response from the real backend into the frontend's `Paginated<T>`.
 *
 * The API and the mocks disagree on one field name — the backend paginates with
 * `totalPages`, the UI reads `pageCount` — so without this every list silently loses
 * its pagination control. `mapItem` adapts each row when the real row shape differs
 * from what the components expect (e.g. audit entries).
 */
export function toPaginated<T>(
  raw: unknown,
  mapItem: (item: any) => T = (i) => i as T, // eslint-disable-line @typescript-eslint/no-explicit-any
): Paginated<T> {
  const r = (raw ?? {}) as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  const items: unknown[] = Array.isArray(r.items) ? r.items : Array.isArray(raw) ? raw : [];
  return {
    items: items.map(mapItem),
    total: typeof r.total === 'number' ? r.total : items.length,
    page: typeof r.page === 'number' ? r.page : 1,
    pageSize: typeof r.pageSize === 'number' ? r.pageSize : items.length,
    pageCount: r.pageCount ?? r.totalPages ?? 1,
  };
}
