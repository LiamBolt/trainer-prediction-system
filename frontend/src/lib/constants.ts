/**
 * Domain constants and lookups (§8). Single source for labels, orderings,
 * and the scoring metadata shared by mock generation, the scoring engine,
 * and the UI.
 */
import type {
  AccountStatus,
  AllocationStatus,
  AvailabilityStatus,
  ConfidenceBand,
  CriterionKey,
  PoliceRank,
  ProficiencyLevel,
  ProgrammeStatus,
  QualificationLevel,
  RoleName,
} from '@/types/domain';

export const APP_NAME = 'Trainer Prediction System';
export const APP_ACRONYM = 'TPS';
export const APP_VERSION = import.meta.env.VITE_APP_VERSION ?? '1.0.0';
export const ORG_NAME = 'Uganda Police Force';
export const ORG_UNIT = 'ICT Research, Planning & Innovation';
export const CLASSIFICATION_LEFT = 'RESTRICTED · AUTHORISED PERSONNEL ONLY';
export const CLASSIFICATION_RIGHT = `TPS v${APP_VERSION} · © UPF 2026`;

/** Police ranks, junior -> senior (§8.1). */
export const RANK_ORDER: PoliceRank[] = [
  'PC',
  'CPL',
  'SGT',
  'AIP',
  'IP',
  'ASP',
  'SP',
  'SSP',
  'ACP',
];

export const RANK_FULL_NAMES: Record<PoliceRank, string> = {
  PC: 'Police Constable',
  CPL: 'Corporal',
  SGT: 'Sergeant',
  AIP: 'Assistant Inspector of Police',
  IP: 'Inspector of Police',
  ASP: 'Assistant Superintendent of Police',
  SP: 'Superintendent of Police',
  SSP: 'Senior Superintendent of Police',
  ACP: 'Assistant Commissioner of Police',
};

/** Trainers span AIP -> SSP (§8.1). */
export const TRAINER_RANKS: PoliceRank[] = ['AIP', 'IP', 'ASP', 'SP', 'SSP'];

export const ROLE_LABELS: Record<RoleName, string> = {
  TRAINING_ADMINISTRATOR: 'Training Administrator',
  TRAINING_OFFICER: 'Training Officer',
  TRAINER: 'Trainer',
  SYSTEM_ADMINISTRATOR: 'System Administrator',
};

export const QUALIFICATION_ORDER: QualificationLevel[] = [
  'CERTIFICATE',
  'DIPLOMA',
  'BACHELORS',
  'POSTGRAD_DIPLOMA',
  'MASTERS',
  'DOCTORATE',
];

export const QUALIFICATION_LABELS: Record<QualificationLevel, string> = {
  CERTIFICATE: 'Certificate',
  DIPLOMA: 'Diploma',
  BACHELORS: "Bachelor's degree",
  POSTGRAD_DIPLOMA: 'Postgraduate diploma',
  MASTERS: "Master's degree",
  DOCTORATE: 'Doctorate',
};

/** Highest-qualification base score (§7.1 QUALIFICATION). */
export const QUALIFICATION_SCORE: Record<QualificationLevel, number> = {
  DOCTORATE: 100,
  MASTERS: 90,
  POSTGRAD_DIPLOMA: 78,
  BACHELORS: 65,
  DIPLOMA: 50,
  CERTIFICATE: 35,
};

export const PROFICIENCY_ORDER: ProficiencyLevel[] = [
  'BASIC',
  'INTERMEDIATE',
  'ADVANCED',
  'EXPERT',
];

export const PROFICIENCY_LABELS: Record<ProficiencyLevel, string> = {
  BASIC: 'Basic',
  INTERMEDIATE: 'Intermediate',
  ADVANCED: 'Advanced',
  EXPERT: 'Expert',
};

/** Proficiency-in-required-area score (§7.1 SPECIALIZATION). */
export const PROFICIENCY_SCORE: Record<ProficiencyLevel, number> = {
  EXPERT: 100,
  ADVANCED: 85,
  INTERMEDIATE: 65,
  BASIC: 40,
};

/**
 * The five scoring criteria (§7.1), ordered by default weight (heaviest first).
 * `description` is the plain-English one-liner shown in the Weight Studio (§12.6).
 */
export interface CriterionMeta {
  key: CriterionKey;
  label: string;
  shortLabel: string;
  defaultWeight: number;
  description: string;
}

export const CRITERIA: CriterionMeta[] = [
  {
    key: 'SPECIALIZATION',
    label: 'Specialisation match',
    shortLabel: 'Specialisation',
    defaultWeight: 30,
    description:
      'How closely the trainer’s proven area of expertise matches what this course requires.',
  },
  {
    key: 'PERFORMANCE',
    label: 'Proven performance',
    shortLabel: 'Performance',
    defaultWeight: 25,
    description: 'The trainer’s average rating from courses they have delivered before.',
  },
  {
    key: 'EXPERIENCE',
    label: 'Years of service',
    shortLabel: 'Experience',
    defaultWeight: 20,
    description: 'Length of service, counted up to a twenty-year ceiling.',
  },
  {
    key: 'QUALIFICATION',
    label: 'Qualification',
    shortLabel: 'Qualification',
    defaultWeight: 15,
    description: 'The trainer’s highest formal academic or professional qualification.',
  },
  {
    key: 'AVAILABILITY',
    label: 'Availability',
    shortLabel: 'Availability',
    defaultWeight: 10,
    description: 'How much spare teaching capacity the trainer has right now.',
  },
];

export const CRITERION_ORDER: CriterionKey[] = CRITERIA.map((c) => c.key);

/**
 * Fixed criterion -> viz-ramp colour (§4.7). Mapped in DEFAULT weight order so a
 * segment keeps its colour while weights are tuned (heaviest = darkest in light).
 * CSS vars, so light/dark invert automatically.
 */
export const CRITERION_COLOR: Record<CriterionKey, string> = {
  SPECIALIZATION: 'var(--viz-1)',
  PERFORMANCE: 'var(--viz-2)',
  EXPERIENCE: 'var(--viz-3)',
  QUALIFICATION: 'var(--viz-4)',
  AVAILABILITY: 'var(--viz-5)',
};

export const CRITERION_META: Record<CriterionKey, CriterionMeta> = CRITERIA.reduce(
  (acc, c) => {
    acc[c.key] = c;
    return acc;
  },
  {} as Record<CriterionKey, CriterionMeta>,
);

export const DEFAULT_WEIGHTS: Record<CriterionKey, number> = {
  SPECIALIZATION: 30,
  PERFORMANCE: 25,
  EXPERIENCE: 20,
  QUALIFICATION: 15,
  AVAILABILITY: 10,
};

/** Weight Studio presets (§12.6) — each states what it optimises for. */
export interface WeightPreset {
  id: string;
  label: string;
  description: string;
  weights: Record<CriterionKey, number>;
}

export const WEIGHT_PRESETS: WeightPreset[] = [
  {
    id: 'standard',
    label: 'Standard policy',
    description: 'The balanced weighting approved as force policy.',
    weights: { ...DEFAULT_WEIGHTS },
  },
  {
    id: 'performance',
    label: 'Prioritise proven performance',
    description: 'Favours trainers with a strong, recent evaluation record.',
    weights: { SPECIALIZATION: 24, PERFORMANCE: 40, EXPERIENCE: 16, QUALIFICATION: 12, AVAILABILITY: 8 },
  },
  {
    id: 'specialisation',
    label: 'Prioritise specialisation depth',
    description: 'Favours the deepest expertise in the required area.',
    weights: { SPECIALIZATION: 45, PERFORMANCE: 20, EXPERIENCE: 15, QUALIFICATION: 15, AVAILABILITY: 5 },
  },
  {
    id: 'workload',
    label: 'Spread the workload',
    description: 'Favours trainers who have been assigned less recently.',
    weights: { SPECIALIZATION: 25, PERFORMANCE: 20, EXPERIENCE: 15, QUALIFICATION: 10, AVAILABILITY: 30 },
  },
];

/** Confidence band thresholds (§7.1 Stage 3). */
export const CONFIDENCE_BANDS = { HIGH: 75, MODERATE: 45 } as const;

export function confidenceBandFor(level: number): ConfidenceBand {
  if (level >= CONFIDENCE_BANDS.HIGH) return 'HIGH';
  if (level >= CONFIDENCE_BANDS.MODERATE) return 'MODERATE';
  return 'LOW';
}

/** Stations with their region (§8.2). */
export interface StationMeta {
  name: string;
  region: string;
}

export const REGIONS = [
  'Kampala Metropolitan',
  'Central',
  'Eastern',
  'Northern',
  'Western',
  'West Nile',
  'Karamoja',
] as const;

export const STATIONS: StationMeta[] = [
  { name: 'Central Police Station Kampala', region: 'Kampala Metropolitan' },
  { name: 'Old Kampala', region: 'Kampala Metropolitan' },
  { name: 'Kira Road', region: 'Kampala Metropolitan' },
  { name: 'Jinja Road', region: 'Kampala Metropolitan' },
  { name: 'Katwe', region: 'Kampala Metropolitan' },
  { name: 'Kabalagala', region: 'Kampala Metropolitan' },
  { name: 'Naguru', region: 'Kampala Metropolitan' },
  { name: 'Nsambya', region: 'Kampala Metropolitan' },
  { name: 'Kibuli', region: 'Kampala Metropolitan' },
  { name: 'Wandegeya', region: 'Kampala Metropolitan' },
  { name: 'Ntinda', region: 'Kampala Metropolitan' },
  { name: 'Kawempe', region: 'Kampala Metropolitan' },
  { name: 'Nateete', region: 'Kampala Metropolitan' },
  { name: 'Entebbe', region: 'Central' },
  { name: 'Mukono', region: 'Central' },
  { name: 'Masaka', region: 'Central' },
  { name: 'Jinja Central', region: 'Eastern' },
  { name: 'Mbale', region: 'Eastern' },
  { name: 'Soroti', region: 'Eastern' },
  { name: 'Tororo', region: 'Eastern' },
  { name: 'Gulu', region: 'Northern' },
  { name: 'Lira', region: 'Northern' },
  { name: 'Arua', region: 'West Nile' },
  { name: 'Mbarara', region: 'Western' },
  { name: 'Fort Portal', region: 'Western' },
  { name: 'Hoima', region: 'Western' },
  { name: 'Kabale', region: 'Western' },
  { name: 'Masindi', region: 'Western' },
  { name: 'Moroto', region: 'Karamoja' },
];

export const DIRECTORATES = [
  'Criminal Investigations (CID)',
  'Counter Terrorism',
  'Traffic and Road Safety',
  'Fire and Rescue Services',
  'Community Affairs',
  'Human Resource Development',
  'ICT Research, Planning and Innovation',
  'Interpol and International Relations',
  'Operations',
  'Professional Standards Unit',
  'Police Health Services',
  'Welfare and Production',
];

export const INSTITUTIONS = [
  'Police Senior Command and Staff College Bwebajja',
  'Police Training School Kabalye, Masindi',
  'Police Training School Olilim, Katakwi',
  'Canine Training School Nsambya',
  'Marine Training School Kajjansi',
  'Makerere University',
  'Kyambogo University',
  'Uganda Christian University, Mukono',
  'Uganda Management Institute',
  'Nkumba University',
  'Law Development Centre',
  'Uganda Institute of Information and Communications Technology',
  'EAPCCO Regional Training Centre',
];

/** Police training institutions — used for the QUALIFICATION +8 bonus (§7.1). */
export const POLICE_INSTITUTIONS = new Set([
  'Police Senior Command and Staff College Bwebajja',
  'Police Training School Kabalye, Masindi',
  'Police Training School Olilim, Katakwi',
  'Canine Training School Nsambya',
  'Marine Training School Kajjansi',
  'EAPCCO Regional Training Centre',
]);

export const SPECIALIZATIONS = [
  'Cybercrime Investigation',
  'Digital Forensics',
  'Criminal Investigation',
  'Scene of Crime Management',
  'Fingerprint and Ballistics',
  'Community Policing',
  'Public Order Management',
  'Traffic Management and Road Safety',
  'Counter-Terrorism',
  'Firearms and Tactical Training',
  'Canine Handling',
  'Marine Operations',
  'Human Rights and Professional Standards',
  'Anti-Corruption',
  'Child and Family Protection',
  'Gender-Based Violence Response',
  'Drill and Ceremonial',
  'First Aid and Emergency Response',
  'Intelligence Analysis',
  'Border Management',
  'Crowd Control',
  'Fire and Rescue Operations',
  'Records and Registry Management',
  'ICT Systems Administration',
];

/**
 * Each specialisation's parent programme category. Drives the SPECIALIZATION
 * +10 breadth bonus (§7.1) and the "evaluation in the required specialisation"
 * relevance test in PERFORMANCE scoring.
 */
export const SPECIALIZATION_CATEGORY: Record<string, string> = {
  'Cybercrime Investigation': 'Investigations',
  'Criminal Investigation': 'Investigations',
  'Digital Forensics': 'Forensics',
  'Scene of Crime Management': 'Forensics',
  'Fingerprint and Ballistics': 'Forensics',
  'Community Policing': 'Community Policing',
  'Public Order Management': 'Public Order',
  'Crowd Control': 'Public Order',
  'Drill and Ceremonial': 'Public Order',
  'Traffic Management and Road Safety': 'Traffic',
  'Counter-Terrorism': 'Counter-Terrorism',
  'Border Management': 'Counter-Terrorism',
  'Firearms and Tactical Training': 'Firearms',
  'Canine Handling': 'Firearms',
  'Marine Operations': 'Marine',
  'Fire and Rescue Operations': 'Marine',
  'Human Rights and Professional Standards': 'Professional Standards',
  'Anti-Corruption': 'Professional Standards',
  'Child and Family Protection': 'Child Protection',
  'Gender-Based Violence Response': 'Child Protection',
  'First Aid and Emergency Response': 'Community Policing',
  'Intelligence Analysis': 'Intelligence',
  'Records and Registry Management': 'Records Management',
  'ICT Systems Administration': 'Records Management',
};

export function categoryForSpecialization(area: string): string | undefined {
  return SPECIALIZATION_CATEGORY[area];
}

export const PROGRAMME_CATEGORIES = [
  'Investigations',
  'Community Policing',
  'Public Order',
  'Forensics',
  'Traffic',
  'Counter-Terrorism',
  'Professional Standards',
  'Child Protection',
  'Marine',
  'Intelligence',
  'Firearms',
  'Records Management',
];

/** Programme title shapes (§8.6). */
export const PROGRAMME_TITLE_SHAPES = [
  'Basic Cybercrime Investigation Course — Intake {n}',
  'Community Policing Refresher, {region} Region',
  'Public Order Management Pre-Deployment Training',
  'Scene of Crime Management Course',
  'Digital Forensics Level 2',
  'Traffic Law Enforcement and Road Safety Course',
  'Anti-Corruption and Professional Standards Seminar',
  'Child and Family Protection Unit Training',
  'Marine Search and Rescue Course, Kajjansi',
  'Intelligence Analysis Foundation Course',
  'Firearms Instructor Refresher — Kabalye',
  'Records and Registry Management Workshop',
];

// --- Enum display labels -------------------------------------------------

export const PROGRAMME_STATUS_LABELS: Record<ProgrammeStatus, string> = {
  DRAFT: 'Draft',
  REQUIREMENTS_SET: 'Requirements set',
  PREDICTED: 'Predicted',
  AWAITING_RESPONSE: 'Awaiting response',
  ALLOCATED: 'Allocated',
  CONDUCTED: 'Conducted',
  EVALUATED: 'Evaluated',
  CANCELLED: 'Cancelled',
};

export const ALLOCATION_STATUS_LABELS: Record<AllocationStatus, string> = {
  PENDING_TRAINER: 'Awaiting trainer',
  CONFIRMED: 'Confirmed',
  DECLINED: 'Declined',
  CONDUCTED: 'Conducted',
  EVALUATED: 'Evaluated',
  WITHDRAWN: 'Withdrawn',
};

export const AVAILABILITY_LABELS: Record<AvailabilityStatus, string> = {
  AVAILABLE: 'Available',
  ASSIGNED: 'Assigned',
  UNAVAILABLE: 'Unavailable',
};

export const ACCOUNT_STATUS_LABELS: Record<AccountStatus, string> = {
  ACTIVE: 'Active',
  SUSPENDED: 'Suspended',
  DEACTIVATED: 'Deactivated',
};

export const CONFIDENCE_LABELS: Record<ConfidenceBand, string> = {
  HIGH: 'High',
  MODERATE: 'Moderate',
  LOW: 'Low',
};

/** Semantic colour bucket used by StatusBadge (§10.1). */
export type SemanticTone = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

export const PROGRAMME_STATUS_TONE: Record<ProgrammeStatus, SemanticTone> = {
  DRAFT: 'neutral',
  REQUIREMENTS_SET: 'info',
  PREDICTED: 'info',
  AWAITING_RESPONSE: 'warning',
  ALLOCATED: 'success',
  CONDUCTED: 'success',
  EVALUATED: 'success',
  CANCELLED: 'danger',
};

export const ALLOCATION_STATUS_TONE: Record<AllocationStatus, SemanticTone> = {
  PENDING_TRAINER: 'warning',
  CONFIRMED: 'success',
  DECLINED: 'danger',
  CONDUCTED: 'info',
  EVALUATED: 'success',
  WITHDRAWN: 'neutral',
};

export const AVAILABILITY_TONE: Record<AvailabilityStatus, SemanticTone> = {
  AVAILABLE: 'success',
  ASSIGNED: 'warning',
  UNAVAILABLE: 'danger',
};

export const ACCOUNT_STATUS_TONE: Record<AccountStatus, SemanticTone> = {
  ACTIVE: 'success',
  SUSPENDED: 'warning',
  DEACTIVATED: 'danger',
};

export const CONFIDENCE_TONE: Record<ConfidenceBand, SemanticTone> = {
  HIGH: 'success',
  MODERATE: 'warning',
  LOW: 'warning',
};

// --- Auth / lockout (FR-01) ---------------------------------------------

export const MAX_LOGIN_ATTEMPTS = 3;
export const LOCKOUT_MINUTES = 15;

export const PHONE_PREFIXES = ['0772', '0782', '0752', '0700', '0701', '0703', '0784'];
