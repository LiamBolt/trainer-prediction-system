import { useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { createColumnHelper } from '@tanstack/react-table';
import { Plus, Download } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { DataTable } from '@/components/table/DataTable';
import { FilterBar } from '@/components/table/FilterBar';
import { Button, Pagination, Select, StatusBadge } from '@/components/ui';
import { RoleGate } from '@/components/routing/RoleGate';
import { programmesApi } from '@/api/endpoints';
import { useDebounce } from '@/hooks/useDebounce';
import { downloadCsv } from '@/lib/csv';
import { PROGRAMME_STATUS_LABELS, PROGRAMME_CATEGORIES } from '@/lib/constants';
import { formatDate, formatDateRange, programmeRegistry } from '@/lib/format';
import type { ProgrammeStatus, TrainingProgramme } from '@/types/domain';

const col = createColumnHelper<TrainingProgramme>();

export function ProgrammesPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

  const page = Number(params.get('page') ?? '1');
  const status = params.get('status') ?? '';
  const category = params.get('category') ?? '';
  const [searchInput, setSearchInput] = useState(params.get('q') ?? '');
  const search = useDebounce(searchInput, 300);

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
    queryKey: ['programmes', { search, status, category, page }],
    queryFn: () =>
      programmesApi.listProgrammes({
        search: search || undefined,
        status: (status || undefined) as ProgrammeStatus | undefined,
        category: category || undefined,
        page,
      }),
  });

  const columns = useMemo(
    () => [
      col.accessor('programmeId', {
        header: 'Registry no.',
        cell: (c) => <span className="font-mono text-data tabular-nums">{programmeRegistry(c.getValue())}</span>,
      }),
      col.accessor('title', {
        header: 'Title',
        cell: (c) => (
          <span className="block max-w-xs truncate font-medium text-ink" title={c.getValue()}>
            {c.getValue()}
          </span>
        ),
      }),
      col.accessor('category', { header: 'Category' }),
      col.accessor('requiredSpecialization', {
        header: 'Specialisation',
        cell: (c) =>
          c.getValue() ? (
            <span className="block max-w-xs truncate">{c.getValue()}</span>
          ) : (
            <span className="text-text-disabled">—</span>
          ),
      }),
      col.accessor('startDate', {
        header: 'Dates',
        cell: (c) => (
          <span className="font-mono text-data tabular-nums">
            {formatDateRange(c.row.original.startDate, c.row.original.endDate)}
          </span>
        ),
      }),
      col.accessor('location', { header: 'Location' }),
      col.accessor('status', {
        header: 'Status',
        cell: (c) => <StatusBadge kind="programme" value={c.getValue()} />,
      }),
      col.accessor('createdByName', { header: 'Created by' }),
    ],
    [],
  );

  const items = query.data?.items ?? [];
  const hasFilters = Boolean(status || category || search);

  const exportCsv = () => {
    downloadCsv('training-requests', items, [
      { key: 'registry', header: 'Registry No.', value: (p) => programmeRegistry(p.programmeId) },
      { key: 'title', header: 'Title', value: (p) => p.title },
      { key: 'category', header: 'Category', value: (p) => p.category },
      { key: 'spec', header: 'Required Specialisation', value: (p) => p.requiredSpecialization },
      { key: 'start', header: 'Start', value: (p) => formatDate(p.startDate) },
      { key: 'end', header: 'End', value: (p) => formatDate(p.endDate) },
      { key: 'location', header: 'Location', value: (p) => p.location },
      { key: 'status', header: 'Status', value: (p) => PROGRAMME_STATUS_LABELS[p.status] },
      { key: 'createdBy', header: 'Created By', value: (p) => p.createdByName },
    ]);
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Programmes"
        title="Training requests"
        description="Every training request across the directorate, with its current status in the workflow."
        actions={
          <RoleGate roles={['TRAINING_ADMINISTRATOR', 'TRAINING_OFFICER']}>
            <Button onClick={() => navigate('/programmes/new')} icon={<Plus size={16} className="shrink-0" />}>
              Create request
            </Button>
          </RoleGate>
        }
      />

      <FilterBar
        search={searchInput}
        onSearchChange={setSearchInput}
        searchPlaceholder="Search by title…"
        hasActiveFilters={hasFilters}
        onClear={() => {
          setSearchInput('');
          setParams(new URLSearchParams());
        }}
        actions={
          <Button variant="secondary" size="sm" onClick={exportCsv} icon={<Download size={16} className="shrink-0" />}>
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
              ...Object.entries(PROGRAMME_STATUS_LABELS).map(([value, label]) => ({ value, label })),
            ]}
            placeholder="Status"
            aria-label="Filter by status"
          />
        </div>
        <div className="w-full sm:w-48">
          <Select
            value={category}
            onValueChange={(v) => setParam('category', v === 'all' ? '' : v)}
            options={[
              { value: 'all', label: 'All categories' },
              ...PROGRAMME_CATEGORIES.map((c) => ({ value: c, label: c })),
            ]}
            placeholder="Category"
            aria-label="Filter by category"
          />
        </div>
      </FilterBar>

      <DataTable
        columns={columns as never}
        data={items}
        isLoading={query.isLoading}
        isError={query.isError}
        onRetry={() => query.refetch()}
        onRowClick={(p) => navigate(`/programmes/${p.programmeId}`)}
        getRowId={(p) => String(p.programmeId)}
        empty={{
          title: 'No training requests yet',
          description: 'Create one to start matching trainers.',
        }}
      />

      {query.data && query.data.pageCount > 1 && (
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
