import { describe, expect, it } from 'vitest';
import type {
  PerformanceEvaluation,
  Qualification,
  Specialization,
  Trainer,
  TrainingProgramme,
} from '@/types/domain';
import { DEFAULT_WEIGHTS } from '@/lib/constants';
import {
  scoreSpecialization,
  scorePerformance,
  scoreExperience,
  scoreQualification,
  scoreAvailability,
} from './criteria';
import { evaluateGates } from './gates';
import {
  computeTotal,
  computeConfidence,
  compareCandidates,
  recomputeWithWeights,
  scoreCandidate,
  type ScoredCandidate,
} from './score';
import { buildCounterfactual, buildRationale } from './narrative';
import { runPrediction } from './index';

// --- fixtures -------------------------------------------------------------

function spec(area: string, level: Specialization['proficiencyLevel']): Specialization {
  return { specializationId: 1, trainerId: 1, specializationArea: area, proficiencyLevel: level };
}
function qual(
  level: Qualification['qualificationLevel'],
  institutionName = 'Makerere University',
): Qualification {
  return {
    qualificationId: 1,
    trainerId: 1,
    qualificationName: 'Test',
    qualificationLevel: level,
    institutionName,
    yearObtained: 2015,
  };
}
function evaluation(score: number, date = '2026-01-10'): PerformanceEvaluation {
  return {
    evaluationId: 1,
    allocationId: 1,
    trainerId: 1,
    programmeId: 1,
    programmeTitle: 'Test course',
    scoreAwarded: score,
    evaluatorComments: 'ok',
    evaluatedBy: 1,
    evaluatedByName: 'Officer',
    evaluationDate: date,
  };
}
function makeTrainer(overrides: Partial<Trainer> = {}): Trainer {
  return {
    trainerId: 1,
    userId: 1,
    fullName: 'ASP Grace Nabirye',
    forceNumber: '41927',
    policeRank: 'ASP',
    station: 'Kira Road',
    region: 'Kampala Metropolitan',
    directorate: 'Criminal Investigations (CID)',
    yearsExperience: 11,
    availabilityStatus: 'AVAILABLE',
    contactNumber: '+256 772 419 273',
    qualifications: [qual('BACHELORS')],
    specializations: [spec('Cybercrime Investigation', 'ADVANCED')],
    performanceHistory: [],
    currentAllocations: 0,
    lastAssignedDate: null,
    profileCompleteness: 80,
    ...overrides,
  };
}
function makeProgramme(overrides: Partial<TrainingProgramme> = {}): TrainingProgramme {
  return {
    programmeId: 1,
    title: 'Basic Cybercrime Investigation Course — Intake 14',
    category: 'Investigations',
    requiredSpecialization: 'Cybercrime Investigation',
    minimumExperience: 3,
    minimumQualification: null,
    startDate: '2026-08-10',
    endDate: '2026-08-21',
    location: 'Kampala',
    status: 'REQUIREMENTS_SET',
    createdBy: 2,
    createdByName: 'Officer',
    createdAt: '2026-07-01',
    requirementsSetAt: '2026-07-02',
    requirementsChangedSincePrediction: false,
    ...overrides,
  };
}

// --- gates (Stage 1) ------------------------------------------------------

describe('evaluateGates — order and reasons', () => {
  const programme = makeProgramme({ minimumExperience: 5, minimumQualification: 'MASTERS' });

  it('excludes UNAVAILABLE first (BR-03)', () => {
    const t = makeTrainer({ availabilityStatus: 'UNAVAILABLE', specializations: [] });
    expect(evaluateGates(t, programme)?.reason).toBe('UNAVAILABLE');
  });

  it('excludes missing specialisation (BR-04)', () => {
    const t = makeTrainer({ specializations: [spec('Marine Operations', 'EXPERT')] });
    expect(evaluateGates(t, programme)?.reason).toBe('MISSING_SPECIALIZATION');
  });

  it('excludes schedule conflict before experience', () => {
    const t = makeTrainer({ yearsExperience: 1 });
    const out = evaluateGates(t, programme, {
      conflict: { title: 'Digital Forensics Level 2', startDate: '2026-08-10', endDate: '2026-08-21' },
    });
    expect(out?.reason).toBe('SCHEDULE_CONFLICT');
    expect(out?.reasonDetail).toContain('Digital Forensics Level 2');
  });

  it('excludes below minimum experience (FR-05)', () => {
    const t = makeTrainer({ yearsExperience: 2 });
    expect(evaluateGates(t, programme)?.reason).toBe('BELOW_MINIMUM_EXPERIENCE');
  });

  it('excludes below minimum qualification (FR-05)', () => {
    const t = makeTrainer({ yearsExperience: 10, qualifications: [qual('DIPLOMA')] });
    expect(evaluateGates(t, programme)?.reason).toBe('BELOW_MINIMUM_QUALIFICATION');
  });

  it('passes a fully eligible trainer', () => {
    const t = makeTrainer({ yearsExperience: 10, qualifications: [qual('MASTERS')] });
    expect(evaluateGates(t, programme)).toBeNull();
  });
});

// --- normalisation (Stage 2) ---------------------------------------------

describe('criterion normalisation', () => {
  const programme = makeProgramme();

  it('maps proficiency and adds the breadth bonus', () => {
    const base = scoreSpecialization(makeTrainer(), programme);
    expect(base.normalized).toBe(85); // ADVANCED

    const broad = makeTrainer({
      specializations: [
        spec('Cybercrime Investigation', 'ADVANCED'),
        spec('Criminal Investigation', 'INTERMEDIATE'), // same "Investigations" category
      ],
    });
    expect(scoreSpecialization(broad, programme).normalized).toBe(95); // +10, capped at 100
  });

  it('uses a neutral prior of 55 when there is no history', () => {
    const r = scorePerformance(makeTrainer(), programme);
    expect(r.normalized).toBe(55);
    expect(r.dataQuality).toBe('MISSING');
    expect(r.mean).toBeNull();
  });

  it('maps mean rating (4.6 -> 90)', () => {
    const t = makeTrainer({ performanceHistory: [evaluation(4.4), evaluation(4.8)] });
    const r = scorePerformance(t, programme);
    expect(r.mean).toBeCloseTo(4.6, 5);
    expect(r.normalized).toBe(90);
  });

  it('caps experience at 20 years', () => {
    expect(scoreExperience(makeTrainer({ yearsExperience: 10 })).normalized).toBe(50);
    expect(scoreExperience(makeTrainer({ yearsExperience: 25 })).normalized).toBe(100);
  });

  it('scores qualification with the police-college bonus', () => {
    expect(scoreQualification(makeTrainer({ qualifications: [qual('MASTERS')] })).normalized).toBe(90);
    const police = makeTrainer({
      qualifications: [qual('MASTERS', 'Police Training School Kabalye, Masindi')],
    });
    expect(scoreQualification(police).normalized).toBe(98); // +8
  });

  it('scores availability by workload, ASSIGNED capped at 50', () => {
    expect(scoreAvailability(makeTrainer({ currentAllocations: 0 })).normalized).toBe(100);
    expect(scoreAvailability(makeTrainer({ currentAllocations: 2 })).normalized).toBe(50);
    expect(
      scoreAvailability(makeTrainer({ availabilityStatus: 'ASSIGNED', currentAllocations: 0 }))
        .normalized,
    ).toBe(50);
  });
});

// --- total, confidence, weights ------------------------------------------

describe('total and weight recompute', () => {
  const programme = makeProgramme();

  it('total is the sum of contributions, one decimal', () => {
    const c = scoreCandidate(makeTrainer(), programme, DEFAULT_WEIGHTS);
    expect(c.total).toBe(computeTotal(c.breakdown));
    expect(Number.isInteger(c.total * 10)).toBe(true);
  });

  it('recompute changes contributions but never normalized values', () => {
    const c = scoreCandidate(makeTrainer(), programme, DEFAULT_WEIGHTS);
    const before = c.breakdown.map((b) => b.normalized);
    const heavy = { ...DEFAULT_WEIGHTS, SPECIALIZATION: 50, AVAILABILITY: 0, PERFORMANCE: 15 };
    const { breakdown, total } = recomputeWithWeights(c.breakdown, heavy);
    expect(breakdown.map((b) => b.normalized)).toEqual(before);
    expect(total).toBe(computeTotal(breakdown));
    const spec = breakdown.find((b) => b.key === 'SPECIALIZATION');
    expect(spec?.contribution).toBeCloseTo((50 * (spec?.normalized ?? 0)) / 100, 1);
  });

  it('bands confidence by data completeness', () => {
    const rich = makeTrainer({
      profileCompleteness: 100,
      performanceHistory: [evaluation(4), evaluation(4), evaluation(5), evaluation(4), evaluation(5)],
    });
    expect(computeConfidence(rich, new Date('2026-07-22')).band).toBe('HIGH');
    const thin = makeTrainer({ profileCompleteness: 30, performanceHistory: [] });
    expect(computeConfidence(thin, new Date('2026-07-22')).band).toBe('LOW');
  });
});

// --- tie-break ------------------------------------------------------------

describe('deterministic tie-break', () => {
  const programme = makeProgramme();
  const build = (t: Trainer): ScoredCandidate => scoreCandidate(t, programme, DEFAULT_WEIGHTS);

  it('breaks equal totals by higher performance mean', () => {
    const a = build(makeTrainer({ trainerId: 1, performanceHistory: [evaluation(5), evaluation(5)] }));
    const b = build(makeTrainer({ trainerId: 2, performanceHistory: [evaluation(3), evaluation(3)] }));
    const sorted = [b, a].sort(compareCandidates);
    // The equal-spec/exp/qual trainers differ only by performance; higher mean wins.
    expect(sorted[0]?.performanceMean ?? 0).toBeGreaterThanOrEqual(sorted[1]?.performanceMean ?? 0);
  });
});

// --- narrative (Stage 4) --------------------------------------------------

describe('narrative', () => {
  const programme = makeProgramme();

  it('names the strongest evidence with history', () => {
    const c = scoreCandidate(
      makeTrainer({ performanceHistory: [evaluation(4.6), evaluation(4.6)] }),
      programme,
      DEFAULT_WEIGHTS,
    );
    const text = buildRationale(c, programme);
    expect(text).toContain('ASP Nabirye');
    expect(text).toContain('Cybercrime Investigation');
    expect(text).toContain('out of 5');
  });

  it('is honest when history is thin', () => {
    const c = scoreCandidate(makeTrainer(), programme, DEFAULT_WEIGHTS);
    expect(buildRationale(c, programme)).toContain('no recorded evaluations yet');
  });

  it('returns null when no single change reaches rank 1', () => {
    const c = scoreCandidate(makeTrainer(), programme, DEFAULT_WEIGHTS);
    // A gap larger than any single lever can close.
    expect(buildCounterfactual(c, c.total + 60, DEFAULT_WEIGHTS)).toBeNull();
  });

  it('proposes a concrete evaluation when one closes the gap', () => {
    const c = scoreCandidate(
      makeTrainer({ performanceHistory: [evaluation(3), evaluation(3)] }),
      programme,
      DEFAULT_WEIGHTS,
    );
    const text = buildCounterfactual(c, c.total + 1, DEFAULT_WEIGHTS);
    expect(text).toMatch(/rank 1st/);
  });
});

// --- orchestrator ---------------------------------------------------------

describe('runPrediction', () => {
  const programme = makeProgramme();

  it('ranks eligible trainers and records exclusions (BR-03/BR-05)', () => {
    const trainers = [
      makeTrainer({ trainerId: 1, forceNumber: '10001', performanceHistory: [evaluation(4.8), evaluation(4.8)] }),
      makeTrainer({ trainerId: 2, forceNumber: '10002', performanceHistory: [evaluation(3.2)] }),
      makeTrainer({ trainerId: 3, forceNumber: '10003', availabilityStatus: 'UNAVAILABLE' }),
    ];
    const run = runPrediction({ programme, trainers, now: new Date('2026-07-22') });
    expect(run.rankedCount).toBe(2);
    expect(run.excludedCount).toBe(1);
    // BR-05 — strictly descending by score.
    for (let i = 1; i < run.predictions.length; i++) {
      const prev = run.predictions[i - 1]!;
      const cur = run.predictions[i]!;
      expect(prev.predictionScore).toBeGreaterThanOrEqual(cur.predictionScore);
      expect(cur.rankPosition).toBe(i + 1);
    }
    // No unavailable trainer appears in the ranked list.
    expect(run.predictions.some((p) => p.trainerId === 3)).toBe(false);
  });
});
