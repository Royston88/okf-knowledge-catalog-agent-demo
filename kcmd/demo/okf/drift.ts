// `drift` — does the catalog still match what the bundle asserts, and where not?
//
//   bun kcmd/demo/okf/drift.ts                 report; exit 0 clean, 1 drift, 2 error
//   bun kcmd/demo/okf/drift.ts --strict        make stale caches fail too
//   bun kcmd/demo/okf/drift.ts --sweep         record the post-push baseline
//   bun kcmd/demo/okf/drift.ts --json          machine-readable findings
//
// This is rule 3, implemented: *pull is a diff for owned content and a refresh
// for mirrored content, and it never writes an owned field.* The original
// wording — "pull is a diff, not a source" — was written to stop an
// edit-in-the-UI-then-pull workflow re-establishing two sources of truth. That
// danger is specific to OWNED content; for mirrored content there is only ever
// one source, the platform, and the bundle is a cache of it.
//
// WHAT THIS DELIBERATELY CANNOT DO: write to `okf-bundle/`. No flag, no escape
// hatch. The remedy for drift is always *fix the bundle and re-push*, which is
// also the remedy shown to work — RESULTS §5 records all four historical
// projection breakages recovering that way, because the bundle was
// authoritative. So this buys a safe READ direction without a write-back path,
// and under this design it never becomes one.
//
// IT DOES NOT GO THROUGH `kcmd pull`, and that is not a style preference. The
// catalog stamps `Entry.updateTime`, per-`Aspect` `updateTime` and
// `EntryLink.updateTime`, and MEASURED at `view=ALL` all 109 aspects on these
// entries carry theirs. Those are the only drift evidence we cannot forge —
// `toServiceEntry` never sends them, so Dataplex is their sole author. kcmd
// threw all of them away in two places (`_fixEntry` rebuilt each aspect as
// `{aspectType, data}`; `toLocalEntry` then kept only `.data`), both now fixed.
//
// THE MULTI-WRITER ASSUMPTION, stated so this can verify it rather than assume
// it. Policy is that exactly two writers touch the catalog: our push, and the
// Dataplex scans. That is enforced by process, not by the platform. Because the
// server timestamps are unforgeable, a third-party write shows up as
// *unexplained* — newer than our recorded push, with no matching scan movement
// — rather than silently.

import * as fs from 'node:fs';
import * as path from 'node:path';
import {
  ConceptPlan, compareConcept, exitCode, expectedAspects, lastPushPath,
  publishingAspects, readLastPush, summarise,
} from './plan';
import { resolveTargets, Target } from './targets';
import { aspectId } from './tiers';
import { okfKey, project, location, entryGroup } from './config';

const REPO = path.resolve(import.meta.dirname ?? __dirname, '../../..');
const BUNDLE = process.env.OKF_BUNDLE
  ? path.resolve(process.env.OKF_BUNDLE) : path.join(REPO, 'okf-bundle');
const DATASET = process.env.OKF_BQ_DATASET;
if (!DATASET) throw new Error('OKF_BQ_DATASET is not set');

const MANIFEST = {
  A: path.join(REPO, 'bq-okf-workspace', 'catalog.yaml'),
  B: path.join(REPO, 'okf-kb-workspace', 'catalog.yaml'),
};

const GENERIC = 'dataplex-types.global.generic';
const BUILTIN_TYPE_PROJECT = 'dataplex-types';

async function client() {
  const token = process.env.KCMD_ACCESS_TOKEN;
  if (!token) {
    throw new Error(
      'KCMD_ACCESS_TOKEN is not set. Without it the CLI mints a token from the ' +
      'globally active gcloud config, which is a different identity.');
  }
  const kcmd = await import(path.resolve(import.meta.dirname ?? __dirname,
    '../../build/ts/tool/libts/index.js'));
  return new kcmd.dataplex.CatalogClient(
    new kcmd.gcp.ApiContext(project, location, token));
}

/**
 * Build the plan for every concept: `expected` from the bundle, `actual` from
 * the catalog, then compare.
 *
 * Exported so the push scripts can use the SAME function as their planner.
 * `drift` is this with the apply step omitted; `push` is this followed by it.
 * They cannot disagree about what constitutes a difference.
 */
export async function buildPlan(
  opts: { tracks?: Array<'A' | 'B'> } = {},
): Promise<{ plans: ConceptPlan[]; orphans: string[]; readFailures: string[] }> {
  const cat = await client();
  const tracks = opts.tracks ?? ['A', 'B'];
  const targets = resolveTargets(BUNDLE, {
    project, location, dataset: DATASET, entryGroup,
  }).filter((t) => tracks.includes(t.track));

  const published = {
    A: publishingAspects(MANIFEST.A),
    B: publishingAspects(MANIFEST.B),
  };
  const lastPush = readLastPush(REPO);

  const plans: ConceptPlan[] = [];
  const readFailures: string[] = [];

  for (const t of targets) {
    const content = fs.readFileSync(t.file, 'utf8');
    const res = await cat.getEntry(
      project, location, t.entryGroup, t.entryId, undefined, 'ALL');
    let actual: any | undefined;
    if (res.status === 200 && res.result) {
      actual = res.result;
    } else if (res.status !== 404) {
      // CONSERVATIVE. A read we could not complete is not evidence of equality.
      readFailures.push(`${t.rel}: HTTP ${res.status}`);
    }

    // Track A must echo the live entry type; it cannot be synthesised offline
    // (a view would be wrongly stamped `bigquery-table`). With no live entry
    // there is nothing to compare against anyway.
    const entryType = t.track === 'B' ? GENERIC
      : actual ? `${BUILTIN_TYPE_PROJECT}.${String(actual.entryType).split('/')[3]}.` +
                 `${String(actual.entryType).split('/')[5]}`
      : GENERIC;

    const exp = expectedAspects(
      content, okfKey, t.entryName, entryType, t.withAssetAspects,
      published[t.track]);
    if (!exp) continue;

    const plan: ConceptPlan = {
      rel: t.rel, entryName: t.entryName, entryId: t.entryId,
      expected: exp.aspects, body: exp.body, actual,
      findings: [], needsPush: true, reason: 'not compared',
    };
    if (readFailures.some((f) => f.startsWith(`${t.rel}:`))) {
      plan.reason = 'read failed — pushing, because an unread entry is not a match';
      plans.push(plan);
      continue;
    }
    plans.push(compareConcept(plan, lastPush[t.rel]));
  }

  // ORPHANS — new capability, not a rename. Under total-declarative push
  // semantics an entry in our EntryGroup that the bundle does not declare IS
  // drift, and nothing before this would have seen it.
  const orphans: string[] = [];
  if (tracks.includes('B')) {
    const declared = new Set(targets.filter((t) => t.track === 'B').map((t) => t.entryId));
    // The 7 synthetic directory entries are declared by the LAYOUT rather than
    // by a concept file, and the EntryGroup's own auto-created self-entry is
    // declared by nobody. Neither is an orphan.
    for await (const e of cat.listEntries(project, location, entryGroup)) {
      const id = String(e.name).split('/entries/')[1];
      if (!id || declared.has(id)) continue;
      if (id === 'index' || id.endsWith('/index')) continue;
      if (String(e.entryType).endsWith('/entrygroup')) continue;
      orphans.push(id);
    }
  }
  return { plans, orphans, readFailures };
}

/**
 * Read back the server's timestamps for everything we just pushed and record
 * them as the drift baseline.
 *
 * `_state/` is TRACKED in this repo — `g_before.json`, `g_after.json` and
 * `g_restored.json` are committed as Measurement G evidence — so this produces
 * a git diff on every push that changes anything. That is a deliberate trade
 * and the plan's own recommendation: a drift baseline that does not survive a
 * clone cannot support the CI use this is for, and the churn is one small file.
 *
 * Always the SERVER's timestamps from the response, never local wall-clock: no
 * clock skew, and no trust in our own idea of when the push finished.
 */
export async function sweep(): Promise<number> {
  const cat = await client();
  const targets = resolveTargets(BUNDLE, {
    project, location, dataset: DATASET, entryGroup,
  });
  const out: Record<string, Record<string, string>> = {};
  let n = 0;
  for (const t of targets) {
    const res = await cat.getEntry(
      project, location, t.entryGroup, t.entryId, undefined, 'ALL');
    if (res.status !== 200 || !res.result) continue;
    const rec: Record<string, string> = { '(entry)': res.result.updateTime ?? '' };
    for (const [key, a] of Object.entries<any>(res.result.aspects ?? {})) {
      if (a?.updateTime) rec[aspectId(key)] = a.updateTime;
    }
    out[t.rel] = rec;
    n++;
  }
  const p = lastPushPath(REPO);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(out, null, 2) + '\n');
  console.log(`swept ${n} entr(ies) -> ${path.relative(REPO, p)}`);
  return 0;
}

/**
 * Re-capture the offline comparator fixtures from the live catalog.
 *
 * THE FIXTURES ARE THEMSELVES A CACHE, AND THEY GO STALE. They record a
 * `view=ALL` response taken immediately after a clean push, so "the comparator
 * reports clean" is the known-correct answer. Change the bundle — as Phase 6's
 * mirror did, adding `# Data characteristics` to the body and `stale_after` to
 * the `okf` aspect — and the fixtures describe a catalog that no longer exists,
 * so `drift.test.ts` fails on `okf:drift` and `overview:drift`.
 *
 * That failure is CORRECT and should not be papered over: the offline suite
 * noticing that its own ground truth moved is the suite working. The remedy is
 * to push, confirm `drift.ts` is clean, and re-capture here — in that order,
 * because capturing from a catalog that has drifted would bake the drift in as
 * the expected answer, and the offline suite would then never fail again.
 *
 *     bun kcmd/demo/okf/drift.ts --capture-fixtures
 */
async function captureFixtures(): Promise<number> {
  const { plans } = await buildPlan();
  const dirty = plans.filter((p) => p.needsPush);
  if (dirty.length) {
    console.error(
      `REFUSING: ${dirty.length} concept(s) differ from the catalog ` +
      `(${dirty.slice(0, 3).map((p) => p.rel).join(', ')}…). Capturing now would ` +
      `record the drift as the expected answer. Push first, confirm ` +
      `\`drift.ts\` exits 0, then re-run.`);
    return 2;
  }
  const cat = await client();
  const dir = path.join(REPO, 'kcmd/demo/okf/fixtures');
  fs.mkdirSync(dir, { recursive: true });
  const want: Array<[string, string, string]> = [
    ['trackB_grain_accounts', entryGroup, 'references/grain/accounts'],
    ['trackA_investors', '@bigquery',
     `bigquery.googleapis.com/projects/${project}/datasets/${DATASET}/tables/investors`],
  ];
  for (const [name, group, id] of want) {
    const res = await cat.getEntry(project, location, group, id, undefined, 'ALL');
    if (res.status !== 200 || !res.result) {
      console.error(`failed to read ${id}: HTTP ${res.status}`);
      return 2;
    }
    const p = path.join(dir, `${name}.json`);
    fs.writeFileSync(p, JSON.stringify(res.result, null, 2) + '\n');
    console.log(`captured ${name} (${Object.keys(res.result.aspects ?? {}).length} aspects)`);
  }
  return 0;
}

async function main(): Promise<number> {
  const argv = process.argv.slice(2);
  if (argv.includes('--sweep')) return sweep();
  if (argv.includes('--capture-fixtures')) return captureFixtures();
  const strict = argv.includes('--strict');

  const { plans, orphans, readFailures } = await buildPlan();

  if (argv.includes('--json')) {
    console.log(JSON.stringify({ plans, orphans, readFailures }, null, 2));
  } else {
    const interesting = plans.flatMap((p) => p.findings)
      .filter((f) => f.verdict !== 'ok');
    for (const f of interesting) {
      const ts = f.updateTime ? `  [${f.updateTime}]` : '';
      console.log(`${f.verdict.toUpperCase().padEnd(12)} ${f.concept}  ` +
                  `${f.channel} (tier ${f.tier})${ts}\n             ${f.detail}`);
    }
    for (const o of orphans) {
      console.log(`UNEXPECTED   ${o}  (entry)\n             ` +
                  `an entry exists in ${entryGroup} that the bundle does not declare`);
    }
    for (const r of readFailures) {
      console.log(`READ FAILED  ${r}`);
    }
    console.log(`\n${summarise(plans)}`);
    if (orphans.length) console.log(`${orphans.length} orphan entr(ies)`);
    const stale = plans.flatMap((p) => p.findings)
      .filter((f) => f.verdict === 'stale-cache').length;
    if (stale) {
      console.log(`${stale} stale cache(s) — NOT a fault. The warehouse or the ` +
                  `scan moved on legitimately; refresh, review, commit.` +
                  (strict ? ' (--strict: failing anyway)' : ''));
    }
  }

  if (readFailures.length) return 2;
  const code = exitCode(plans, strict) || (orphans.length ? 1 : 0);
  console.log(code === 0 ? 'NO DRIFT' : 'DRIFT');
  return code;
}

if (import.meta.main) {
  process.exit(await main());
}
