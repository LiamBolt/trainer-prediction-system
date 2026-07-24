import { describe, expect, it } from 'vitest';
import { generateDb } from './generate';

const db = generateDb();

describe('mock dataset volumes (§8)', () => {
  it('has the expected core volumes', () => {
    expect(db.trainers).toHaveLength(812);
    expect(db.users).toHaveLength(40);
    expect(db.programmes).toHaveLength(46);
    expect(db.notifications).toHaveLength(18);
    expect(db.audit.length).toBeGreaterThanOrEqual(600);
    expect(db.evaluations.length).toBeGreaterThanOrEqual(40);
  });

  it('is deterministic across runs', () => {
    const a = generateDb();
    const b = generateDb();
    expect(a.trainers[100]?.forceNumber).toBe(b.trainers[100]?.forceNumber);
    expect(a.trainers[500]?.fullName).toBe(b.trainers[500]?.fullName);
  });

  it('roster reads ~30% women (name pool split)', () => {
    // Female given names as a sanity proxy on the generated pool trainers.
    const female = new Set(['Grace', 'Sarah', 'Aisha', 'Betty', 'Immaculate', 'Robinah', 'Prossy', 'Zainab', 'Harriet', 'Norah', 'Specioza', 'Justine']);
    const share =
      db.trainers.filter((t) => female.has(t.fullName.split(' ')[0] ?? '')).length / db.trainers.length;
    expect(share).toBeGreaterThan(0.2);
    expect(share).toBeLessThan(0.42);
  });
});

describe('featured cybercrime run (§8.10 story beats)', () => {
  const run = db.runs.find((r) => r.programmeId === db.featuredProgrammeId);

  it('exists and ranks a large eligible pool', () => {
    expect(run).toBeDefined();
    expect(run!.rankedCount).toBeGreaterThan(400);
    expect(run!.excludedCount).toBeGreaterThan(0);
    expect(run!.elapsedMs).toBe(1400);
  });

  it('has the two curated heroes as the top two, within 1.4 points', () => {
    const [first, second] = run!.predictions;
    expect(first?.trainerId).toBe(1); // IP Sarah Mugisha
    expect(second?.trainerId).toBe(2); // ASP Betty Nabirye
    expect(first!.predictionScore).toBeGreaterThan(second!.predictionScore);
    expect(first!.predictionScore - second!.predictionScore).toBeLessThanOrEqual(1.4);
  });

  it('includes a zero-evaluation LOW-confidence candidate (trainer 4)', () => {
    const t4 = run!.predictions.find((p) => p.trainerId === 4);
    expect(t4).toBeDefined();
    expect(t4!.confidenceBand).toBe('LOW');
    const perf = t4!.breakdown.find((c) => c.key === 'PERFORMANCE');
    expect(perf?.dataQuality).toBe('MISSING');
  });

  it('has real Exclusion-Ledger content grouped by rule', () => {
    const reasons = new Set(run!.excluded.map((e) => e.reason));
    expect(reasons.has('UNAVAILABLE')).toBe(true);
    expect(reasons.has('MISSING_SPECIALIZATION')).toBe(true);
    // BR-05 — no unavailable trainer appears in the ranked list.
    const unavailableIds = new Set(
      db.trainers.filter((t) => t.availabilityStatus === 'UNAVAILABLE').map((t) => t.trainerId),
    );
    expect(run!.predictions.some((p) => unavailableIds.has(p.trainerId))).toBe(false);
  });

  it('the top two flip under the performance-priority preset', () => {
    // Recompute contributions with a heavier PERFORMANCE weight (preset).
    const heavy = { SPECIALIZATION: 24, PERFORMANCE: 40, EXPERIENCE: 16, QUALIFICATION: 12, AVAILABILITY: 8 };
    const rescore = (trainerId: number) => {
      const p = run!.predictions.find((x) => x.trainerId === trainerId)!;
      return p.breakdown.reduce((s, c) => s + (heavy[c.key] * c.normalized) / 100, 0);
    };
    expect(rescore(2)).toBeGreaterThan(rescore(1)); // Nabirye overtakes Mugisha
  });
});

describe('lifecycle records', () => {
  it('has a trainer-declined allocation with a real reason', () => {
    const declined = db.allocations.find((a) => a.status === 'DECLINED');
    expect(declined).toBeDefined();
    expect(declined!.declineReason).toContain('court testimony');
  });

  it('has a CONDUCTED allocation awaiting evaluation', () => {
    expect(db.allocations.some((a) => a.status === 'CONDUCTED')).toBe(true);
  });

  it('links the trainer demo account to hero T1', () => {
    const trainerUser = db.users.find((u) => u.username === 'trainer');
    expect(trainerUser?.userId).toBe(db.trainers[0]?.userId);
  });
});
