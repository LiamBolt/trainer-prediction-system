import { client } from '../axiosClient';
import type {
  AllocationHistoryRow,
  PerformanceTrendRow,
  ReportFilters,
  ReportResponse,
  UtilisationReportRow,
} from '@/types/api';

export type ReportKind = 'utilisation' | 'allocations' | 'performance';

export const getUtilisationReport = (
  filters: ReportFilters = {},
): Promise<ReportResponse<UtilisationReportRow>> =>
  client.get('/reports/utilisation', { params: filters }).then((r) => r.data);

export const getAllocationHistoryReport = (
  filters: ReportFilters = {},
): Promise<ReportResponse<AllocationHistoryRow>> =>
  client.get('/reports/allocations', { params: filters }).then((r) => r.data);

export const getPerformanceTrendReport = (
  filters: ReportFilters = {},
): Promise<ReportResponse<PerformanceTrendRow>> =>
  client.get('/reports/performance', { params: filters }).then((r) => r.data);
