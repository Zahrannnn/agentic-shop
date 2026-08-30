/**
 * Reassurance copy for the pre-prose thinking state, bucketed by elapsed
 * seconds (PRODUCT.md principle 4: long thinking is normal; the wait must
 * read as work being done, honestly and without anxiety). Curator voice —
 * the lines describe care being taken, never pipeline stage names (the
 * internal lifecycle vocabulary is deliberately not rendered, UX review).
 *
 * Pure and deterministic: a pure function of the elapsed count, so the
 * rotation is unit-testable and identical across renders.
 */

const REASSURANCE_EARLY = "Reading the catalog…";
const REASSURANCE_MID = "Comparing candidates on what matters to you…";
const REASSURANCE_LONG = "Taking the time to get this right…";

/** Elapsed-second thresholds where the reassurance line rotates. */
export const REASSURANCE_BUCKETS = { mid: 8, long: 20 } as const;

export function reassuranceFor(elapsedSeconds: number): string {
  if (elapsedSeconds < REASSURANCE_BUCKETS.mid) {
    return REASSURANCE_EARLY;
  }
  if (elapsedSeconds < REASSURANCE_BUCKETS.long) {
    return REASSURANCE_MID;
  }
  return REASSURANCE_LONG;
}
