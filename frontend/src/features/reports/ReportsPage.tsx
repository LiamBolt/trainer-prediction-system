import { lazy, Suspense, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, FileText } from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  DateRangePicker,
  EmptyState,
  ErrorState,
  Select,
  Skeleton,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  toast,
} from '@/components/ui';
import { FilterBar } from '@/components/table/FilterBar';
import { ReportPrintLayout } from './ReportPrintLayout';
import { reportsApi } from '@/api/endpoints';
import { useAuth } from '@/hooks/useAuth';
import { downloadCsv } from '@/lib/csv';
import { exportElementToPdf } from '@/lib/pdf';
import { PROGRAMME_CATEGORIES, ALLOCATION_STATUS_LABELS } from '@/lib/constants';
import { formatDate, formatForceNumber, formatRating, formatScore } from '@/lib/format';
import type { ReportFilters } from '@/types/api';

const TrendLine = lazy(() => import('@/components/charts/TrendLine').then((m) => ({ default: m.TrendLine })));
const DistributionBar = lazy(() =>
  import('@/components/charts/DistributionBar').then((m) => ({ default: m.DistributionBar })),
);

type Kind = 'utilisation' | 'allocations' | 'performance';

/** Reports (FR-11, §11.9) — three report types, each filterable by date range and
 *  category, with a chart, a data table, and PDF + CSV export. */
export function ReportsPage() {
  const { user } = useAuth();
  const [kind, setKind] = useState<Kind>('utilisation');
  const [filters, setFilters] = useState<ReportFilters>({});
  const [exporting, setExporting] = useState(false);
  const printRef = useRef<HTMLDivElement>(null);

  const utilisation = useQuery({
    queryKey: ['report', 'utilisation', filters],
    queryFn: () => reportsApi.getUtilisationReport(filters),
    enabled: kind === 'utilisation',
  });
  const allocations = useQuery({
    queryKey: ['report', 'allocations', filters],
    queryFn: () => reportsApi.getAllocationHistoryReport(filters),
    enabled: kind === 'allocations',
  });
  const performance = useQuery({
    queryKey: ['report', 'performance', filters],
    queryFn: () => reportsApi.getPerformanceTrendReport(filters),
    enabled: kind === 'performance',
  });

  const active = kind === 'utilisation' ? utilisation : kind === 'allocations' ? allocations : performance;

  const TITLES: Record<Kind, string> = {
    utilisation: 'Training utilisation',
    allocations: 'Allocation history',
    performance: 'Performance trends',
  };

  // Normalise the active report into printable/CSV columns + rows.
  const printColumns =
    kind === 'utilisation'
      ? [
          { key: 'trainer', header: 'Trainer' },
          { key: 'force', header: 'Force No.' },
          { key: 'allocations', header: 'Allocations' },
          { key: 'lastAssigned', header: 'Last Assigned' },
        ]
      : kind === 'allocations'
        ? [
            { key: 'registry', header: 'Registry No.' },
            { key: 'programme', header: 'Programme' },
            { key: 'trainer', header: 'Trainer' },
            { key: 'score', header: 'Score' },
            { key: 'date', header: 'Approved' },
            { key: 'status', header: 'Status' },
          ]
        : [
            { key: 'quarter', header: 'Quarter' },
            { key: 'mean', header: 'Mean Score' },
            { key: 'count', header: 'Evaluations' },
          ];

  const printRows: Record<string, string | number>[] =
    kind === 'utilisation'
      ? (utilisation.data?.rows ?? []).map((r) => ({
          trainer: `${r.rank} ${r.trainerName}`,
          force: formatForceNumber(r.forceNumber),
          allocations: r.allocations,
          lastAssigned: r.lastAssigned ? formatDate(r.lastAssigned) : 'Never',
        }))
      : kind === 'allocations'
        ? (allocations.data?.rows ?? []).map((r) => ({
            registry: r.registryNumber,
            programme: r.programmeTitle,
            trainer: r.trainerName,
            score: formatScore(r.score),
            date: formatDate(r.approvalDate),
            status: ALLOCATION_STATUS_LABELS[r.status],
          }))
        : (performance.data?.rows ?? []).map((r) => ({
            quarter: r.quarter,
            mean: formatRating(r.meanScore),
            count: r.evaluationCount,
          }));

  const exportPdf = async () => {
    if (!printRef.current) return;
    try {
      setExporting(true);
      await exportElementToPdf(printRef.current, `${kind}-report.pdf`);
      toast.success('Report exported to PDF');
    } catch {
      toast.error('Could not export the report.');
    } finally {
      setExporting(false);
    }
  };

  const exportCsv = () => {
    downloadCsv(
      `${kind}-report`,
      printRows,
      printColumns.map((c) => ({ key: c.key, header: c.header, value: (r) => r[c.key] ?? '' })),
    );
    toast.success('Report exported to CSV');
  };

  const hasFilters = Boolean(filters.from || filters.to || filters.category);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Insights"
        title="Reports"
        description="Filter, review, and export the training record. Exports carry their own filter parameters and timestamp."
      />

      <Tabs value={kind} onValueChange={(v) => setKind(v as Kind)}>
        <TabsList>
          <TabsTrigger value="utilisation">Training utilisation</TabsTrigger>
          <TabsTrigger value="allocations">Allocation history</TabsTrigger>
          <TabsTrigger value="performance">Performance trends</TabsTrigger>
        </TabsList>

        <TabsContent value={kind}>
          <div className="flex flex-col gap-6">
            <FilterBar
              hasActiveFilters={hasFilters}
              onClear={() => setFilters({})}
              actions={
                <div className="flex items-center gap-2">
                  <Button variant="secondary" size="sm" onClick={exportCsv} icon={<Download size={16} className="shrink-0" />}>
                    CSV
                  </Button>
                  <Button variant="secondary" size="sm" onClick={exportPdf} loading={exporting} icon={<FileText size={16} className="shrink-0" />}>
                    PDF
                  </Button>
                </div>
              }
            >
              <div className="w-full sm:w-64">
                <DateRangePicker
                  value={{ from: filters.from, to: filters.to }}
                  onChange={(v) => setFilters((f) => ({ ...f, from: v.from, to: v.to }))}
                  placeholder="Date range"
                />
              </div>
              <div className="w-full sm:w-52">
                <Select
                  value={filters.category ?? ''}
                  onValueChange={(v) => setFilters((f) => ({ ...f, category: v === 'all' ? undefined : v }))}
                  options={[
                    { value: 'all', label: 'All categories' },
                    ...PROGRAMME_CATEGORIES.map((c) => ({ value: c, label: c })),
                  ]}
                  placeholder="Category"
                  aria-label="Filter by category"
                />
              </div>
            </FilterBar>

            {active.isLoading ? (
              <>
                <Skeleton className="h-72 rounded-md" />
                <Skeleton className="h-64 rounded-md" />
              </>
            ) : active.isError ? (
              <Card>
                <CardBody>
                  <ErrorState onRetry={() => active.refetch()} />
                </CardBody>
              </Card>
            ) : (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle>{TITLES[kind]}</CardTitle>
                  </CardHeader>
                  <CardBody>
                    {(active.data?.chart.length ?? 0) === 0 ? (
                      <EmptyState compact title="No data for these filters" description="Try widening the date range." />
                    ) : (
                      <Suspense fallback={<Skeleton className="h-64 rounded-md" />}>
                        {kind === 'performance' ? (
                          <TrendLine data={active.data!.chart} domain={[1, 5]} height={280} valueSuffix=" / 5" />
                        ) : (
                          <DistributionBar data={active.data!.chart} layout={kind === 'utilisation' ? 'vertical' : 'horizontal'} height={300} />
                        )}
                      </Suspense>
                    )}
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Data</CardTitle>
                  </CardHeader>
                  <CardBody>
                    {printRows.length === 0 ? (
                      <EmptyState compact title="No records for these filters" />
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full border-collapse">
                          <thead>
                            <tr className="border-b border-hairline">
                              {printColumns.map((c) => (
                                <th key={c.key} className="px-4 py-3 text-left font-mono text-label uppercase text-text-muted first:pl-0">
                                  {c.header}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {printRows.slice(0, 50).map((r, i) => (
                              <tr key={i} className="border-b border-hairline last:border-b-0">
                                {printColumns.map((c) => (
                                  <td key={c.key} className="h-row whitespace-nowrap px-4 align-middle text-body text-ink first:pl-0">
                                    {r[c.key]}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardBody>
                </Card>
              </>
            )}
          </div>
        </TabsContent>
      </Tabs>

      {/* Off-screen print layout captured for PDF */}
      <ReportPrintLayout
        ref={printRef}
        title={TITLES[kind]}
        filters={filters}
        generatedBy={user?.fullName ?? 'Unknown officer'}
        columns={printColumns}
        rows={printRows}
      />
    </div>
  );
}
