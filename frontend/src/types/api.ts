/**
 * API transport shapes (§9.3). These envelopes are what the service layer
 * returns; their signatures are final and survive the mock -> real backend swap.
 */
import type {
  AccountStatus,
  Allocation,
  AllocationStatus,
  AuditAction,
  AuditLogEntry,
  AvailabilityStatus,
  CriterionKey,
  PerformanceEvaluation,
  PoliceRank,
  ProgrammeStatus,
  QualificationLevel,
  RoleName,
  TrainingProgramme,
  User,
} from './domain';

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  pageCount: number;
}

export interface AuthSession {
  token: string;
  user: User;
  expiresAt: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

/** Discriminated result so the sign-in screen can render every FR-01 state. */
export type LoginResult =
  | { outcome: 'SUCCESS'; session: AuthSession }
  | { outcome: 'INVALID'; attemptsRemaining: number }
  | { outcome: 'LOCKED'; unlockAt: string }
  | { outcome: 'DEACTIVATED' };

export interface ProgrammeCreateInput {
  title: string;
  categoryId: number;
  startDate: string;
  endDate: string;
  stationId: number;
  expectedParticipants?: number;
}

export interface RequirementsInput {
  requiredSpecializationAreaId: number;
  minimumExperience: number;
  minimumQualificationLevelId: number | null;
}

export interface EligibilityPreview {
  eligible: number;
  total: number;
}

export interface ApproveAllocationInput {
  predictionId: number;
  programmeId: number;
  trainerId: number;
  remarks: string;
  weights: Record<CriterionKey, number>;
  weightsWereSimulated: boolean;
}

export interface DeclineAssignmentInput {
  allocationId: number;
  reason: string;
}

export interface EvaluationInput {
  allocationId: number;
  scoreAwarded: number;
  evaluatorComments: string;
  evaluationDate: string;
}

export interface UserCreateInput {
  username: string;
  fullName: string;
  email: string;
  role: RoleName;
}

/** Filters for the Users directory (FR-12). */
export interface UserFilters {
  search?: string;
  role?: RoleName;
  accountStatus?: AccountStatus;
  page?: number;
  pageSize?: number;
}

/** POST /users response — the account plus the ONE-TIME temporary password (§6.9). */
export interface UserCreated {
  user: User;
  temporaryPassword: string;
  message: string;
}

/** POST /users/{id}/reset-password response — a new one-time password (§6.10). */
export interface PasswordReset {
  temporaryPassword: string;
  message: string;
}

export interface UserUpdateInput {
  fullName?: string;
  email?: string;
  role?: RoleName;
  accountStatus?: AccountStatus;
}

/** FR-03 — the trainer's full credential lists (adding never overwrites). */
export interface TrainerCredentialsInput {
  qualifications: {
    qualificationId: number;
    qualificationName: string;
    qualificationLevel: QualificationLevel;
    institutionName: string;
    yearObtained: number;
  }[];
  specializations: {
    specializationId: number;
    specializationArea: string;
    proficiencyLevel: string;
  }[];
}

export interface TrainerSelfUpdateInput {
  policeRank: PoliceRank;
  station: string;
  yearsExperience: number;
  contactNumber: string;
  availabilityStatus: AvailabilityStatus;
}

/** Filters mapped to/from URL search params, then folded into query keys. */
export interface ProgrammeFilters {
  search?: string;
  status?: ProgrammeStatus;
  category?: string;
  from?: string;
  to?: string;
  page?: number;
  pageSize?: number;
}

export interface TrainerFilters {
  search?: string;
  // The API keys on reference IDs and camelCase status — NOT free-text names. Sending
  // `specialization`/`region`/`availability` (names) was silently ignored → no filter.
  specializationAreaId?: number;
  stationId?: number;
  regionId?: number;
  availabilityStatus?: AvailabilityStatus;
  minExperience?: number;
  maxExperience?: number;
  page?: number;
  pageSize?: number;
}

export interface AllocationFilters {
  status?: AllocationStatus;
  trainerId?: number;
  from?: string;
  to?: string;
  page?: number;
  pageSize?: number;
}

export interface AuditFilters {
  action?: AuditAction;
  userId?: number;
  role?: RoleName;
  from?: string;
  to?: string;
  page?: number;
  pageSize?: number;
}

export interface ReportFilters {
  from?: string;
  to?: string;
  category?: string;
}

export interface DashboardSummary {
  awaitingApproval: number;
  predictionsReady: number;
  allocationsThisQuarter: number;
  evaluationsOutstanding: number;
}

// --- List/view shapes (server-side joins for list rows) ------------------

export interface AllocationListItem extends Allocation {
  programmeTitle: string;
  trainerName: string;
  trainerRank: PoliceRank;
  trainerForceNumber: string;
  trainerStation: string;
  programmeStartDate: string;
  programmeEndDate: string;
  programmeLocation: string;
}

export interface ProgrammeDetail {
  programme: TrainingProgramme;
  allocation: Allocation | null;
  hasRun: boolean;
  auditTrail: AuditLogEntry[];
}

export interface TrainerEvaluationsResponse {
  evaluations: PerformanceEvaluation[];
  mean: number | null;
}

export interface PredictionQueueItem {
  programmeId: number;
  title: string;
  category: string;
  rankedCount: number;
  topTrainerName: string;
  topTrainerRank: PoliceRank;
  topScore: number;
  generatedDate: string;
}

export interface Bucket {
  label: string;
  value: number;
}

export interface TrendPoint {
  label: string;
  value: number;
}

export interface RuntimePoint {
  date: string;
  ms: number;
}

export interface DashboardData {
  role: RoleName;
  summary: DashboardSummary;
  predictionQueue?: PredictionQueueItem[];
  utilisation?: Bucket[];
  performanceTrend?: TrendPoint[];
  recentActivity?: AuditLogEntry[];
  myRequestsByStatus?: Bucket[];
  requestsNeedingRequirements?: TrainingProgramme[];
  upcoming?: TrainingProgramme[];
  pendingInvitations?: AllocationListItem[];
  profileCompleteness?: number;
  myMeanScore?: number | null;
  myScoreTrend?: TrendPoint[];
  usersByRole?: Bucket[];
  failedSignins24h?: number;
  lockedAccounts?: number;
  activeUsers?: number;
  predictionRuntimes?: RuntimePoint[];
  auditVolume?: number;
  lastBackupAt?: string;
}

// --- Report shapes --------------------------------------------------------

export interface UtilisationReportRow {
  trainerId: number;
  trainerName: string;
  rank: PoliceRank;
  forceNumber: string;
  allocations: number;
  lastAssigned: string | null;
}

export interface AllocationHistoryRow {
  registryNumber: string;
  programmeTitle: string;
  trainerName: string;
  approvedByName: string;
  approvalDate: string;
  status: AllocationStatus;
  score: number;
}

export interface PerformanceTrendRow {
  quarter: string;
  meanScore: number;
  evaluationCount: number;
}

export interface ReportResponse<Row> {
  rows: Row[];
  chart: TrendPoint[];
  generatedAt: string;
  filters: ReportFilters;
}
