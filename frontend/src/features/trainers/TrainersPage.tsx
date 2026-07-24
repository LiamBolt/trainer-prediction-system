import { useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { createColumnHelper } from '@tanstack/react-table';
import { LayoutGrid, Rows3 } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { DataTable } from '@/components/table/DataTable';
import { FilterBar } from '@/components/table/FilterBar';
import {
  Avatar,
  Badge,
  Card,
  CardBody,
  IconButton,
  Pagination,
  Combobox,
  Select,
  Skeleton,
  EmptyState,
} from '@/components/ui';
import { AvailabilityPill } from '@/components/prediction';
import { trainersApi } from '@/api/endpoints';
import { useDebounce } from '@/hooks/useDebounce';
import {
  AVAILABILITY_LABELS,
  PROFICIENCY_LABELS,
  REGIONS,
  SPECIALIZATIONS,
} from '@/lib/constants';
import { formatForceNumber } from '@/lib/format';
import type { AvailabilityStatus, Trainer } from '@/types/domain';

const col = createColumnHelper<Trainer>();

/** Trainer directory (§11.6) — table + card-grid toggle, read-only for Officers
 *  and Administrators (FR-02). */
export function TrainersPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [view, setView] = useState<'table' | 'grid'>('table');

  const page = Number(params.get('page') ?? '1');
  const specialization = params.get('specialization') ?? '';
  const region = params.get('region') ?? '';
  const availability = params.get('availability') ?? '';
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
    queryKey: ['trainers', { search, specialization, region, availability, page }],
    queryFn: () =>
      trainersApi.listTrainers({
        search: search || undefined,
        specialization: specialization || undefined,
        region: region || undefined,
        availability: (availability || undefined) as AvailabilityStatus | undefined,
        page,
      }),
  });

  const columns = useMemo(
    () => [
      col.accessor('fullName', {
        header: 'Trainer',
        cell: (c) => (
          <span className="flex items-center gap-3">
            <Avatar name={c.getValue()} size={32} />
            <span className="flex flex-col">
              <span className="font-medium text-ink">
                {c.row.original.policeRank} {c.getValue()}
              </span>
              <span className="font-mono text-label text-text-muted">
                {formatForceNumber(c.row.original.forceNumber)}
              </span>
            </span>
          </span>
        ),
      }),
      col.accessor('station', { header: 'Station' }),
      col.accessor('region', { header: 'Region' }),
      col.accessor('yearsExperience', {
        header: 'Years',
        cell: (c) => <span className="font-mono text-data tabular-nums">{c.getValue()}</span>,
        meta: { align: 'right' },
      }),
      col.accessor('specializations', {
        header: 'Specialisations',
        enableSorting: false,
        cell: (c) => (
          <span className="flex flex-wrap gap-1">
            {c.getValue().slice(0, 2).map((s) => (
              <Badge key={s.specializationId} tone="neutral" dot={false}>
                {s.specializationArea}
              </Badge>
            ))}
            {c.getValue().length > 2 && (
              <span className="text-body-sm text-text-muted">+{c.getValue().length - 2}</span>
            )}
          </span>
        ),
      }),
      col.accessor('availabilityStatus', {
        header: 'Availability',
        cell: (c) => <AvailabilityPill status={c.getValue()} />,
      }),
    ],
    [],
  );

  const items = query.data?.items ?? [];
  const hasFilters = Boolean(specialization || region || availability || search);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Trainers"
        title="Trainer directory"
        description="Every trainer on the establishment, with their specialisations and current availability."
        actions={
          <div className="flex items-center gap-1 rounded-sm border border-hairline p-1">
            <IconButton
              label="Table view"
              size="sm"
              variant={view === 'table' ? 'primary' : 'ghost'}
              onClick={() => setView('table')}
            >
              <Rows3 size={16} className="shrink-0" />
            </IconButton>
            <IconButton
              label="Card view"
              size="sm"
              variant={view === 'grid' ? 'primary' : 'ghost'}
              onClick={() => setView('grid')}
            >
              <LayoutGrid size={16} className="shrink-0" />
            </IconButton>
          </div>
        }
      />

      <FilterBar
        search={searchInput}
        onSearchChange={setSearchInput}
        searchPlaceholder="Search by name or force number…"
        hasActiveFilters={hasFilters}
        onClear={() => {
          setSearchInput('');
          setParams(new URLSearchParams());
        }}
      >
        <div className="w-full sm:w-56">
          <Combobox
            value={specialization}
            onChange={(v) => setParam('specialization', v)}
            options={SPECIALIZATIONS.map((s) => ({ value: s, label: s }))}
            placeholder="Specialisation"
          />
        </div>
        <div className="w-full sm:w-44">
          <Select
            value={region}
            onValueChange={(v) => setParam('region', v === 'all' ? '' : v)}
            options={[
              { value: 'all', label: 'All regions' },
              ...REGIONS.map((r) => ({ value: r, label: r })),
            ]}
            placeholder="Region"
            aria-label="Filter by region"
          />
        </div>
        <div className="w-full sm:w-44">
          <Select
            value={availability}
            onValueChange={(v) => setParam('availability', v === 'all' ? '' : v)}
            options={[
              { value: 'all', label: 'Any availability' },
              ...Object.entries(AVAILABILITY_LABELS).map(([value, label]) => ({ value, label })),
            ]}
            placeholder="Availability"
            aria-label="Filter by availability"
          />
        </div>
      </FilterBar>

      {view === 'table' ? (
        <DataTable
          columns={columns as never}
          data={items}
          isLoading={query.isLoading}
          isError={query.isError}
          onRetry={() => query.refetch()}
          onRowClick={(t) => navigate(`/trainers/${t.trainerId}`)}
          getRowId={(t) => String(t.trainerId)}
          empty={{ title: 'No trainers match these filters', description: 'Try widening the filters.' }}
        />
      ) : query.isLoading ? (
        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40 rounded-md" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <Card>
          <CardBody>
            <EmptyState title="No trainers match these filters" description="Try widening the filters." />
          </CardBody>
        </Card>
      ) : (
        <div className="grid items-stretch gap-6 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((t) => (
            <button key={t.trainerId} type="button" onClick={() => navigate(`/trainers/${t.trainerId}`)} className="text-left">
              <Card interactive className="h-full">
                <CardBody>
                  <div className="flex flex-col gap-3">
                    <div className="flex items-center gap-3">
                      <Avatar name={t.fullName} size={40} />
                      <div className="flex min-w-0 flex-col">
                        <span className="truncate text-h3 text-ink">
                          {t.policeRank} {t.fullName}
                        </span>
                        <span className="truncate font-mono text-label text-text-muted">
                          {formatForceNumber(t.forceNumber)} · {t.station}
                        </span>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {t.specializations.slice(0, 2).map((s) => (
                        <Badge key={s.specializationId} tone="neutral" dot={false}>
                          {s.specializationArea} · {PROFICIENCY_LABELS[s.proficiencyLevel]}
                        </Badge>
                      ))}
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-label text-text-muted">
                        {t.yearsExperience} years of service
                      </span>
                      <AvailabilityPill status={t.availabilityStatus} />
                    </div>
                  </div>
                </CardBody>
              </Card>
            </button>
          ))}
        </div>
      )}

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
