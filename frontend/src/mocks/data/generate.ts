/**
 * Deterministic mock dataset (§8). One Rng(MOCK_SEED) threaded through the whole
 * build so the data is byte-identical on every reload. Generation order is fixed
 * and must not be reshuffled, or the seed drifts.
 *
 * Story beats wired in per §8.10: a featured PREDICTED cybercrime course with a
 * tight top two (within ~1.4 pts), a zero-evaluation LOW-confidence candidate, a
 * trainer-declined allocation, a CONDUCTED-not-yet-EVALUATED course, several
 * EVALUATED courses for trends, and real Exclusion-Ledger content.
 */
import dayjs from 'dayjs';
import type {
  Allocation,
  AuditAction,
  AuditLogEntry,
  Notification,
  PerformanceEvaluation,
  PoliceRank,
  Prediction,
  PredictionRun,
  ProficiencyLevel,
  ProgrammeStatus,
  Qualification,
  QualificationLevel,
  Role,
  Specialization,
  Trainer,
  TrainingProgramme,
  User,
} from '@/types/domain';
import {
  DEFAULT_WEIGHTS,
  DIRECTORATES,
  INSTITUTIONS,
  POLICE_INSTITUTIONS,
  PHONE_PREFIXES,
  SPECIALIZATIONS,
  SPECIALIZATION_CATEGORY,
  STATIONS,
  TRAINER_RANKS,
} from '@/lib/constants';
import { runPrediction } from '@/lib/scoring';
import { Rng, MOCK_SEED } from '../seed';
import { makeEmail, makeName } from './names';

export interface WeightPolicyRecord {
  weights: typeof DEFAULT_WEIGHTS;
  changedBy: string;
  changedByRank: PoliceRank;
  changedAt: string;
  history: { changedBy: string; changedAt: string; note: string }[];
}

export interface MockDb {
  roles: Role[];
  users: User[];
  trainers: Trainer[];
  programmes: TrainingProgramme[];
  runs: PredictionRun[];
  predictions: Prediction[];
  allocations: Allocation[];
  evaluations: PerformanceEvaluation[];
  audit: AuditLogEntry[];
  notifications: Notification[];
  weightPolicy: WeightPolicyRecord;
  featuredProgrammeId: number;
  /** Password shared by every seeded demo account (mocks only). */
  demoPassword: string;
}

const NOW = dayjs('2026-07-22');
const iso = (d: dayjs.Dayjs) => d.toISOString();
const pad = (n: number, w = 4) => String(n).padStart(w, '0');

const PROGRAMME_TEMPLATES: { title: string; specialization: string; category: string }[] = [
  { title: 'Basic Cybercrime Investigation Course — Intake {n}', specialization: 'Cybercrime Investigation', category: 'Investigations' },
  { title: 'Community Policing Refresher, {region} Region', specialization: 'Community Policing', category: 'Community Policing' },
  { title: 'Public Order Management Pre-Deployment Training', specialization: 'Public Order Management', category: 'Public Order' },
  { title: 'Scene of Crime Management Course', specialization: 'Scene of Crime Management', category: 'Forensics' },
  { title: 'Digital Forensics Level 2', specialization: 'Digital Forensics', category: 'Forensics' },
  { title: 'Traffic Law Enforcement and Road Safety Course', specialization: 'Traffic Management and Road Safety', category: 'Traffic' },
  { title: 'Anti-Corruption and Professional Standards Seminar', specialization: 'Anti-Corruption', category: 'Professional Standards' },
  { title: 'Child and Family Protection Unit Training', specialization: 'Child and Family Protection', category: 'Child Protection' },
  { title: 'Marine Search and Rescue Course, Kajjansi', specialization: 'Marine Operations', category: 'Marine' },
  { title: 'Intelligence Analysis Foundation Course', specialization: 'Intelligence Analysis', category: 'Intelligence' },
  { title: 'Firearms Instructor Refresher — Kabalye', specialization: 'Firearms and Tactical Training', category: 'Firearms' },
  { title: 'Records and Registry Management Workshop', specialization: 'Records and Registry Management', category: 'Records Management' },
];

const REGION_LABELS = ['Eastern', 'Northern', 'Western', 'Central', 'Karamoja', 'West Nile'];

export function generateDb(): MockDb {
  const rng = new Rng(MOCK_SEED);
  const demoPassword = 'Demo@2026';

  // --- force numbers (unique) --------------------------------------------
  const usedForce = new Set<string>();
  const makeForce = (): string => {
    let f: string;
    do {
      f = String(rng.int(40000, 49999));
    } while (usedForce.has(f));
    usedForce.add(f);
    return f;
  };
  const makePhone = (): string => {
    const prefix = rng.pick(PHONE_PREFIXES).slice(1); // drop leading 0
    const rest = `${pad(rng.int(0, 999), 3)} ${pad(rng.int(0, 999), 3)}`;
    return `+256 ${prefix} ${rest}`;
  };

  const qualYear = () => rng.int(2005, 2022);
  const makeQual = (
    id: number,
    trainerId: number,
    level: QualificationLevel,
    fromPolice: boolean,
  ): Qualification => ({
    qualificationId: id,
    trainerId,
    qualificationName:
      level === 'DOCTORATE'
        ? 'PhD, Security Studies'
        : level === 'MASTERS'
          ? 'MSc, Criminal Justice'
          : level === 'POSTGRAD_DIPLOMA'
            ? 'PG Diploma, Public Administration'
            : level === 'BACHELORS'
              ? 'BA, Social Sciences'
              : level === 'DIPLOMA'
                ? 'Diploma, Police Studies'
                : 'Certificate, Basic Policing',
    qualificationLevel: level,
    institutionName: fromPolice
      ? rng.pick([...POLICE_INSTITUTIONS])
      : rng.pick(INSTITUTIONS),
    yearObtained: qualYear(),
  });

  const roles: Role[] = [
    { roleId: 1, roleName: 'TRAINING_ADMINISTRATOR', description: 'Approves allocations and tunes weighting policy.' },
    { roleId: 2, roleName: 'TRAINING_OFFICER', description: 'Raises training requests and defines requirements.' },
    { roleId: 3, roleName: 'TRAINER', description: 'Delivers training; accepts or declines assignments.' },
    { roleId: 4, roleName: 'SYSTEM_ADMINISTRATOR', description: 'Manages users, roles, and system health.' },
  ];

  // ---------------------------------------------------------------------
  // Trainers — heroes first (curated for the featured run), then the pool.
  // ---------------------------------------------------------------------
  const trainers: Trainer[] = [];
  let qualIdSeq = 1;
  let specIdSeq = 1;

  const buildTrainer = (
    trainerId: number,
    fullName: string,
    rank: PoliceRank,
    opts: {
      years: number;
      specs: [string, ProficiencyLevel][];
      quals: [QualificationLevel, boolean][];
      availability?: Trainer['availabilityStatus'];
      currentAllocations?: number;
      profile?: number;
      directorate?: string;
      stationIdx?: number;
    },
  ): Trainer => {
    const station = STATIONS[opts.stationIdx ?? rng.int(0, STATIONS.length - 1)]!;
    const specializations: Specialization[] = opts.specs.map(([area, level]) => ({
      specializationId: specIdSeq++,
      trainerId,
      specializationArea: area,
      proficiencyLevel: level,
    }));
    const qualifications: Qualification[] = opts.quals.map(([level, police]) =>
      makeQual(qualIdSeq++, trainerId, level, police),
    );
    return {
      trainerId,
      userId: 1000 + trainerId,
      fullName,
      forceNumber: makeForce(),
      policeRank: rank,
      station: station.name,
      region: station.region,
      directorate: opts.directorate ?? rng.pick(DIRECTORATES),
      yearsExperience: opts.years,
      availabilityStatus: opts.availability ?? 'AVAILABLE',
      contactNumber: makePhone(),
      qualifications,
      specializations,
      performanceHistory: [],
      currentAllocations: opts.currentAllocations ?? 0,
      lastAssignedDate: null,
      profileCompleteness: opts.profile ?? rng.int(70, 100),
    };
  };

  // Hero trainers (§8.10). T1 is the seeded `trainer` demo account.
  trainers.push(
    buildTrainer(1, 'Sarah Mugisha', 'IP', {
      years: 13,
      specs: [['Cybercrime Investigation', 'EXPERT']],
      quals: [['MASTERS', true]],
      profile: 95,
      directorate: 'Criminal Investigations (CID)',
      stationIdx: 2,
    }),
    buildTrainer(2, 'Betty Nabirye', 'ASP', {
      years: 12,
      specs: [
        ['Cybercrime Investigation', 'ADVANCED'],
        ['Criminal Investigation', 'ADVANCED'],
      ],
      quals: [['MASTERS', true]],
      profile: 92,
      directorate: 'Criminal Investigations (CID)',
      stationIdx: 6,
    }),
    buildTrainer(3, 'Godfrey Businge', 'IP', {
      years: 10,
      specs: [['Cybercrime Investigation', 'EXPERT']],
      quals: [['BACHELORS', true]],
      profile: 85,
      directorate: 'Criminal Investigations (CID)',
      stationIdx: 3,
    }),
    buildTrainer(4, 'Ibrahim Wekesa', 'ASP', {
      years: 16,
      specs: [['Cybercrime Investigation', 'ADVANCED']],
      quals: [['MASTERS', true]],
      profile: 70,
      directorate: 'ICT Research, Planning and Innovation',
      stationIdx: 0,
    }),
  );

  // Remaining pool up to 812. Cybercrime is common (a basic course), skewed to
  // lower proficiency, so the featured run has a large eligible pool while the
  // curated heroes stay on top.
  const PROFICIENCY_POOL: readonly (readonly [ProficiencyLevel, number])[] = [
    ['BASIC', 55],
    ['INTERMEDIATE', 34],
    ['ADVANCED', 9],
    ['EXPERT', 2],
  ];
  // Cybercrime is a *basic* course — no random EXPERT so the curated heroes lead.
  const CYBER_PROFICIENCY_POOL: readonly (readonly [ProficiencyLevel, number])[] = [
    ['BASIC', 58],
    ['INTERMEDIATE', 36],
    ['ADVANCED', 6],
  ];
  const QUAL_POOL: readonly (readonly [QualificationLevel, number])[] = [
    ['CERTIFICATE', 14],
    ['DIPLOMA', 30],
    ['BACHELORS', 34],
    ['POSTGRAD_DIPLOMA', 10],
    ['MASTERS', 11],
    ['DOCTORATE', 1],
  ];
  const RANK_POOL: readonly (readonly [PoliceRank, number])[] = [
    ['AIP', 16],
    ['IP', 34],
    ['ASP', 28],
    ['SP', 15],
    ['SSP', 7],
  ];
  const AVAIL_POOL: readonly (readonly [Trainer['availabilityStatus'], number])[] = [
    ['AVAILABLE', 68],
    ['ASSIGNED', 26],
    ['UNAVAILABLE', 6],
  ];

  for (let id = 5; id <= 812; id++) {
    const name = makeName(rng);
    const rank = rng.weighted(RANK_POOL as readonly (readonly [PoliceRank, number])[]);
    const years = rng.int(3, 26);

    // Specialisations: cybercrime for ~93%, plus 0–2 others (distinct).
    const specs: [string, ProficiencyLevel][] = [];
    const hasCyber = rng.bool(0.93);
    if (hasCyber) specs.push(['Cybercrime Investigation', rng.weighted(CYBER_PROFICIENCY_POOL)]);
    const extraCount = rng.int(hasCyber ? 0 : 1, 2);
    const others = rng
      .sample(
        SPECIALIZATIONS.filter((s) => s !== 'Cybercrime Investigation'),
        extraCount,
      )
      .map((area): [string, ProficiencyLevel] => [area, rng.weighted(PROFICIENCY_POOL)]);
    specs.push(...others);

    const qCount = rng.int(1, 2);
    const quals: [QualificationLevel, boolean][] = Array.from({ length: qCount }, () => [
      rng.weighted(QUAL_POOL),
      rng.bool(0.4),
    ]);

    const availability = rng.weighted(AVAIL_POOL);
    const currentAllocations =
      availability === 'ASSIGNED' ? rng.int(1, 3) : availability === 'AVAILABLE' ? rng.int(0, 1) : rng.int(0, 2);

    trainers.push(
      buildTrainer(id, name.fullName, rank, {
        years,
        specs,
        quals,
        availability,
        currentAllocations,
        profile: rng.weighted([
          [rng.int(45, 65), 20],
          [rng.int(66, 85), 45],
          [rng.int(86, 100), 35],
        ] as const),
      }),
    );
  }

  const trainerById = new Map(trainers.map((t) => [t.trainerId, t]));

  // ---------------------------------------------------------------------
  // Users — 4 demo accounts + a spread of others across the four roles.
  // ---------------------------------------------------------------------
  const users: User[] = [
    demoUser(1, 'admin.training', 'SSP Grace Nabirye', 'TRAINING_ADMINISTRATOR', 1),
    demoUser(2, 'officer.training', 'ASP Joseph Okello', 'TRAINING_OFFICER', 2),
    demoUser(3, 'trainer', 'IP Sarah Mugisha', 'TRAINER', 3, 1001), // links hero T1 (userId 1001)
    demoUser(4, 'sysadmin', 'SP Denis Byaruhanga', 'SYSTEM_ADMINISTRATOR', 4),
  ];
  function demoUser(
    userId: number,
    username: string,
    fullName: string,
    role: User['role'],
    roleId: number,
    linkUserId?: number,
  ): User {
    return {
      userId: linkUserId ?? userId,
      username,
      fullName,
      email: makeEmail(fullName.split(' ')[1] ?? fullName, fullName.split(' ')[2] ?? ''),
      roleId,
      role,
      accountStatus: 'ACTIVE',
      createdAt: iso(NOW.subtract(rng.int(120, 400), 'day')),
      lastLoginAt: iso(NOW.subtract(rng.int(0, 6), 'day').subtract(rng.int(0, 20), 'hour')),
    };
  }
  const OTHER_ROLES: [User['role'], number][] = [
    ['TRAINING_OFFICER', 2],
    ['TRAINER', 3],
    ['TRAINING_ADMINISTRATOR', 1],
    ['SYSTEM_ADMINISTRATOR', 4],
  ];
  for (let i = 5; i <= 40; i++) {
    const name = makeName(rng);
    const [role, roleId] = OTHER_ROLES[i % OTHER_ROLES.length]!;
    const rank = rng.pick(TRAINER_RANKS);
    const status = rng.weighted([
      ['ACTIVE', 88],
      ['SUSPENDED', 6],
      ['DEACTIVATED', 6],
    ] as const) as User['accountStatus'];
    users.push({
      userId: i,
      username: `${name.given}.${name.surname}`.toLowerCase(),
      fullName: `${rank} ${name.fullName}`,
      email: makeEmail(name.given, name.surname),
      roleId,
      role,
      accountStatus: status,
      createdAt: iso(NOW.subtract(rng.int(60, 500), 'day')),
      lastLoginAt:
        status === 'DEACTIVATED'
          ? iso(NOW.subtract(rng.int(30, 120), 'day'))
          : iso(NOW.subtract(rng.int(0, 20), 'day')),
    });
  }
  const adminUser = users[0]!; // SSP Grace Nabirye
  const officerUser = users[1]!;

  // ---------------------------------------------------------------------
  // Programmes — 46 across all statuses.
  // ---------------------------------------------------------------------
  const programmes: TrainingProgramme[] = [];

  // Featured programme (id 1) — PREDICTED cybercrime course.
  programmes.push({
    programmeId: 1,
    title: 'Basic Cybercrime Investigation Course — Intake 14',
    category: 'Investigations',
    requiredSpecialization: 'Cybercrime Investigation',
    minimumExperience: 3,
    minimumQualification: null,
    startDate: iso(NOW.add(24, 'day')),
    endDate: iso(NOW.add(35, 'day')),
    location: 'Police Training School Kabalye, Masindi',
    status: 'PREDICTED',
    createdBy: officerUser.userId,
    createdByName: officerUser.fullName,
    createdAt: iso(NOW.subtract(12, 'day')),
    requirementsSetAt: iso(NOW.subtract(10, 'day')),
    requirementsChangedSincePrediction: false,
  });

  // Status plan for the remaining 45.
  const STATUS_PLAN: ProgrammeStatus[] = [
    'PREDICTED',
    'PREDICTED', // dashboard shows 3 predictions ready (incl. featured)
    'DRAFT',
    'DRAFT',
    'REQUIREMENTS_SET',
    'REQUIREMENTS_SET',
    'REQUIREMENTS_SET',
    'AWAITING_RESPONSE',
    'AWAITING_RESPONSE',
    'ALLOCATED',
    'ALLOCATED',
    'ALLOCATED',
    'CONDUCTED', // one CONDUCTED-not-EVALUATED (index 0 of conducted)
    'CONDUCTED',
    'CANCELLED',
  ];
  const EVALUATED_COUNT = 45 - STATUS_PLAN.length; // remainder are EVALUATED (past)
  for (let i = 0; i < EVALUATED_COUNT; i++) STATUS_PLAN.push('EVALUATED');

  let intake = 15;
  STATUS_PLAN.forEach((status, i) => {
    const programmeId = i + 2;
    const tpl = PROGRAMME_TEMPLATES[(i + 1) % PROGRAMME_TEMPLATES.length]!;
    const title = tpl.title
      .replace('{n}', String(intake++))
      .replace('{region}', rng.pick(REGION_LABELS));

    // Dates by status: EVALUATED/CONDUCTED in the past; others upcoming.
    const past = status === 'EVALUATED' || status === 'CONDUCTED' || status === 'ALLOCATED';
    const startOffset = past ? -rng.int(30, 420) : rng.int(10, 90);
    const start = NOW.add(startOffset, 'day');
    const end = start.add(rng.int(4, 12), 'day');

    const minQual = rng.bool(0.3)
      ? (rng.pick(['DIPLOMA', 'BACHELORS']) as QualificationLevel)
      : null;

    programmes.push({
      programmeId,
      title,
      category: tpl.category,
      requiredSpecialization: tpl.specialization,
      minimumExperience: rng.pick([2, 3, 5, 8]),
      minimumQualification: minQual,
      startDate: iso(start),
      endDate: iso(end),
      location: rng.pick(STATIONS).name,
      status,
      createdBy: officerUser.userId,
      createdByName: officerUser.fullName,
      createdAt: iso(start.subtract(rng.int(14, 40), 'day')),
      requirementsSetAt: status === 'DRAFT' ? null : iso(start.subtract(rng.int(8, 20), 'day')),
      requirementsChangedSincePrediction: false,
    });
  });
  const featuredProgrammeId = 1;

  // ---------------------------------------------------------------------
  // Evaluations — hero history + a spread across the pool (~47 total).
  // Attached to trainer.performanceHistory. Tied to EVALUATED programmes so
  // the PERFORMANCE relevance test can find "same-category" courses.
  // ---------------------------------------------------------------------
  const evaluations: PerformanceEvaluation[] = [];
  let evalSeq = 1;
  const evaluatedProgrammes = programmes.filter((p) => p.status === 'EVALUATED');
  const investigationsProgrammes = evaluatedProgrammes.filter((p) => p.category === 'Investigations');
  const pickPastProgramme = (category: string): TrainingProgramme => {
    const inCat = evaluatedProgrammes.filter((p) => p.category === category);
    const pool = inCat.length > 0 ? inCat : evaluatedProgrammes;
    return pool.length > 0 ? rng.pick(pool) : programmes[programmes.length - 1]!;
  };

  const addEval = (trainer: Trainer, score: number, programme: TrainingProgramme, ageDays: number) => {
    const ev: PerformanceEvaluation = {
      evaluationId: evalSeq,
      allocationId: 90000 + evalSeq, // synthetic historical allocation
      trainerId: trainer.trainerId,
      programmeId: programme.programmeId,
      programmeTitle: programme.title,
      scoreAwarded: score,
      evaluatorComments: rng.pick([
        'Clear delivery; strong command of the subject.',
        'Well prepared; engaged the trainees throughout.',
        'Good practical exercises; time-keeping could improve.',
        'Excellent case studies drawn from real investigations.',
        'Solid session; handled questions confidently.',
      ]),
      evaluatedBy: adminUser.userId,
      evaluatedByName: adminUser.fullName,
      evaluationDate: iso(NOW.subtract(ageDays, 'day')),
    };
    evaluations.push(ev);
    trainer.performanceHistory.push(ev);
    evalSeq++;
  };

  const investProg = () =>
    investigationsProgrammes.length > 0 ? rng.pick(investigationsProgrammes) : pickPastProgramme('Investigations');

  // Hero evaluations (curated means).
  [4.5, 4.5, 5.0, 4.5, 4.5, 4.5].forEach((s, i) => addEval(trainerById.get(1)!, s, investProg(), 60 + i * 40));
  [5.0, 5.0, 5.0, 4.5, 5.0].forEach((s, i) => addEval(trainerById.get(2)!, s, investProg(), 50 + i * 45));
  [4.5, 4.5, 4.0].forEach((s, i) => addEval(trainerById.get(3)!, s, investProg(), 70 + i * 60));
  // T4 (id 4) intentionally has NO evaluations -> LOW confidence.

  // Spread the remaining evaluations across other eligible trainers whose PRIMARY
  // specialisation is NOT Investigations — so none gains *relevant* performance in
  // the featured cybercrime run, keeping the curated heroes as the top two.
  const historyTargets = rng.sample(
    trainers.filter(
      (t) =>
        t.trainerId > 4 &&
        t.availabilityStatus !== 'UNAVAILABLE' &&
        t.specializations[0] &&
        SPECIALIZATION_CATEGORY[t.specializations[0].specializationArea] !== 'Investigations',
    ),
    16,
  );
  for (const t of historyTargets) {
    const n = rng.int(1, 3);
    const cat = t.specializations[0] ? SPECIALIZATION_CATEGORY[t.specializations[0].specializationArea] : undefined;
    for (let k = 0; k < n; k++) {
      addEval(t, rng.pick([3.0, 3.5, 4.0, 4.0, 4.5, 4.5, 5.0]), pickPastProgramme(cat ?? 'Investigations'), rng.int(40, 500));
    }
  }

  // ---------------------------------------------------------------------
  // Prediction runs — computed for programmes at PREDICTED and beyond.
  // ---------------------------------------------------------------------
  const runs: PredictionRun[] = [];
  const predictions: Prediction[] = [];
  const categoryByProgramme = new Map(programmes.map((p) => [p.programmeId, p.category]));

  const relevanceFor = (programme: TrainingProgramme) => (ev: PerformanceEvaluation) =>
    categoryByProgramme.get(ev.programmeId) === programme.category;

  const runFor = (programme: TrainingProgramme, elapsedMs: number): PredictionRun => {
    const run = runPrediction({
      programme,
      trainers,
      weights: DEFAULT_WEIGHTS,
      isRelevantEvaluation: relevanceFor(programme),
      now: NOW.toDate(),
      generatedDate: iso(NOW.subtract(rng.int(1, 9), 'day')),
      elapsedMs,
    });
    runs.push(run);
    predictions.push(...run.predictions);
    return run;
  };

  const PREDICTED_PLUS: ProgrammeStatus[] = [
    'PREDICTED',
    'AWAITING_RESPONSE',
    'ALLOCATED',
    'CONDUCTED',
    'EVALUATED',
  ];
  const runByProgramme = new Map<number, PredictionRun>();
  for (const p of programmes) {
    if (PREDICTED_PLUS.includes(p.status)) {
      const elapsed = p.programmeId === featuredProgrammeId ? 1400 : rng.int(900, 2400);
      runByProgramme.set(p.programmeId, runFor(p, elapsed));
    }
  }

  // ---------------------------------------------------------------------
  // Allocations — approved decisions with a frozen Decision Receipt payload.
  // ---------------------------------------------------------------------
  const allocations: Allocation[] = [];
  let allocSeq = 400;
  const makeAllocation = (
    programme: TrainingProgramme,
    prediction: Prediction,
    status: Allocation['status'],
    overrides: Partial<Allocation> = {},
  ): Allocation => {
    allocSeq++;
    const trainer = trainerById.get(prediction.trainerId)!;
    const approvalDate = iso(dayjs(prediction.generatedDate).add(rng.int(1, 4), 'day'));
    const base: Allocation = {
      allocationId: allocSeq,
      predictionId: prediction.predictionId,
      programmeId: programme.programmeId,
      trainerId: trainer.trainerId,
      registryNumber: `TPS/ALL/2026/${pad(allocSeq - 400)}`,
      approvedBy: adminUser.userId,
      approvedByName: adminUser.fullName,
      approvedByRank: 'SSP',
      status,
      approvalDate,
      remarks: rng.pick(['Approved as recommended.', 'Best fit for the intake.', '']),
      frozenScore: prediction.predictionScore,
      frozenBreakdown: prediction.breakdown,
      frozenRankPosition: prediction.rankPosition,
      frozenWeights: { ...DEFAULT_WEIGHTS },
      frozenRationale: prediction.rationale,
      weightsWereSimulated: false,
      declineReason: null,
      declinedAt: null,
      respondedAt: null,
      ...overrides,
    };
    allocations.push(base);
    return base;
  };

  for (const p of programmes) {
    const run = runByProgramme.get(p.programmeId);
    if (!run || run.predictions.length === 0) continue;
    const top = run.predictions[0]!;
    if (p.status === 'AWAITING_RESPONSE') {
      makeAllocation(p, top, 'PENDING_TRAINER', { respondedAt: null });
    } else if (p.status === 'ALLOCATED') {
      makeAllocation(p, top, 'CONFIRMED', {
        respondedAt: iso(dayjs(top.generatedDate).add(3, 'day')),
      });
    } else if (p.status === 'CONDUCTED') {
      makeAllocation(p, top, 'CONDUCTED', {
        respondedAt: iso(dayjs(top.generatedDate).add(2, 'day')),
      });
    } else if (p.status === 'EVALUATED') {
      makeAllocation(p, top, 'EVALUATED', {
        respondedAt: iso(dayjs(top.generatedDate).add(2, 'day')),
      });
    }
  }

  // The declined-allocation story beat (§8.10): the first AWAITING_RESPONSE
  // programme's top candidate declined with a real reason.
  const awaiting = programmes.find((p) => p.status === 'AWAITING_RESPONSE');
  if (awaiting) {
    const run = runByProgramme.get(awaiting.programmeId);
    const alloc = allocations.find((a) => a.programmeId === awaiting.programmeId);
    if (run && alloc) {
      alloc.status = 'DECLINED';
      alloc.declineReason = 'Committed to court testimony in Jinja for the same period.';
      alloc.declinedAt = iso(dayjs(alloc.approvalDate).add(2, 'day'));
      alloc.respondedAt = alloc.declinedAt;
    }
  }

  // ---------------------------------------------------------------------
  // Audit log — every seeded decision, plus routine sign-in/report activity.
  // ---------------------------------------------------------------------
  const audit: AuditLogEntry[] = [];
  let logSeq = 1;
  const ip = () => `10.20.${rng.int(0, 40)}.${rng.int(2, 254)}`;
  const addAudit = (
    user: User,
    action: AuditAction,
    affectedRecord: string,
    detail: string,
    when: dayjs.Dayjs,
  ) => {
    audit.push({
      logId: logSeq++,
      userId: user.userId,
      userName: user.fullName,
      userRole: user.role,
      actionPerformed: action,
      timestamp: iso(when),
      affectedRecord,
      detail,
      ipAddress: ip(),
    });
  };

  // Decision + lifecycle entries from the seeded records.
  for (const p of programmes) {
    const created = dayjs(p.createdAt);
    addAudit(officerUser, 'PROGRAMME_CREATED', `PROGRAMME#${p.programmeId}`, `Created "${p.title}"`, created);
    if (p.requirementsSetAt)
      addAudit(officerUser, 'REQUIREMENTS_DEFINED', `PROGRAMME#${p.programmeId}`, `Requirements defined for "${p.title}"`, dayjs(p.requirementsSetAt));
  }
  for (const run of runs) {
    addAudit(
      adminUser,
      'PREDICTION_GENERATED',
      `PROGRAMME#${run.programmeId}`,
      `Ranked ${run.rankedCount}, excluded ${run.excludedCount}, in ${(run.elapsedMs / 1000).toFixed(1)}s`,
      dayjs(run.generatedDate),
    );
  }
  for (const a of allocations) {
    addAudit(adminUser, 'ALLOCATION_APPROVED', `ALLOCATION#${a.allocationId}`, `Approved ${a.registryNumber}`, dayjs(a.approvalDate));
    if (a.status === 'DECLINED' && a.declinedAt)
      addAudit(users[2]!, 'ASSIGNMENT_DECLINED', `ALLOCATION#${a.allocationId}`, a.declineReason ?? '', dayjs(a.declinedAt));
  }
  for (const ev of evaluations)
    addAudit(adminUser, 'EVALUATION_RECORDED', `EVALUATION#${ev.evaluationId}`, `Recorded ${ev.scoreAwarded.toFixed(1)}/5`, dayjs(ev.evaluationDate));

  // Backfill routine activity up to ~600 entries.
  const actionPool: [AuditAction, string][] = [
    ['LOGIN_SUCCESS', 'Signed in'],
    ['LOGIN_FAILED', 'Failed sign-in attempt'],
    ['LOGOUT', 'Signed out'],
    ['REPORT_EXPORTED', 'Exported a report to PDF'],
    ['WEIGHTS_SIMULATED', 'Simulated weighting in the Weight Studio'],
    ['UNAUTHORISED_ATTEMPT', 'Blocked access to a restricted route'],
  ];
  while (audit.length < 600) {
    const user = rng.pick(users);
    const [action, detail] = rng.pick(actionPool);
    addAudit(user, action, `SESSION#${rng.int(1000, 9999)}`, detail, NOW.subtract(rng.int(0, 45), 'day').subtract(rng.int(0, 1400), 'minute'));
  }
  audit.sort((a, b) => dayjs(b.timestamp).valueOf() - dayjs(a.timestamp).valueOf());
  audit.forEach((entry, i) => (entry.logId = audit.length - i));

  // ---------------------------------------------------------------------
  // Notifications — 18, for the trainer and administrator demo accounts.
  // ---------------------------------------------------------------------
  const notifications: Notification[] = [];
  const notify = (
    recipientId: number,
    message: string,
    type: Notification['type'],
    ageHours: number,
    linkTo: string | null,
    read = false,
  ) => {
    notifications.push({
      notificationId: notifications.length + 1,
      recipientId,
      message,
      type,
      sentDate: iso(NOW.subtract(ageHours, 'hour')),
      status: read ? 'READ' : 'UNREAD',
      linkTo,
    });
  };
  notify(1001, 'You have a pending assignment: Digital Forensics Level 2.', 'ASSIGNMENT', 5, '/my-assignments');
  notify(1001, 'Your evaluation for Scene of Crime Management Course was recorded (4.5/5).', 'EVALUATION', 40, '/my-performance', true);
  notify(adminUser.userId, 'A trainer declined an allocation and needs your review.', 'APPROVAL', 8, '/allocations');
  notify(adminUser.userId, '3 predictions are ready for your review.', 'REMINDER', 12, '/dashboard');
  notify(officerUser.userId, 'Requirements are outstanding for 2 of your requests.', 'REMINDER', 20, '/programmes', true);
  for (let i = notifications.length; i < 18; i++) {
    const recipient = rng.pick([1001, adminUser.userId, officerUser.userId]);
    notify(
      recipient,
      rng.pick([
        'A new training request was submitted.',
        'An allocation was confirmed.',
        'A performance evaluation was recorded.',
        'System backup completed successfully.',
      ]),
      rng.pick(['SYSTEM', 'APPROVAL', 'EVALUATION', 'REMINDER'] as const),
      rng.int(24, 400),
      null,
      rng.bool(0.6),
    );
  }

  const weightPolicy: WeightPolicyRecord = {
    weights: { ...DEFAULT_WEIGHTS },
    changedBy: adminUser.fullName,
    changedByRank: 'SSP',
    changedAt: iso(NOW.subtract(60, 'day')),
    history: [
      { changedBy: adminUser.fullName, changedAt: iso(NOW.subtract(60, 'day')), note: 'Adopted standard policy weighting.' },
      { changedBy: 'SP Denis Byaruhanga', changedAt: iso(NOW.subtract(210, 'day')), note: 'Initial policy configured at go-live.' },
    ],
  };

  return {
    roles,
    users,
    trainers,
    programmes,
    runs,
    predictions,
    allocations,
    evaluations,
    audit,
    notifications,
    weightPolicy,
    featuredProgrammeId,
    demoPassword,
  };
}
