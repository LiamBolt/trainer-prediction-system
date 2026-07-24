/**
 * TPS domain model — mirrors the SRS Entity Relationship Diagram (§6).
 * Field names match the intended database schema so the backend swap (§9.3)
 * is frictionless. Eleven core entities.
 */

export type RoleName =
  | 'TRAINING_ADMINISTRATOR'
  | 'TRAINING_OFFICER'
  | 'TRAINER'
  | 'SYSTEM_ADMINISTRATOR';

export type AccountStatus = 'ACTIVE' | 'SUSPENDED' | 'DEACTIVATED';
export type AvailabilityStatus = 'AVAILABLE' | 'ASSIGNED' | 'UNAVAILABLE';
export type ProficiencyLevel = 'BASIC' | 'INTERMEDIATE' | 'ADVANCED' | 'EXPERT';

/** Rank codes, ordered junior -> senior. Full names live in lib/constants.ts (§8.1). */
export type PoliceRank = 'PC' | 'CPL' | 'SGT' | 'AIP' | 'IP' | 'ASP' | 'SP' | 'SSP' | 'ACP';

export type ProgrammeStatus =
  | 'DRAFT' // created, requirements not yet defined (FR-04 done, FR-05 pending)
  | 'REQUIREMENTS_SET' // ready for prediction
  | 'PREDICTED' // prediction run complete, awaiting Administrator review
  | 'AWAITING_RESPONSE' // trainer notified, has not answered
  | 'ALLOCATED' // trainer confirmed
  | 'CONDUCTED' // training delivered — unlocks FR-10
  | 'EVALUATED' // performance recorded, loop closed
  | 'CANCELLED';

export type AllocationStatus =
  | 'PENDING_TRAINER' // approved by Administrator, awaiting trainer response
  | 'CONFIRMED'
  | 'DECLINED'
  | 'CONDUCTED'
  | 'EVALUATED'
  | 'WITHDRAWN';

export interface Role {
  roleId: number;
  roleName: RoleName;
  description: string;
}

export interface User {
  userId: number;
  username: string;
  fullName: string;
  email: string;
  roleId: number;
  role: RoleName;
  accountStatus: AccountStatus;
  createdAt: string;
  lastLoginAt: string | null;
}

export interface Trainer {
  trainerId: number;
  userId: number;
  fullName: string;
  forceNumber: string; // e.g. "41927"
  policeRank: PoliceRank;
  station: string;
  region: string;
  directorate: string;
  yearsExperience: number;
  availabilityStatus: AvailabilityStatus;
  contactNumber: string; // "+256 772 419 273"
  qualifications: Qualification[];
  specializations: Specialization[];
  performanceHistory: PerformanceEvaluation[];
  currentAllocations: number;
  lastAssignedDate: string | null;
  profileCompleteness: number; // 0-100, drives confidence (§7.2)
}

export type QualificationLevel =
  | 'CERTIFICATE'
  | 'DIPLOMA'
  | 'BACHELORS'
  | 'POSTGRAD_DIPLOMA'
  | 'MASTERS'
  | 'DOCTORATE';

export interface Qualification {
  qualificationId: number;
  trainerId: number;
  qualificationName: string;
  qualificationLevel: QualificationLevel;
  institutionName: string;
  yearObtained: number;
}

export interface Specialization {
  specializationId: number;
  trainerId: number;
  specializationArea: string;
  proficiencyLevel: ProficiencyLevel;
}

export interface TrainingProgramme {
  programmeId: number;
  title: string;
  category: string;
  requiredSpecialization: string;
  minimumExperience: number;
  minimumQualification: QualificationLevel | null;
  startDate: string;
  endDate: string;
  location: string;
  status: ProgrammeStatus;
  createdBy: number;
  createdByName: string;
  createdAt: string;
  requirementsSetAt: string | null;
  requirementsChangedSincePrediction: boolean; // drives the re-rank banner, FR-05
}

export type CriterionKey =
  | 'SPECIALIZATION'
  | 'QUALIFICATION'
  | 'EXPERIENCE'
  | 'PERFORMANCE'
  | 'AVAILABILITY';

export type DataQuality = 'COMPLETE' | 'PARTIAL' | 'MISSING';
export type ConfidenceBand = 'LOW' | 'MODERATE' | 'HIGH';

export interface CriterionScore {
  key: CriterionKey;
  label: string; // human-facing, e.g. "Specialisation match"
  weight: number; // points available
  rawValue: string; // "Advanced · Cybercrime Investigation"
  normalized: number; // 0-100
  contribution: number; // weight * normalized / 100, one decimal
  explanation: string; // one sentence, plain English
  dataQuality: DataQuality;
}

export interface Prediction {
  predictionId: number;
  programmeId: number;
  trainerId: number;
  predictionScore: number; // 0-100, one decimal
  confidenceLevel: number; // 0-100
  confidenceBand: ConfidenceBand;
  rankPosition: number;
  breakdown: CriterionScore[]; // the Score Ledger data
  rationale: string; // generated plain-English sentence
  counterfactual: string | null; // "Would rank #1 with one more evaluation at or above 4.0"
  generatedDate: string;
}

export type ExclusionReason =
  | 'UNAVAILABLE'
  | 'MISSING_SPECIALIZATION'
  | 'BELOW_MINIMUM_EXPERIENCE'
  | 'BELOW_MINIMUM_QUALIFICATION'
  | 'SCHEDULE_CONFLICT';

export interface ExcludedTrainer {
  trainerId: number;
  fullName: string;
  policeRank: PoliceRank;
  forceNumber: string;
  reason: ExclusionReason;
  reasonDetail: string; // "Assigned to Digital Forensics Level 2 · 10–21 Aug 2026"
  businessRule: 'BR-03' | 'BR-04' | 'FR-05';
}

export interface PredictionRun {
  runId: string;
  programmeId: number;
  generatedDate: string;
  candidatePoolSize: number; // all trainers considered
  excludedCount: number;
  rankedCount: number;
  elapsedMs: number; // surfaced in the UI, ties to NFR-01
  weights: Record<CriterionKey, number>;
  weightsArePolicyDefault: boolean;
  predictions: Prediction[];
  excluded: ExcludedTrainer[];
}

export interface Allocation {
  allocationId: number;
  predictionId: number;
  programmeId: number;
  trainerId: number;
  registryNumber: string; // "TPS/ALL/2026/0417"
  approvedBy: number;
  approvedByName: string;
  approvedByRank: PoliceRank;
  status: AllocationStatus;
  approvalDate: string;
  remarks: string;
  frozenScore: number; // score at moment of approval
  frozenBreakdown: CriterionScore[]; // the Decision Receipt payload
  frozenRankPosition: number;
  frozenWeights: Record<CriterionKey, number>;
  /** The rationale as it stood at approval — shown to the trainer (§11.7). */
  frozenRationale: string;
  weightsWereSimulated: boolean;
  declineReason: string | null;
  declinedAt: string | null;
  respondedAt: string | null;
}

export interface PerformanceEvaluation {
  evaluationId: number;
  allocationId: number;
  trainerId: number;
  programmeId: number;
  programmeTitle: string;
  scoreAwarded: number; // 1.0 - 5.0
  evaluatorComments: string;
  evaluatedBy: number;
  evaluatedByName: string;
  evaluationDate: string;
}

export type AuditAction =
  | 'LOGIN_SUCCESS'
  | 'LOGIN_FAILED'
  | 'ACCOUNT_LOCKED'
  | 'LOGOUT'
  | 'PROGRAMME_CREATED'
  | 'REQUIREMENTS_DEFINED'
  | 'REQUIREMENTS_CHANGED'
  | 'PREDICTION_GENERATED'
  | 'WEIGHTS_SIMULATED'
  | 'WEIGHTS_SAVED'
  | 'ALLOCATION_APPROVED'
  | 'ALLOCATION_DECLINED'
  | 'CANDIDATE_SKIPPED'
  | 'ASSIGNMENT_ACCEPTED'
  | 'ASSIGNMENT_DECLINED'
  | 'EVALUATION_RECORDED'
  | 'REPORT_EXPORTED'
  | 'USER_CREATED'
  | 'USER_MODIFIED'
  | 'USER_DEACTIVATED'
  | 'ROLE_CHANGED'
  | 'UNAUTHORISED_ATTEMPT';

export interface AuditLogEntry {
  logId: number;
  userId: number;
  userName: string;
  userRole: RoleName;
  actionPerformed: AuditAction;
  timestamp: string;
  affectedRecord: string; // "ALLOCATION#417"
  detail: string;
  ipAddress: string;
}

export type NotificationType = 'ASSIGNMENT' | 'APPROVAL' | 'EVALUATION' | 'SYSTEM' | 'REMINDER';

export interface Notification {
  notificationId: number;
  recipientId: number;
  message: string;
  type: NotificationType;
  sentDate: string;
  status: 'UNREAD' | 'READ';
  linkTo: string | null;
}
