// The three ownership tiers, and the one rule that turns them into two
// behaviours. Pure and offline so the differ, the push planner and the tests
// all key off the same table rather than three copies of it.
//
// | | A — platform-owned | B — bundle-owned | C — contested |
// |---|---|---|---|
// | source of truth | the warehouse / the scan | the bundle | whichever `userManaged` says |
// | pushed? | never | yes, total replace | yes, always, carrying the flag |
// | pull refreshes the bundle? | yes (the cache) | never | only at `userManaged=false` |
// | in the forward diff? | no — report STALE CACHE | yes — report DRIFT | at true DRIFT, at false STALE CACHE |
//
// TIER C IS NOT A THIRD BEHAVIOUR. It is a runtime switch between the other
// two, thrown by `userManaged` — which we compute as `verified`. So sign-off is
// the switch, and there is no third code path in either the differ or the
// refresh.

export enum Tier {
  /** The warehouse and the scans author it. We cache it; we never write it. */
  PLATFORM = 'A',
  /** The bundle authors it. Nothing else may write it. */
  BUNDLE = 'B',
  /** The scan wants it and so do we. `userManaged` decides. */
  CONTESTED = 'C',
  /** Not ours and not the platform's: another team's aspect, a link type. */
  FOREIGN = 'foreign',
}

// Keyed on the aspect id — the last dotted segment — because the same aspect
// comes back qualified by project NUMBER where we wrote project ID
// (`655216118709.global.overview` vs `dataplex-types.global.overview`), and by
// id it is the same thing either way.
//
// TIER A IS FROM MEASUREMENT, NOT FROM MEMORY: `okf-review/probe_entries.py`
// at `view=ALL` across all 14 entries found exactly
//   bigquery-dataset, bigquery-policy, bigquery-table, schema, storage
// as platform-authored (all five carry `aspectSource.dataVersion:
// Ingestion/1.0.0`; the four we or the scan write carry an empty
// `aspectSource`). `data-profile` is listed because the tier is about
// AUTHORITY rather than presence — but note it exists on NONE of these
// entries, which is why Phase 6 computes distributional facts from BigQuery
// instead of mirroring an aspect that is not there.
const TIER_BY_ASPECT_ID: Record<string, Tier> = {
  // A
  'schema': Tier.PLATFORM,
  'storage': Tier.PLATFORM,
  'bigquery-table': Tier.PLATFORM,
  'bigquery-dataset': Tier.PLATFORM,
  'bigquery-policy': Tier.PLATFORM,
  'data-profile': Tier.PLATFORM,
  'data-quality-scorecard': Tier.PLATFORM,
  // B
  'okf': Tier.BUNDLE,
  'overview': Tier.BUNDLE,
  'generic': Tier.BUNDLE,
  // C
  'descriptions': Tier.CONTESTED,
  'queries': Tier.CONTESTED,
};

/** `655216118709.global.overview` / `dataplex-types.global.overview` -> `overview`. */
export function aspectId(key: string): string {
  return key.split('.').pop() ?? key;
}

export function tierOf(key: string): Tier {
  return TIER_BY_ASPECT_ID[aspectId(key)] ?? Tier.FOREIGN;
}

/**
 * Does this channel behave as OWNED (the bundle is authoritative, a difference
 * is drift) or as CACHE (the platform is authoritative, a difference is a stale
 * cache)?
 *
 * `userManaged` is read from the EXPECTED aspect, not the actual one: it is the
 * flag we are asserting. If the catalog disagrees about the flag itself, that
 * is its own finding — the ownership invariant broke — and is reported
 * separately rather than being allowed to decide how to report everything else.
 */
export function behavesAsOwned(key: string, expectedAspect?: any): boolean {
  const tier = tierOf(key);
  if (tier === Tier.BUNDLE) return true;
  if (tier === Tier.CONTESTED) return expectedAspect?.userManaged === true;
  return false;
}
