import { generateDb, type MockDb } from './generate';

/** The seeded mock database — generated once at module load, deterministic. */
export const db: MockDb = generateDb();
export type { MockDb, WeightPolicyRecord } from './generate';
