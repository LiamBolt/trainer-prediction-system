/**
 * Mock request resolvers (§9.3). Routes an Axios request against the seeded
 * in-memory db and mutates it for approvals, declines, evaluations, and CRUD so
 * the full demo walkthrough (§18) works end-to-end without a backend. Every
 * decision writes an audit entry, mirroring the real API's behaviour.
 */
import type { InternalAxiosRequestConfig } from 'axios';
import dayjs from 'dayjs';
import type {
  Allocation,
  AuditAction,
  AuditLogEntry,
  Notification,
  PerformanceEvaluation,
  PredictionRun,
  Trainer,
  TrainingProgramme,
  User,
} from '@/types/domain';
import type {
  AllocationFilters,
  AllocationListItem,
  ApproveAllocationInput,
  AuditFilters,
  Bucket,
  DashboardData,
  DeclineAssignmentInput,
  EligibilityPreview,
  EvaluationInput,
  LoginResult,
  Paginated,
  PredictionQueueItem,
  ProgrammeCreateInput,
  ProgrammeDetail,
  ProgrammeFilters,
  ReportResponse,
  RequirementsInput,
  TrainerCredentialsInput,
  TrainerEvaluationsResponse,
  TrainerFilters,
  TrainerSelfUpdateInput,
  UserCreateInput,
  UserUpdateInput,
  UtilisationReportRow,
  AllocationHistoryRow,
  PerformanceTrendRow,
} from '@/types/api';
import { DEFAULT_WEIGHTS, MAX_LOGIN_ATTEMPTS, LOCKOUT_MINUTES } from '@/lib/constants';
import { evaluateGates, runPrediction } from '@/lib/scoring';
import { db } from './data';

const NOW = () => dayjs('2026-07-22T09:00:00');

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body?: unknown,
  ) {
    super(message);
  }
}

// --- request parsing ------------------------------------------------------

interface ParsedRequest {
  method: string;
  path: string;
  params: Record<string, unknown>;
  body: Record<string, unknown>;
}

function parse(config: InternalAxiosRequestConfig): ParsedRequest {
  const method = (config.method ?? 'get').toLowerCase();
  const path = (config.url ?? '').split('?')[0] ?? '';
  const params = (config.params as Record<string, unknown>) ?? {};
  let body: Record<string, unknown> = {};
  if (typeof config.data === 'string' && config.data.length) {
    try {
      body = JSON.parse(config.data);
    } catch {
      body = {};
    }
  } else if (config.data && typeof config.data === 'object') {
    body = config.data as Record<string, unknown>;
  }
  return { method, path, params, body };
}

// --- helpers --------------------------------------------------------------

function paginate<T>(items: T[], page = 1, pageSize = 25): Paginated<T> {
  const total = items.length;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const p = Math.min(Math.max(1, page), pageCount);
  return { items: items.slice((p - 1) * pageSize, p * pageSize), total, page: p, pageSize, pageCount };
}

const num = (v: unknown): number | undefined =>
  v === undefined || v === '' ? undefined : Number(v);
const str = (v: unknown): string | undefined => (v === undefined || v === '' ? undefined : String(v));

const trainerById = () => new Map(db.trainers.map((t) => [t.trainerId, t]));
const programmeById = (id: number) => db.programmes.find((p) => p.programmeId === id);
const categoryByProgramme = () => new Map(db.programmes.map((p) => [p.programmeId, p.category]));

function writeAudit(
  user: Pick<User, 'userId' | 'fullName' | 'role'>,
  action: AuditAction,
  affectedRecord: string,
  detail: string,
): void {
  const entry: AuditLogEntry = {
    logId: (db.audit[0]?.logId ?? db.audit.length) + 1,
    userId: user.userId,
    userName: user.fullName,
    userRole: user.role,
    actionPerformed: action,
    timestamp: NOW().toISOString(),
    affectedRecord,
    detail,
    ipAddress: '10.20.0.10',
  };
  db.audit.unshift(entry);
}

const adminActor = () => db.users[0]!;

function relevanceFor(programme: TrainingProgramme) {
  const cats = categoryByProgramme();
  return (ev: PerformanceEvaluation) => cats.get(ev.programmeId) === programme.category;
}

function ensureRun(programme: TrainingProgramme, weights = DEFAULT_WEIGHTS): PredictionRun {
  const existing = db.runs.find((r) => r.programmeId === programme.programmeId);
  if (existing && weights === DEFAULT_WEIGHTS) return existing;
  const run = runPrediction({
    programme,
    trainers: db.trainers,
    weights,
    isRelevantEvaluation: relevanceFor(programme),
    now: NOW().toDate(),
    generatedDate: NOW().toISOString(),
    elapsedMs: programme.programmeId === db.featuredProgrammeId ? 1400 : 900 + Math.round(Math.random() * 1500),
  });
  const idx = db.runs.findIndex((r) => r.programmeId === programme.programmeId);
  if (idx >= 0) db.runs[idx] = run;
  else db.runs.push(run);
  return run;
}

function toAllocationListItem(a: Allocation): AllocationListItem {
  const t = trainerById().get(a.trainerId);
  const p = programmeById(a.programmeId);
  return {
    ...a,
    programmeTitle: p?.title ?? '—',
    trainerName: t?.fullName ?? '—',
    trainerRank: t?.policeRank ?? 'IP',
    trainerForceNumber: t?.forceNumber ?? '—',
    trainerStation: t?.station ?? '—',
    programmeStartDate: p?.startDate ?? '',
    programmeEndDate: p?.endDate ?? '',
    programmeLocation: p?.location ?? '—',
  };
}

// --- auth (FR-01) ---------------------------------------------------------

interface AttemptRecord {
  count: number;
  unlockAt?: string;
}
const attempts = new Map<string, AttemptRecord>();

function handleLogin(username: string, password: string): LoginResult {
  const key = username.toLowerCase();
  const rec = attempts.get(key) ?? { count: 0 };

  if (rec.unlockAt && dayjs().isBefore(dayjs(rec.unlockAt))) {
    return { outcome: 'LOCKED', unlockAt: rec.unlockAt };
  }

  const user = db.users.find((u) => u.username.toLowerCase() === key);
  const valid = user && password === db.demoPassword;

  if (!valid) {
    rec.count += 1;
    if (rec.count >= MAX_LOGIN_ATTEMPTS) {
      rec.unlockAt = dayjs().add(LOCKOUT_MINUTES, 'minute').toISOString();
      attempts.set(key, rec);
      return { outcome: 'LOCKED', unlockAt: rec.unlockAt };
    }
    attempts.set(key, rec);
    return { outcome: 'INVALID', attemptsRemaining: MAX_LOGIN_ATTEMPTS - rec.count };
  }

  if (user.accountStatus === 'DEACTIVATED') return { outcome: 'DEACTIVATED' };

  attempts.delete(key);
  user.lastLoginAt = NOW().toISOString();
  writeAudit(user, 'LOGIN_SUCCESS', `USER#${user.userId}`, 'Signed in');
  return {
    outcome: 'SUCCESS',
    session: {
      token: `mock.${btoa(user.username)}.${Date.now()}`,
      user,
      expiresAt: dayjs().add(8, 'hour').toISOString(),
    },
  };
}

// --- dashboard ------------------------------------------------------------

function quarterLabel(d: dayjs.Dayjs): string {
  return `Q${Math.floor(d.month() / 3) + 1} ${d.year()}`;
}

function buildDashboard(role: DashboardData['role'], userId?: number): DashboardData {
  const predictedRuns = db.runs.filter(
    (r) => programmeById(r.programmeId)?.status === 'PREDICTED',
  );
  const summary = {
    awaitingApproval: db.programmes.filter((p) => p.status === 'PREDICTED').length,
    predictionsReady: predictedRuns.length,
    allocationsThisQuarter: db.allocations.filter((a) =>
      dayjs(a.approvalDate).isAfter(NOW().subtract(90, 'day')),
    ).length,
    evaluationsOutstanding: db.allocations.filter((a) => a.status === 'CONDUCTED').length,
  };

  if (role === 'TRAINING_ADMINISTRATOR') {
    const utilisation: Bucket[] = [...trainerUtilisation()].slice(0, 10);
    return {
      role,
      summary,
      predictionQueue: predictedRuns.map(predictionQueueItem),
      utilisation,
      performanceTrend: performanceByQuarter(),
      recentActivity: db.audit.slice(0, 8),
    };
  }
  if (role === 'TRAINING_OFFICER') {
    const mine = db.programmes.filter((p) => p.createdBy === (userId ?? db.users[1]!.userId));
    const byStatus = countBy(mine, (p) => p.status);
    return {
      role,
      summary,
      myRequestsByStatus: Object.entries(byStatus).map(([label, value]) => ({ label, value })),
      requestsNeedingRequirements: mine.filter((p) => p.status === 'DRAFT'),
      upcoming: db.programmes
        .filter((p) => dayjs(p.startDate).isAfter(NOW()) && dayjs(p.startDate).isBefore(NOW().add(30, 'day')))
        .slice(0, 6),
    };
  }
  if (role === 'TRAINER') {
    const trainer = db.trainers.find((t) => t.userId === userId) ?? db.trainers[0]!;
    const invitations = db.allocations
      .filter((a) => a.trainerId === trainer.trainerId && a.status === 'PENDING_TRAINER')
      .map(toAllocationListItem);
    const mean =
      trainer.performanceHistory.length > 0
        ? trainer.performanceHistory.reduce((s, e) => s + e.scoreAwarded, 0) /
          trainer.performanceHistory.length
        : null;
    return {
      role,
      summary,
      pendingInvitations: invitations,
      profileCompleteness: trainer.profileCompleteness,
      myMeanScore: mean,
      myScoreTrend: trainer.performanceHistory
        .slice()
        .sort((a, b) => dayjs(a.evaluationDate).valueOf() - dayjs(b.evaluationDate).valueOf())
        .map((e) => ({ label: dayjs(e.evaluationDate).format('MMM YY'), value: e.scoreAwarded })),
      upcoming: [],
    };
  }
  // SYSTEM_ADMINISTRATOR
  return {
    role,
    summary,
    usersByRole: Object.entries(countBy(db.users, (u) => u.role)).map(([label, value]) => ({ label, value })),
    activeUsers: db.users.filter((u) => u.accountStatus === 'ACTIVE').length,
    failedSignins24h: db.audit.filter(
      (a) => a.actionPerformed === 'LOGIN_FAILED' && dayjs(a.timestamp).isAfter(NOW().subtract(24, 'hour')),
    ).length,
    lockedAccounts: db.users.filter((u) => u.accountStatus === 'SUSPENDED').length,
    predictionRuntimes: db.runs
      .slice()
      .sort((a, b) => dayjs(a.generatedDate).valueOf() - dayjs(b.generatedDate).valueOf())
      .map((r) => ({ date: r.generatedDate, ms: r.elapsedMs })),
    auditVolume: db.audit.length,
    lastBackupAt: NOW().subtract(6, 'hour').toISOString(),
  };
}

function predictionQueueItem(run: PredictionRun): PredictionQueueItem {
  const p = programmeById(run.programmeId)!;
  const top = run.predictions[0];
  const t = top ? trainerById().get(top.trainerId) : undefined;
  return {
    programmeId: run.programmeId,
    title: p.title,
    category: p.category,
    rankedCount: run.rankedCount,
    topTrainerName: t?.fullName ?? '—',
    topTrainerRank: t?.policeRank ?? 'IP',
    topScore: top?.predictionScore ?? 0,
    generatedDate: run.generatedDate,
  };
}

function trainerUtilisation(): Bucket[] {
  const counts = new Map<number, number>();
  for (const a of db.allocations) counts.set(a.trainerId, (counts.get(a.trainerId) ?? 0) + 1);
  const tById = trainerById();
  return [...counts.entries()]
    .map(([id, value]) => ({ label: tById.get(id)?.fullName ?? `#${id}`, value }))
    .sort((a, b) => b.value - a.value);
}

function performanceByQuarter() {
  const byQ = new Map<string, number[]>();
  for (const e of db.evaluations) {
    const q = quarterLabel(dayjs(e.evaluationDate));
    (byQ.get(q) ?? byQ.set(q, []).get(q)!).push(e.scoreAwarded);
  }
  return [...byQ.entries()]
    .map(([label, xs]) => ({ label, value: Math.round((xs.reduce((s, x) => s + x, 0) / xs.length) * 10) / 10 }))
    .sort((a, b) => a.label.localeCompare(b.label))
    .slice(-8);
}

function countBy<T>(items: T[], key: (t: T) => string): Record<string, number> {
  return items.reduce<Record<string, number>>((acc, item) => {
    const k = key(item);
    acc[k] = (acc[k] ?? 0) + 1;
    return acc;
  }, {});
}

// --- resolver -------------------------------------------------------------

export function resolveRequest(config: InternalAxiosRequestConfig): unknown {
  const { method, path, params, body } = parse(config);
  const seg = path.split('/').filter(Boolean); // e.g. ['programmes','1','predict']

  // AUTH
  if (method === 'post' && path === '/auth/login')
    return handleLogin(String(body.username ?? ''), String(body.password ?? ''));
  if (method === 'post' && path === '/auth/logout') return { ok: true };

  // DASHBOARD
  if (method === 'get' && path === '/dashboard')
    return buildDashboard((str(params.role) as DashboardData['role']) ?? 'TRAINING_ADMINISTRATOR', num(params.userId));

  // TRAINERS
  if (method === 'get' && path === '/trainers') return listTrainers(params as TrainerFilters);
  if (method === 'get' && seg[0] === 'trainers' && seg[1] && !seg[2]) {
    const t = trainerById().get(Number(seg[1]));
    if (!t) throw new ApiError(404, 'Trainer not found');
    return t;
  }
  if (method === 'get' && seg[0] === 'trainers' && seg[2] === 'evaluations') {
    const t = trainerById().get(Number(seg[1]));
    if (!t) throw new ApiError(404, 'Trainer not found');
    const mean =
      t.performanceHistory.length > 0
        ? t.performanceHistory.reduce((s, e) => s + e.scoreAwarded, 0) / t.performanceHistory.length
        : null;
    return { evaluations: t.performanceHistory, mean } satisfies TrainerEvaluationsResponse;
  }
  if (method === 'get' && path === '/me/trainer') {
    const t = db.trainers.find((x) => x.userId === num(params.userId)) ?? db.trainers[0]!;
    return t;
  }
  if (method === 'patch' && seg[0] === 'trainers' && seg[2] === 'credentials')
    return updateTrainerCredentials(Number(seg[1]), body as unknown as TrainerCredentialsInput);
  if (method === 'patch' && seg[0] === 'trainers' && seg[1]) return updateTrainer(Number(seg[1]), body as unknown as TrainerSelfUpdateInput);

  // PROGRAMMES
  if (method === 'get' && path === '/programmes') return listProgrammes(params as ProgrammeFilters);
  if (method === 'post' && path === '/programmes') return createProgramme(body as unknown as ProgrammeCreateInput);
  if (method === 'get' && seg[0] === 'programmes' && seg[1] && seg[2] === 'eligibility')
    return eligibility(params);
  if (method === 'get' && seg[0] === 'programmes' && seg[1] && seg[2] === 'prediction')
    return getPrediction(Number(seg[1]));
  if (method === 'post' && seg[0] === 'programmes' && seg[1] && seg[2] === 'predict')
    return runPredict(Number(seg[1]), body);
  if (method === 'post' && seg[0] === 'programmes' && seg[1] && seg[2] === 'requirements')
    return setRequirements(Number(seg[1]), body as unknown as RequirementsInput);
  if (method === 'get' && seg[0] === 'programmes' && seg[1] && !seg[2]) return programmeDetail(Number(seg[1]));

  // ALLOCATIONS
  if (method === 'get' && path === '/allocations') return listAllocations(params as AllocationFilters);
  if (method === 'post' && path === '/allocations') return approveAllocation(body as unknown as ApproveAllocationInput);
  if (method === 'get' && seg[0] === 'allocations' && seg[1] && !seg[2]) {
    const a = db.allocations.find((x) => x.allocationId === Number(seg[1]));
    if (!a) throw new ApiError(404, 'Allocation not found');
    return toAllocationListItem(a);
  }
  if (method === 'post' && seg[0] === 'allocations' && seg[2] === 'decline')
    return declineAssignment(Number(seg[1]), body as unknown as DeclineAssignmentInput);
  if (method === 'post' && seg[0] === 'allocations' && seg[2] === 'accept')
    return acceptAssignment(Number(seg[1]));
  if (method === 'post' && seg[0] === 'allocations' && seg[2] === 'promote-next')
    return promoteNext(Number(seg[1]));

  // EVALUATIONS
  if (method === 'get' && path === '/evaluations') return listEvaluations();
  if (method === 'post' && path === '/evaluations') return recordEvaluation(body as unknown as EvaluationInput);

  // REPORTS
  if (method === 'get' && seg[0] === 'reports' && seg[1]) return buildReport(seg[1], params);

  // USERS
  if (method === 'get' && path === '/users') return db.users;
  if (method === 'post' && path === '/users') return createUser(body as unknown as UserCreateInput);
  if (method === 'patch' && seg[0] === 'users' && seg[1]) return updateUser(Number(seg[1]), body as unknown as UserUpdateInput);

  // AUDIT
  if (method === 'get' && path === '/audit') return listAudit(params as AuditFilters);

  // NOTIFICATIONS
  if (method === 'get' && path === '/notifications')
    return db.notifications.filter((n) => !num(params.recipientId) || n.recipientId === num(params.recipientId));
  if (method === 'post' && path === '/notifications/read-all') return markAllRead(num(params.recipientId));
  if (method === 'patch' && seg[0] === 'notifications' && seg[2] === 'read') return markRead(Number(seg[1]));

  // ROLES / POLICY
  if (method === 'get' && path === '/roles') return db.roles;
  if (method === 'get' && path === '/scoring-policy') return db.weightPolicy;
  if (method === 'post' && path === '/scoring-policy') return saveScoringPolicy(body);

  throw new ApiError(404, `No mock handler for ${method.toUpperCase()} ${path}`);
}

// --- trainers -------------------------------------------------------------

function listTrainers(f: TrainerFilters): Paginated<Trainer> {
  let items = db.trainers;
  const search = str(f.search)?.toLowerCase();
  if (search)
    items = items.filter(
      (t) => t.fullName.toLowerCase().includes(search) || t.forceNumber.includes(search),
    );
  if (str(f.availabilityStatus))
    items = items.filter((t) => t.availabilityStatus === f.availabilityStatus);
  if (num(f.minExperience) !== undefined)
    items = items.filter((t) => t.yearsExperience >= num(f.minExperience)!);
  if (num(f.maxExperience) !== undefined)
    items = items.filter((t) => t.yearsExperience <= num(f.maxExperience)!);
  // specializationAreaId / regionId / stationId filtering runs against the real API;
  // the mock dataset keys on names, so those filters are a no-op in mock mode.
  return paginate(items, num(f.page), num(f.pageSize) ?? 24);
}

/** FR-03 — replace the credential lists with the client's full set. */
function updateTrainerCredentials(trainerId: number, input: TrainerCredentialsInput): Trainer {
  const t = trainerById().get(trainerId);
  if (!t) throw new ApiError(404, 'Trainer not found');
  t.qualifications = input.qualifications.map((q, i) => ({
    qualificationId: q.qualificationId || 900000 + i,
    trainerId,
    qualificationName: q.qualificationName,
    qualificationLevel: q.qualificationLevel,
    institutionName: q.institutionName,
    yearObtained: Number(q.yearObtained),
  }));
  t.specializations = input.specializations.map((s, i) => ({
    specializationId: s.specializationId || 900000 + i,
    trainerId,
    specializationArea: s.specializationArea,
    proficiencyLevel: s.proficiencyLevel as Trainer['specializations'][number]['proficiencyLevel'],
  }));
  writeAudit(adminActor(), 'USER_MODIFIED', `TRAINER#${trainerId}`, 'Updated qualifications and specialisations');
  return t;
}

function updateTrainer(trainerId: number, input: TrainerSelfUpdateInput): Trainer {
  const t = trainerById().get(trainerId);
  if (!t) throw new ApiError(404, 'Trainer not found');
  Object.assign(t, {
    policeRank: input.policeRank,
    station: input.station,
    yearsExperience: input.yearsExperience,
    contactNumber: input.contactNumber,
    availabilityStatus: input.availabilityStatus,
  });
  writeAudit(adminActor(), 'USER_MODIFIED', `TRAINER#${trainerId}`, 'Updated own profile');
  return t;
}

// --- programmes -----------------------------------------------------------

function listProgrammes(f: ProgrammeFilters): Paginated<TrainingProgramme> {
  let items = [...db.programmes].sort((a, b) => dayjs(b.createdAt).valueOf() - dayjs(a.createdAt).valueOf());
  const search = str(f.search)?.toLowerCase();
  if (search) items = items.filter((p) => p.title.toLowerCase().includes(search));
  if (str(f.status)) items = items.filter((p) => p.status === f.status);
  if (str(f.category)) items = items.filter((p) => p.category === f.category);
  if (str(f.from)) items = items.filter((p) => dayjs(p.startDate).isAfter(dayjs(f.from).subtract(1, 'day')));
  if (str(f.to)) items = items.filter((p) => dayjs(p.startDate).isBefore(dayjs(f.to).add(1, 'day')));
  return paginate(items, num(f.page), num(f.pageSize) ?? 15);
}

function createProgramme(input: ProgrammeCreateInput): TrainingProgramme {
  const programmeId = Math.max(...db.programmes.map((p) => p.programmeId)) + 1;
  const officer = db.users[1]!;
  const programme: TrainingProgramme = {
    programmeId,
    title: input.title,
    category: `Category ${input.categoryId}`,
    requiredSpecialization: '',
    minimumExperience: 0,
    minimumQualification: null,
    startDate: input.startDate,
    endDate: input.endDate,
    location: `Station ${input.stationId}`,
    status: 'DRAFT',
    createdBy: officer.userId,
    createdByName: officer.fullName,
    createdAt: NOW().toISOString(),
    requirementsSetAt: null,
    requirementsChangedSincePrediction: false,
  };
  db.programmes.push(programme);
  writeAudit(officer, 'PROGRAMME_CREATED', `PROGRAMME#${programmeId}`, `Created "${input.title}"`);
  return programme;
}

function setRequirements(programmeId: number, input: RequirementsInput): TrainingProgramme {
  const p = programmeById(programmeId);
  if (!p) throw new ApiError(404, 'Programme not found');
  const alreadyPredicted = db.runs.some((r) => r.programmeId === programmeId);
  p.requiredSpecializationAreaId = input.requiredSpecializationAreaId;
  p.requiredSpecialization = String(input.requiredSpecializationAreaId);
  p.minimumExperience = input.minimumExperience;
  p.minimumQualificationLevelId = input.minimumQualificationLevelId;
  p.minimumQualification = null;
  p.requirementsSetAt = NOW().toISOString();
  if (p.status === 'DRAFT') p.status = 'REQUIREMENTS_SET';
  if (alreadyPredicted) p.requirementsChangedSincePrediction = true;
  writeAudit(db.users[1]!, alreadyPredicted ? 'REQUIREMENTS_CHANGED' : 'REQUIREMENTS_DEFINED', `PROGRAMME#${programmeId}`, 'Requirements set');
  return p;
}

function eligibility(params: Record<string, unknown>): EligibilityPreview {
  const requiredSpecialization = str(params.specialization) ?? '';
  const minimumExperience = num(params.minExp) ?? 0;
  const minimumQualification = (str(params.minQual) as TrainingProgramme['minimumQualification']) ?? null;
  const probe: TrainingProgramme = {
    ...(db.programmes[0] as TrainingProgramme),
    requiredSpecialization,
    minimumExperience,
    minimumQualification,
  };
  const eligible = requiredSpecialization
    ? db.trainers.filter((t) => evaluateGates(t, probe) === null).length
    : 0;
  return { eligible, total: db.trainers.length };
}

function getPrediction(programmeId: number): PredictionRun {
  const p = programmeById(programmeId);
  if (!p) throw new ApiError(404, 'Programme not found');
  return ensureRun(p);
}

function runPredict(programmeId: number, body: Record<string, unknown>): PredictionRun {
  const p = programmeById(programmeId);
  if (!p) throw new ApiError(404, 'Programme not found');
  const weights = (body.weights as typeof DEFAULT_WEIGHTS) ?? DEFAULT_WEIGHTS;
  const run = runPrediction({
    programme: p,
    trainers: db.trainers,
    weights,
    isRelevantEvaluation: relevanceFor(p),
    now: NOW().toDate(),
    generatedDate: NOW().toISOString(),
    elapsedMs: programmeId === db.featuredProgrammeId ? 1400 : 900 + Math.round(Math.random() * 1500),
  });
  const idx = db.runs.findIndex((r) => r.programmeId === programmeId);
  if (idx >= 0) db.runs[idx] = run;
  else db.runs.push(run);
  if (p.status === 'REQUIREMENTS_SET') p.status = 'PREDICTED';
  p.requirementsChangedSincePrediction = false;
  writeAudit(adminActor(), 'PREDICTION_GENERATED', `PROGRAMME#${programmeId}`, `Ranked ${run.rankedCount}, excluded ${run.excludedCount}`);
  return run;
}

function programmeDetail(programmeId: number): ProgrammeDetail {
  const programme = programmeById(programmeId);
  if (!programme) throw new ApiError(404, 'Programme not found');
  const allocation = db.allocations.find((a) => a.programmeId === programmeId) ?? null;
  const auditTrail = db.audit.filter((a) => a.affectedRecord === `PROGRAMME#${programmeId}`);
  return { programme, allocation, hasRun: db.runs.some((r) => r.programmeId === programmeId), auditTrail };
}

// --- allocations ----------------------------------------------------------

function listAllocations(f: AllocationFilters): Paginated<AllocationListItem> {
  let items = [...db.allocations].sort((a, b) => dayjs(b.approvalDate).valueOf() - dayjs(a.approvalDate).valueOf());
  if (str(f.status)) items = items.filter((a) => a.status === f.status);
  if (num(f.trainerId) !== undefined) items = items.filter((a) => a.trainerId === num(f.trainerId));
  if (str(f.from)) items = items.filter((a) => dayjs(a.approvalDate).isAfter(dayjs(f.from).subtract(1, 'day')));
  if (str(f.to)) items = items.filter((a) => dayjs(a.approvalDate).isBefore(dayjs(f.to).add(1, 'day')));
  const rows = items.map(toAllocationListItem);
  return paginate(rows, num(f.page), num(f.pageSize) ?? 15);
}

function approveAllocation(input: ApproveAllocationInput): Allocation {
  const programme = programmeById(input.programmeId);
  const run = db.runs.find((r) => r.programmeId === input.programmeId);
  const prediction = run?.predictions.find((p) => p.predictionId === input.predictionId);
  if (!programme || !prediction) throw new ApiError(404, 'Prediction not found');
  const allocationId = Math.max(...db.allocations.map((a) => a.allocationId), 400) + 1;
  const admin = adminActor();
  const allocation: Allocation = {
    allocationId,
    predictionId: prediction.predictionId,
    programmeId: input.programmeId,
    trainerId: prediction.trainerId,
    registryNumber: `TPS/ALL/2026/${String(allocationId - 400).padStart(4, '0')}`,
    approvedBy: admin.userId,
    approvedByName: admin.fullName,
    approvedByRank: 'SSP',
    status: 'PENDING_TRAINER',
    approvalDate: NOW().toISOString(),
    remarks: input.remarks,
    frozenScore: prediction.predictionScore,
    frozenBreakdown: prediction.breakdown,
    frozenRankPosition: prediction.rankPosition,
    frozenWeights: input.weights,
    frozenRationale: prediction.rationale,
    weightsWereSimulated: input.weightsWereSimulated,
    declineReason: null,
    declinedAt: null,
    respondedAt: null,
  };
  db.allocations.push(allocation);
  programme.status = 'AWAITING_RESPONSE';
  writeAudit(admin, 'ALLOCATION_APPROVED', `ALLOCATION#${allocationId}`, `Approved ${allocation.registryNumber}`);
  return allocation;
}

function declineAssignment(allocationId: number, input: DeclineAssignmentInput): Allocation {
  const a = db.allocations.find((x) => x.allocationId === allocationId);
  if (!a) throw new ApiError(404, 'Allocation not found');
  a.status = 'DECLINED';
  a.declineReason = input.reason;
  a.declinedAt = NOW().toISOString();
  a.respondedAt = a.declinedAt;
  writeAudit(db.users[2]!, 'ASSIGNMENT_DECLINED', `ALLOCATION#${allocationId}`, input.reason);
  return a;
}

function acceptAssignment(allocationId: number): Allocation {
  const a = db.allocations.find((x) => x.allocationId === allocationId);
  if (!a) throw new ApiError(404, 'Allocation not found');
  a.status = 'CONFIRMED';
  a.respondedAt = NOW().toISOString();
  const p = programmeById(a.programmeId);
  if (p) p.status = 'ALLOCATED';
  writeAudit(db.users[2]!, 'ASSIGNMENT_ACCEPTED', `ALLOCATION#${allocationId}`, 'Accepted assignment');
  return a;
}

/** FR-08 — promote the next-ranked candidate using the SAME ranking; no re-run. */
function promoteNext(allocationId: number): Allocation {
  const declined = db.allocations.find((x) => x.allocationId === allocationId);
  if (!declined) throw new ApiError(404, 'Allocation not found');
  const run = db.runs.find((r) => r.programmeId === declined.programmeId);
  const nextPred = run?.predictions.find((p) => p.rankPosition === declined.frozenRankPosition + 1);
  if (!run || !nextPred) throw new ApiError(409, 'No further candidate to promote');
  const admin = adminActor();
  const allocationId2 = Math.max(...db.allocations.map((a) => a.allocationId)) + 1;
  const allocation: Allocation = {
    allocationId: allocationId2,
    predictionId: nextPred.predictionId,
    programmeId: declined.programmeId,
    trainerId: nextPred.trainerId,
    registryNumber: `TPS/ALL/2026/${String(allocationId2 - 400).padStart(4, '0')}`,
    approvedBy: admin.userId,
    approvedByName: admin.fullName,
    approvedByRank: 'SSP',
    status: 'PENDING_TRAINER',
    approvalDate: NOW().toISOString(),
    remarks: `Promoted after ${declined.registryNumber} was declined.`,
    frozenScore: nextPred.predictionScore,
    frozenBreakdown: nextPred.breakdown,
    frozenRankPosition: nextPred.rankPosition,
    frozenWeights: declined.frozenWeights,
    frozenRationale: nextPred.rationale,
    weightsWereSimulated: declined.weightsWereSimulated,
    declineReason: null,
    declinedAt: null,
    respondedAt: null,
  };
  db.allocations.push(allocation);
  writeAudit(admin, 'ALLOCATION_APPROVED', `ALLOCATION#${allocationId2}`, 'Promoted next-ranked candidate (ranking reused, no re-run)');
  return allocation;
}

// --- evaluations ----------------------------------------------------------

function listEvaluations() {
  const awaiting = db.allocations.filter((a) => a.status === 'CONDUCTED').map(toAllocationListItem);
  const recorded = [...db.evaluations]
    .sort((a, b) => dayjs(b.evaluationDate).valueOf() - dayjs(a.evaluationDate).valueOf())
    .slice(0, 50);
  return { awaiting, recorded };
}

function recordEvaluation(input: EvaluationInput): PerformanceEvaluation {
  const alloc = db.allocations.find((a) => a.allocationId === input.allocationId);
  if (!alloc) throw new ApiError(404, 'Allocation not found');
  if (alloc.status !== 'CONDUCTED') throw new ApiError(409, 'Training has not been conducted yet');
  const trainer = trainerById().get(alloc.trainerId)!;
  const programme = programmeById(alloc.programmeId)!;
  const evaluation: PerformanceEvaluation = {
    evaluationId: Math.max(...db.evaluations.map((e) => e.evaluationId), 0) + 1,
    allocationId: alloc.allocationId,
    trainerId: alloc.trainerId,
    programmeId: alloc.programmeId,
    programmeTitle: programme.title,
    scoreAwarded: input.scoreAwarded,
    evaluatorComments: input.evaluatorComments,
    evaluatedBy: adminActor().userId,
    evaluatedByName: adminActor().fullName,
    evaluationDate: input.evaluationDate,
  };
  db.evaluations.push(evaluation);
  trainer.performanceHistory.push(evaluation);
  alloc.status = 'EVALUATED';
  programme.status = 'EVALUATED';
  writeAudit(adminActor(), 'EVALUATION_RECORDED', `EVALUATION#${evaluation.evaluationId}`, `Recorded ${input.scoreAwarded.toFixed(1)}/5`);
  return evaluation;
}

// --- reports --------------------------------------------------------------

function buildReport(kind: string, params: Record<string, unknown>) {
  const from = str(params.from);
  const to = str(params.to);
  const category = str(params.category);
  const inRange = (date: string) =>
    (!from || dayjs(date).isAfter(dayjs(from).subtract(1, 'day'))) &&
    (!to || dayjs(date).isBefore(dayjs(to).add(1, 'day')));

  if (kind === 'utilisation') {
    const rows: UtilisationReportRow[] = trainerUtilisation()
      .map((b) => {
        const t = db.trainers.find((x) => x.fullName === b.label)!;
        return {
          trainerId: t.trainerId,
          trainerName: t.fullName,
          rank: t.policeRank,
          forceNumber: t.forceNumber,
          allocations: b.value,
          lastAssigned: t.lastAssignedDate,
        };
      })
      .slice(0, 20);
    const response: ReportResponse<UtilisationReportRow> = {
      rows,
      chart: rows.slice(0, 10).map((r) => ({ label: r.trainerName, value: r.allocations })),
      generatedAt: NOW().toISOString(),
      filters: { from, to, category },
    };
    return response;
  }
  if (kind === 'allocations') {
    let source = db.allocations.filter((a) => inRange(a.approvalDate));
    if (category) source = source.filter((a) => programmeById(a.programmeId)?.category === category);
    const tById = trainerById();
    const rows: AllocationHistoryRow[] = source.map((a) => {
      const p = programmeById(a.programmeId);
      const t = tById.get(a.trainerId);
      return {
        registryNumber: a.registryNumber,
        programmeTitle: p?.title ?? '—',
        trainerName: t?.fullName ?? '—',
        approvedByName: a.approvedByName,
        approvalDate: a.approvalDate,
        status: a.status,
        score: a.frozenScore,
      };
    });
    const response: ReportResponse<AllocationHistoryRow> = {
      rows,
      chart: performanceByQuarter(),
      generatedAt: NOW().toISOString(),
      filters: { from, to, category },
    };
    return response;
  }
  // performance
  const byQ = new Map<string, number[]>();
  for (const e of db.evaluations) {
    if (!inRange(e.evaluationDate)) continue;
    const q = quarterLabel(dayjs(e.evaluationDate));
    (byQ.get(q) ?? byQ.set(q, []).get(q)!).push(e.scoreAwarded);
  }
  const rows: PerformanceTrendRow[] = [...byQ.entries()]
    .map(([quarter, xs]) => ({
      quarter,
      meanScore: Math.round((xs.reduce((s, x) => s + x, 0) / xs.length) * 10) / 10,
      evaluationCount: xs.length,
    }))
    .sort((a, b) => a.quarter.localeCompare(b.quarter));
  const response: ReportResponse<PerformanceTrendRow> = {
    rows,
    chart: rows.map((r) => ({ label: r.quarter, value: r.meanScore })),
    generatedAt: NOW().toISOString(),
    filters: { from, to, category },
  };
  return response;
}

// --- users ----------------------------------------------------------------

function createUser(input: UserCreateInput): User {
  const userId = Math.max(...db.users.map((u) => u.userId)) + 1;
  const roleId = { TRAINING_ADMINISTRATOR: 1, TRAINING_OFFICER: 2, TRAINER: 3, SYSTEM_ADMINISTRATOR: 4 }[input.role];
  const user: User = {
    userId,
    username: input.username,
    fullName: input.fullName,
    email: input.email,
    roleId,
    role: input.role,
    accountStatus: 'ACTIVE',
    createdAt: NOW().toISOString(),
    lastLoginAt: null,
  };
  db.users.push(user);
  writeAudit(db.users[3]!, 'USER_CREATED', `USER#${userId}`, `Created ${input.username}`);
  return user;
}

function updateUser(userId: number, input: UserUpdateInput): User {
  const user = db.users.find((u) => u.userId === userId);
  if (!user) throw new ApiError(404, 'User not found');
  const roleChanged = input.role && input.role !== user.role;
  Object.assign(user, input);
  if (input.role) user.roleId = { TRAINING_ADMINISTRATOR: 1, TRAINING_OFFICER: 2, TRAINER: 3, SYSTEM_ADMINISTRATOR: 4 }[input.role];
  const action: AuditAction =
    input.accountStatus === 'DEACTIVATED' ? 'USER_DEACTIVATED' : roleChanged ? 'ROLE_CHANGED' : 'USER_MODIFIED';
  writeAudit(db.users[3]!, action, `USER#${userId}`, `Updated ${user.username}`);
  return user;
}

// --- audit ----------------------------------------------------------------

function listAudit(f: AuditFilters): Paginated<AuditLogEntry> {
  let items = db.audit;
  if (str(f.action)) items = items.filter((a) => a.actionPerformed === f.action);
  if (num(f.userId) !== undefined) items = items.filter((a) => a.userId === num(f.userId));
  if (str(f.role)) items = items.filter((a) => a.userRole === f.role);
  if (str(f.from)) items = items.filter((a) => dayjs(a.timestamp).isAfter(dayjs(f.from).subtract(1, 'day')));
  if (str(f.to)) items = items.filter((a) => dayjs(a.timestamp).isBefore(dayjs(f.to).add(1, 'day')));
  return paginate(items, num(f.page), num(f.pageSize) ?? 50);
}

// --- notifications --------------------------------------------------------

function markAllRead(recipientId?: number): { ok: true } {
  db.notifications.forEach((n) => {
    if (!recipientId || n.recipientId === recipientId) n.status = 'READ';
  });
  return { ok: true };
}
function markRead(id: number): Notification {
  const n = db.notifications.find((x) => x.notificationId === id);
  if (!n) throw new ApiError(404, 'Notification not found');
  n.status = 'READ';
  return n;
}

// --- policy ---------------------------------------------------------------

function saveScoringPolicy(body: Record<string, unknown>) {
  const weights = body.weights as typeof DEFAULT_WEIGHTS;
  db.weightPolicy.weights = weights;
  db.weightPolicy.changedAt = NOW().toISOString();
  db.weightPolicy.history.unshift({
    changedBy: db.users[3]!.fullName,
    changedAt: NOW().toISOString(),
    note: 'Updated policy weighting.',
  });
  writeAudit(db.users[3]!, 'WEIGHTS_SAVED', 'POLICY', 'Saved scoring-policy weights');
  return db.weightPolicy;
}
