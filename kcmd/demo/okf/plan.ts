// The forward differ — and the push planner, which is the same code.
//
// THE DIRECTION IS THE DESIGN. We compare `expected` (built from the bundle by
// the very function the push uses) against `actual` (read from the catalog), IN
// THE CATALOG'S SHAPE. We never translate the catalog back into OKF.
//
//   expected = buildStagedEntry(okf-bundle/<concept>)   the object push sends
//   actual   = CatalogClient.getEntry(<entry>, view=ALL)
//   compare aspect by aspect
//
// A reverse mapping is lossy, and a reverse-mapped diff is blind to exactly the
// fields the reverse mapping does not know about. The forward projection has no
// such gap: it IS the definition of what the bundle claims about the catalog,
// because it is the same value the push writes. Two consequences fall out for
// free: the Measurement F false-drift class disappears (we compare parsed
// structures, so serializer style cannot register), and the differ depends on
// NONE of the six kcmd defects — in particular not defect 2, because it never
// goes through `kcmd pull`.
//
// ONE CODE PATH, TWO VERBS. `drift.ts` runs this with `--dry-run` semantics:
// compare and report, change nothing. The push scripts run the same function
// and stage only what it says differs. They cannot disagree about what
// constitutes a difference because they are the same comparison.
//
// WHY THE PLANNER MATTERS BEYOND SPEED. As shipped, `sync.ts` calls
// `modifyEntry` whenever the updateMask is non-empty, without checking whether
// anything changed — so every push bumps every `updateTime` and the server's
// timestamps, which are the ONLY drift evidence we cannot forge, degrade to a
// sound negative test. Staging only what differs makes them exact: after a
// push, moved <=> we wrote it, and thereafter moved <=> someone else did.
//
// THE RISK THIS INTRODUCES, NAMED. "Decide whether it needs pushing" means a
// false no-change verdict silently drops a real change — this repo's signature
// failure. The comparison is therefore CONSERVATIVE: any uncertainty counts as
// a difference. Unmatched keys, unrecognised structure, a failed read, a
// missing baseline — all push. Equality is only ever concluded from a complete,
// successful, structural match.

import * as fs from 'node:fs';
import * as path from 'node:path';
import { buildStagedEntry, splitFrontmatter } from './okf';
import { Tier, aspectId, behavesAsOwned, tierOf } from './tiers';

export type Verdict =
  | 'ok'
  | 'drift'          // owned content no longer matches what the bundle asserts
  | 'stale-cache'    // cache content moved on legitimately; our copy is behind
  | 'missing'        // we assert it and the catalog does not have it
  | 'foreign'        // someone else's aspect; noted, never failed on
  | 'unexpected';    // present, ours to explain, and we cannot

export interface ChannelFinding {
  concept: string;
  entry: string;
  channel: string;      // the aspect id, e.g. `overview`
  tier: Tier;
  verdict: Verdict;
  detail: string;
  updateTime?: string;  // the catalog's own, when it has one
  /**
   * The catalog's `updateTime` for this channel is NEWER than the one our last
   * push recorded — so this channel moved after we wrote it, and we did not
   * move it. This is the difference between "the bundle was edited" (safe to
   * push) and "something overwrote our projection" (stop and look).
   *
   * It is trustworthy for one measured reason: **Dataplex's per-aspect
   * `updateTime` is content-addressed.** 14 `modifyEntry` calls carrying
   * byte-identical aspect data moved the entry-level `updateTime` on all 14
   * entries and the aspect-level `updateTime` on ZERO of 241 aspects. So a
   * moved aspect timestamp means the aspect's CONTENT changed, not merely that
   * something wrote to the entry.
   */
  thirdParty?: boolean;
}

export interface ConceptPlan {
  rel: string;          // bundle-relative path without `.md`
  entryName: string;    // kcmd local name
  entryId: string;      // the Dataplex entry id
  expected: Record<string, any>;   // aspect key -> aspect data, as pushed
  body: string;
  actual?: any;         // the live entry, or undefined if absent / unreadable
  findings: ChannelFinding[];
  /** Conservative: true unless a complete structural match proved otherwise. */
  needsPush: boolean;
  reason: string;
}

const OVERVIEW_KEY = 'dataplex-types.global.overview';

// ---------------------------------------------------------------------------
// Normalisation — and only this much.
//
// Two real differences of FORM exist between what we send and what comes back,
// and neither is a difference of content:
//   1. aspect keys come back qualified by project NUMBER where we wrote project
//      ID (`404799090046.us.okf` vs `royston-dev-8253.us.okf`), exactly as the
//      built-ins surface as `655216118709.global.overview`;
//   2. JSON key order.
// (1) is handled by matching on the aspect id; (2) by comparing parsed values
// through a key-sorted serialisation. Nothing else is normalised — every other
// difference is a real one, and smoothing it over is how a differ becomes a
// thing people stop reading.

function stable(v: any): string {
  const walk = (x: any): any => {
    if (Array.isArray(x)) return x.map(walk);
    if (x && typeof x === 'object') {
      return Object.fromEntries(Object.keys(x).sort().map((k) => [k, walk(x[k])]));
    }
    return x;
  };
  return JSON.stringify(walk(v));
}

function byId(aspects: Record<string, any>): Map<string, { key: string; value: any }> {
  const out = new Map<string, { key: string; value: any }>();
  for (const [key, value] of Object.entries(aspects ?? {})) {
    out.set(aspectId(key), { key, value });
  }
  return out;
}

/** The manifest's `publishing.aspects`, so `expected` models what push SENDS. */
export function publishingAspects(manifestPath: string): Set<string> {
  const text = fs.readFileSync(manifestPath, 'utf8');
  const out = new Set<string>();
  let inPublishing = false, inAspects = false;
  for (const raw of text.split(/\r?\n/)) {
    if (/^publishing:/.test(raw)) { inPublishing = true; continue; }
    if (/^\S/.test(raw)) { inPublishing = false; inAspects = false; continue; }
    if (!inPublishing) continue;
    if (/^\s{2}aspects:/.test(raw)) { inAspects = true; continue; }
    if (/^\s{2}\S/.test(raw)) { inAspects = false; continue; }
    const m = inAspects && raw.match(/^\s*-\s*(\S+)/);
    if (m) out.add(aspectId(m[1]));
  }
  return out;
}

/**
 * What the push will actually write for one concept: the stash's aspects,
 * narrowed to `publishing.aspects`, plus the body as `overview`.
 *
 * Modelling the publishing filter is not a detail. `toServiceEntry` drops any
 * aspect the manifest does not publish, so an `expected` that ignored it would
 * report drift on channels we never send — and a differ that cries wolf on a
 * healthy system is worse than none.
 */
export function expectedAspects(
  content: string,
  okfKey: string,
  entryName: string,
  entryType: string,
  withAssetAspects: boolean,
  published: Set<string>,
): { aspects: Record<string, any>; body: string } | null {
  const built = buildStagedEntry(content, okfKey, entryName, entryType, withAssetAspects);
  if (!built) return null;
  const aspects: Record<string, any> = {};
  for (const [key, value] of Object.entries(built.stash.aspects ?? {})) {
    if (published.has(aspectId(key))) aspects[key] = value;
  }
  const body = built.body.trim();
  if (body && published.has('overview')) {
    aspects[OVERVIEW_KEY] = { content: body, contentType: 'MARKDOWN' };
  }
  return { aspects, body };
}

/**
 * Compare one concept's `expected` against one live entry.
 *
 * `lastPush` is the per-aspect `updateTime` recorded by the previous push's
 * sweep. Where it exists it upgrades the report from "these differ" to "someone
 * else wrote this, and here is when" — the multi-writer signal. Where it does
 * not, the comparison still stands on content alone.
 */
export function compareConcept(
  plan: ConceptPlan,
  lastPush?: Record<string, string>,
): ConceptPlan {
  const findings: ChannelFinding[] = [];
  const label = plan.rel;

  if (!plan.actual) {
    plan.findings = [{
      concept: label, entry: plan.entryId, channel: '(entry)', tier: Tier.BUNDLE,
      verdict: 'missing', detail: 'the entry does not exist in the catalog',
    }];
    plan.needsPush = true;
    plan.reason = 'entry absent';
    return plan;
  }

  const exp = byId(plan.expected);
  const act = byId(plan.actual.aspects ?? {});
  let differs = false;

  for (const [id, e] of exp) {
    const a = act.get(id);
    const owned = behavesAsOwned(e.key, e.value);
    const tier = tierOf(e.key);
    if (!a) {
      differs = true;
      findings.push({
        concept: label, entry: plan.entryId, channel: id, tier,
        verdict: owned ? 'drift' : 'stale-cache',
        detail: owned
          ? 'the bundle asserts this aspect and the catalog does not have it'
          : 'the scan owns this aspect at userManaged=false and it is absent',
      });
      continue;
    }
    // The live shape is `{aspectType, data, createTime, updateTime, ...}`;
    // what we assert is the `data` payload.
    const actualData = a.value?.data ?? a.value;
    if (stable(actualData) === stable(e.value)) continue;
    differs = true;
    const ts = a.value?.updateTime;
    const recorded = lastPush?.[id];
    const movedSinceOurPush = !!(ts && recorded && ts > recorded);
    findings.push({
      concept: label, entry: plan.entryId, channel: id, tier,
      verdict: owned ? 'drift' : 'stale-cache',
      updateTime: ts,
      thirdParty: movedSinceOurPush,
      detail: owned
        ? (movedSinceOurPush
            ? `content differs, and updateTime ${ts} is NEWER than our last push ` +
              `${recorded} — written by a third party`
            : 'content differs from what the bundle asserts')
        : (movedSinceOurPush
            ? `the scan refreshed this at ${ts} (after our push at ${recorded}); ` +
              `userManaged=false, so this is the system working`
            : 'the catalog holds a different value and owns it'),
    });
  }

  for (const [id, a] of act) {
    if (exp.has(id)) continue;
    const tier = tierOf(a.key);
    if (tier === Tier.PLATFORM) {
      // Never in `expected`, because we never assert it. Not drift. Phase 6
      // compares it against the bundle's mirrored cache; until a concept
      // carries that mirror there is nothing to be stale RELATIVE TO, so it is
      // reported as present-and-unmirrored rather than as a fault.
      findings.push({
        concept: label, entry: plan.entryId, channel: id, tier, verdict: 'ok',
        updateTime: a.value?.updateTime,
        detail: 'platform-owned; cached in the bundle, never pushed',
      });
      continue;
    }
    if (tier === Tier.FOREIGN) {
      findings.push({
        concept: label, entry: plan.entryId, channel: id, tier, verdict: 'foreign',
        updateTime: a.value?.updateTime,
        detail: 'not ours and not the platform\'s — noted, not failed on',
      });
      continue;
    }
    // A tier B or C aspect on the entry that the bundle does not assert. Either
    // the manifest stopped publishing it or someone added it by hand.
    findings.push({
      concept: label, entry: plan.entryId, channel: id, tier, verdict: 'unexpected',
      updateTime: a.value?.updateTime,
      detail: 'an aspect we own by tier but do not assert for this concept',
    });
  }

  // THE OWNERSHIP INVARIANT, checked on its own rather than folded into the
  // content comparison: does the catalog's `userManaged` match what we compute
  // from `verified`? A mismatch means policy and catalog disagree about WHO
  // OWNS the channel, which is a different fault from the content differing and
  // has a different remedy.
  for (const [id, e] of exp) {
    if (tierOf(e.key) !== Tier.CONTESTED) continue;
    const a = act.get(id);
    if (!a) continue;
    const actualFlag = (a.value?.data ?? a.value)?.userManaged === true;
    if (actualFlag !== (e.value?.userManaged === true)) {
      differs = true;
      findings.push({
        concept: label, entry: plan.entryId, channel: `${id}.userManaged`,
        tier: Tier.CONTESTED, verdict: 'drift',
        updateTime: a.value?.updateTime,
        detail: `the bundle computes userManaged=${e.value?.userManaged === true} ` +
                `from \`verified\`; the catalog says ${actualFlag}`,
      });
    }
  }

  plan.findings = findings;
  plan.needsPush = differs;
  plan.reason = differs ? 'content differs' : 'identical';
  return plan;
}

/**
 * The findings that make a push unsafe to proceed with: an OWNED channel that
 * something else wrote after our last push.
 *
 * This is kcmd spec §3.3's fail-fast — "fail fast if modified in the catalog in
 * the interim", with a `--force` override — implemented against SERVER TRUTH
 * rather than the client-side checksums §3.7 proposes. It is strictly better
 * than a `.catalog.state` file: the server is the authority on "did this
 * change", and there is no hash of ours that can be wrong or stale.
 *
 * Note what is NOT here. A concept that differs because THE BUNDLE was edited
 * is not a conflict — its aspect timestamps still match the baseline, since the
 * catalog has not moved since we wrote it. Pushing that is the normal case and
 * must not need a flag. Distinguishing the two is only possible because the
 * aspect timestamps are server-authored and content-addressed.
 *
 * Conservative on the missing-baseline case: with no `_state/last_push.json`,
 * `thirdParty` is never set, so nothing blocks. That is the right default for a
 * fresh clone — the alternative is a tool that refuses to run until it has
 * pushed once — and it is why the baseline is committed rather than ignored.
 */
export function conflicts(plans: ConceptPlan[]): ChannelFinding[] {
  return plans.flatMap((p) => p.findings)
    .filter((f) => f.thirdParty && f.verdict === 'drift');
}

/** Exit codes: 0 = no drift (stale caches are listed and do not fail), 1 = drift, 2 = tool error. */
export function exitCode(plans: ConceptPlan[], strict = false): number {
  const all = plans.flatMap((p) => p.findings);
  if (all.some((f) => f.verdict === 'drift' || f.verdict === 'missing'
                   || f.verdict === 'unexpected')) return 1;
  if (strict && all.some((f) => f.verdict === 'stale-cache')) return 1;
  return 0;
}

export function summarise(plans: ConceptPlan[]): string {
  const counts: Record<string, number> = {};
  for (const f of plans.flatMap((p) => p.findings)) {
    if (f.verdict === 'ok') continue;
    counts[f.verdict] = (counts[f.verdict] ?? 0) + 1;
  }
  const needs = plans.filter((p) => p.needsPush).length;
  return `${plans.length} concept(s); ${needs} need a push; findings ` +
         (Object.keys(counts).length ? JSON.stringify(counts) : '{}');
}

/** Where the post-push server timestamps live. Tracked, deliberately — see drift.ts. */
export function lastPushPath(root: string): string {
  return path.join(root, '_state', 'last_push.json');
}

export function readLastPush(root: string): Record<string, Record<string, string>> {
  const p = lastPushPath(root);
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : {};
}
