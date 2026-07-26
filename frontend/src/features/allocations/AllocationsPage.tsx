import { useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { createColumnHelper } from '@tanstack/react-table';
import { Download } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { DataTable } from '@/components/table/DataTable';
import { FilterBar } from '@/components/table/FilterBar';
import { Button, DateRangePicker, Pagination, Select, StatusBadge } from '@/components/ui';
import { allocationsApi } from '@/api/endpoints';
import { downloadCsv } from '@/lib/csv';
import { ALLOCATION_STATUS_LABELS } from '@/lib/constants';
import { formatDate, formatScore, ordinal } from '@/lib/format';
import type { AllocationListItem } from '@/types/api';
import type { AllocationStatus } from '@/types/domain';

const col = createColumnHelper<AllocationListItem>();

export function AllocationsPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

  const page = Number(params.get('page') ?? '1');
  const status = params.get('status') ?? '';
  const from = params.get('from') ?? '';
  const to = params.get('to') ?? '';
  const [search, setSearch] = useState('');

  const setParam = (key: string, value: string) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) next.set(key, value);
      else next.delete(key);
      if (key !== 'page') next.delete('page');
      return next;
    });
  };

  const query = useQuery({
    queryKey: ['allocations', { status, from, to, page }],
    queryFn: () =>
      allocationsApi.listAllocations({
        status: (status || undefined) as AllocationStatus | undefined,
        from: from || undefined,
        to: to || undefined,
        page,
      }),
  });

  const columns = useMemo(
    () => [
      col.accessor('registryNumber', {
        header: 'Registry no.',
        cell: (c) => <span className="font-mono text-data tabular-nums">{c.getValue()}</span>,
      }),
      col.accessor('programmeTitle', {
        header: 'Programme',
        cell: (c) => (
          <span className="block max-w-xs truncate font-medium text-ink" title={c.getValue()}>
            {c.getValue()}
          </span>
        ),
      }),
      col.accessor('trainerName', {
        header: 'Trainer',
        cell: (c) => `${c.row.original.trainerRank} ${c.getValue()}`,
      }),
      col.accessor('frozenRankPosition', {
        header: 'Rank',
        cell: (c) => <span className="font-mono text-data tabular-nums">{ordinal(c.getValue())}</span>,
        meta: { align: 'right' },
      }),
      col.accessor('frozenScore', {
        header: 'Score',
        cell: (c) => <span className="font-mono text-data tabular-nums">{formatScore(c.getValue())}</span>,
        meta: { align: 'right' },
      }),
      col.accessor('approvedByName', { header: 'Approved by' }),
      col.accessor('approvalDate', {
        header: 'Approved',
        cell: (c) => <span className="font-mono text-data tabular-nums">{formatDate(c.getValue())}</span>,
      }),
      col.accessor('status', {
        header: 'Status',
        cell: (c) => <StatusBadge kind="allocation" value={c.getValue()} />,
      }),
    ],
    [],
  );

  const items = query.data?.items ?? [];
  // Search by programme — filters the loaded allocations by title (case-insensitive).
  const q = search.trim().toLowerCase();
  const rows = q ? items.filter((a) => a.programmeTitle.toLowerCase().includes(q)) : items;
  const hasFilters = Boolean(status || from || to || search);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Decisions"
        title="Allocations"
        description="Every approved allocation, with the score and rank frozen at the moment of approval."
      />

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search by programme…"
        hasActiveFilters={hasFilters}
        onClear={() => {
          setSearch('');
          setParams(new URLSearchParams());
        }}
        actions={
          <Button
            variant="secondary"
            size="sm"
            icon={<Download size={16} className="shrink-0" />}
            onClick={() =>
              downloadCsv('allocations', rows, [
                { key: 'registry', header: 'Registry No.', value: (a) => a.registryNumber },
                { key: 'programme', header: 'Programme', value: (a) => a.programmeTitle },
                { key: 'trainer', header: 'Trainer', value: (a) => `${a.trainerRank} ${a.trainerName}` },
                { key: 'rank', header: 'Rank At Approval', value: (a) => a.frozenRankPosition },
                { key: 'score', header: 'Score', value: (a) => a.frozenScore.toFixed(1) },
                { key: 'approvedBy', header: 'Approved By', value: (a) => a.approvedByName },
                { key: 'date', header: 'Approval Date', value: (a) => formatDate(a.approvalDate) },
                { key: 'status', header: 'Status', value: (a) => ALLOCATION_STATUS_LABELS[a.status] },
              ])
            }
          >
            Export CSV
          </Button>
        }
      >
        <div className="w-full sm:w-48">
          <Select
            value={status}
            onValueChange={(v) => setParam('status', v === 'all' ? '' : v)}
            options={[
              { value: 'all', label: 'All statuses' },
              ...Object.entries(ALLOCATION_STATUS_LABELS).map(([value, label]) => ({ value, label })),
            ]}
            placeholder="Status"
            aria-label="Filter by status"
          />
        </div>
        <div className="w-full sm:w-64">
          <DateRangePicker
            value={{ from: from || undefined, to: to || undefined }}
            onChange={(v) => {
              setParam('from', v.from ?? '');
              setParam('to', v.to ?? '');
            }}
            placeholder="Approval date range"
          />
        </div>
      </FilterBar>

      <DataTable
        columns={columns as never}
        data={rows}
        isLoading={query.isLoading}
        isError={query.isError}
        onRetry={() => query.refetch()}
        onRowClick={(a) => navigate(`/allocations/${a.allocationId}`)}
        getRowId={(a) => String(a.allocationId)}
        empty={{
          title: 'No allocations yet',
          description: 'Approve a trainer from a ranking to create the first allocation.',
        }}
      />

      {!q && query.data && query.data.pageCount > 1 && (
        <Pagination
          page={query.data.page}
          pageCount={query.data.pageCount}
          total={query.data.total}
          pageSize={query.data.pageSize}
          onPageChange={(p) => setParam('page', String(p))}
        />
      )}
    </div>
  );
}
