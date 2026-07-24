import { create } from 'zustand';
import type { CriterionKey } from '@/types/domain';
import { CRITERION_ORDER, DEFAULT_WEIGHTS } from '@/lib/constants';

/**
 * weightStore — the live Weight Studio simulation (§12.6). Client-only until an
 * administrator saves it as policy at /admin/scoring-policy. Weights always total
 * 100: adjusting one proportionally redistributes the remainder across the others.
 */
type Weights = Record<CriterionKey, number>;

interface WeightState {
  weights: Weights;
  policy: Weights;
  simulated: boolean;
  setWeight: (key: CriterionKey, value: number) => void;
  applyWeights: (weights: Weights) => void;
  resetToPolicy: () => void;
  setPolicy: (weights: Weights, syncCurrent?: boolean) => void;
}

const sum = (w: Weights) => CRITERION_ORDER.reduce((s, k) => s + w[k], 0);
const equals = (a: Weights, b: Weights) => CRITERION_ORDER.every((k) => a[k] === b[k]);

/** Set one weight to `value`; distribute the remainder across the others. */
export function redistribute(current: Weights, key: CriterionKey, value: number): Weights {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  const others = CRITERION_ORDER.filter((k) => k !== key);
  const remainder = 100 - clamped;
  const othersTotal = others.reduce((s, k) => s + current[k], 0);

  const next = { ...current, [key]: clamped } as Weights;
  if (othersTotal === 0) {
    const each = Math.floor(remainder / others.length);
    others.forEach((k, i) => (next[k] = each + (i === 0 ? remainder - each * others.length : 0)));
  } else {
    others.forEach((k) => (next[k] = Math.round((current[k] / othersTotal) * remainder)));
  }

  // Absorb integer-rounding drift into the largest untouched criterion.
  const drift = 100 - sum(next);
  if (drift !== 0) {
    const target = [...others].sort((a, b) => next[b] - next[a])[0] ?? key;
    next[target] = Math.max(0, next[target] + drift);
  }
  return next;
}

export const useWeightStore = create<WeightState>((set, get) => ({
  weights: { ...DEFAULT_WEIGHTS },
  policy: { ...DEFAULT_WEIGHTS },
  simulated: false,
  setWeight: (key, value) => {
    const next = redistribute(get().weights, key, value);
    set({ weights: next, simulated: !equals(next, get().policy) });
  },
  applyWeights: (weights) => set({ weights: { ...weights }, simulated: !equals(weights, get().policy) }),
  resetToPolicy: () => set({ weights: { ...get().policy }, simulated: false }),
  setPolicy: (weights, syncCurrent = true) =>
    set((s) => ({
      policy: { ...weights },
      weights: syncCurrent ? { ...weights } : s.weights,
      simulated: syncCurrent ? false : !equals(s.weights, weights),
    })),
}));
