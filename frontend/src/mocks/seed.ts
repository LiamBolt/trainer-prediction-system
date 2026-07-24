/**
 * Deterministic seeded PRNG (mulberry32) and helpers — §8. Fixed seed 20260722
 * makes the mock dataset byte-identical on every reload. A demo that reshuffles
 * itself is not a demo.
 */

export const MOCK_SEED = 20260722;

/** mulberry32 — tiny, fast, deterministic 32-bit PRNG. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return function next(): number {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A small deterministic RNG with convenience methods, seeded once. */
export class Rng {
  private next: () => number;

  constructor(seed: number = MOCK_SEED) {
    this.next = mulberry32(seed);
  }

  /** Float in [0, 1). */
  float(): number {
    return this.next();
  }

  /** Integer in [min, max] inclusive. */
  int(min: number, max: number): number {
    return Math.floor(this.next() * (max - min + 1)) + min;
  }

  /** Float in [min, max), rounded to `decimals`. */
  range(min: number, max: number, decimals = 0): number {
    const v = this.next() * (max - min) + min;
    const f = 10 ** decimals;
    return Math.round(v * f) / f;
  }

  bool(probabilityTrue = 0.5): boolean {
    return this.next() < probabilityTrue;
  }

  /** Uniform pick from a non-empty array. */
  pick<T>(items: readonly T[]): T {
    if (items.length === 0) throw new Error('Rng.pick: empty array');
    return items[Math.floor(this.next() * items.length)] as T;
  }

  /** Pick `n` distinct items (Fisher–Yates on a copy). */
  sample<T>(items: readonly T[], n: number): T[] {
    const copy = [...items];
    const count = Math.min(n, copy.length);
    for (let i = 0; i < count; i++) {
      const j = i + Math.floor(this.next() * (copy.length - i));
      const a = copy[i] as T;
      copy[i] = copy[j] as T;
      copy[j] = a;
    }
    return copy.slice(0, count);
  }

  shuffle<T>(items: readonly T[]): T[] {
    return this.sample(items, items.length);
  }

  /** Weighted pick: items paired with weights. */
  weighted<T>(entries: readonly (readonly [T, number])[]): T {
    const total = entries.reduce((s, [, w]) => s + w, 0);
    let r = this.next() * total;
    for (const [item, w] of entries) {
      r -= w;
      if (r <= 0) return item;
    }
    return entries[entries.length - 1]?.[0] as T;
  }
}
