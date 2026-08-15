// Offline tests for the projection and the comparator. No catalog, no
// credentials, no network.
//   bun kcmd/demo/okf/drift.test.ts
//
// TWO GUARDS, and the plan is explicit that these should land even if nothing
// else does, because between them they make the differ testable rather than
// merely observable in a live run:
//
//   1. PROJECTION DETERMINISM. `expected` must be a pure function of the
//      bundle. This also gates the emitter itself — `expected` IS the object
//      the push sends, so a determinism failure is a PUSH bug found offline.
//   2. THE COMPARATOR, against a recorded `getEntry` response. One Track A
//      entry and one Track B entry, captured at `view=ALL` from the live
//      catalog immediately after a clean push, so "clean" is the known-correct
//      answer and any change to the comparator that breaks it shows up here
//      instead of as a red report nobody trusts.

import * as fs from 'node:fs';
import * as path from 'node:path';
import { compareConcept, expectedAspects, ConceptPlan } from './plan';
import { tierOf, Tier, behavesAsOwned } from './tiers';

let pass = 0, fail = 0;
const ok = (name: string, cond: boolean, detail = '') => {
  if (cond) { pass++; console.log(`  PASS  ${name}`); }
  else { fail++; console.log(`  FAIL  ${name} ${detail}`); }
};

const REPO = path.resolve(import.meta.dirname ?? __dirname, '../../..');
const BUNDLE = path.join(REPO, 'okf-bundle');
const FIX = path.join(REPO, 'kcmd/demo/okf/fixtures');
const OKF_KEY = 'royston-dev-8253.us.okf';
const GENERIC = 'dataplex-types.global.generic';
const PUB_A = new Set(['okf', 'overview', 'descriptions', 'queries']);
const PUB_B = new Set(['generic', 'overview', 'okf']);

const walk = (d: string, p = ''): string[] =>
  fs.readdirSync(d, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(path.join(d, e.name), `${p}${e.name}/`)
    : e.name.endsWith('.md') && e.name !== 'index.md' && e.name !== 'log.md'
      ? [`${p}${e.name}`] : []);

// ---------------------------------------------------------------------------
console.log('projection determinism');
{
  let differs = 0, n = 0;
  for (const rel of walk(BUNDLE)) {
    const content = fs.readFileSync(path.join(BUNDLE, rel), 'utf8');
    const assetBacked = /^(tables|datasets)\//.test(rel);
    const type = assetBacked
      ? (rel.startsWith('datasets/') ? 'dataplex-types.global.bigquery-dataset'
                                     : 'dataplex-types.global.bigquery-table')
      : GENERIC;
    const args = [content, OKF_KEY, rel.slice(0, -3), type, assetBacked,
                  assetBacked ? PUB_A : PUB_B] as const;
    const a = expectedAspects(...args);
    const b = expectedAspects(...args);
    n++;
    if (JSON.stringify(a) !== JSON.stringify(b)) differs++;
  }
  ok('expected is a pure function of the bundle', differs === 0,
     `(${differs} of ${n} concepts differ between two builds)`);
  ok('all 58 concepts project', n === 58, `(got ${n})`);
}

// ---------------------------------------------------------------------------
console.log('the tier table');
{
  ok('schema is platform-owned', tierOf('655216118709.global.schema') === Tier.PLATFORM);
  ok('overview is bundle-owned', tierOf('dataplex-types.global.overview') === Tier.BUNDLE);
  ok('descriptions is contested', tierOf('655216118709.global.descriptions') === Tier.CONTESTED);
  ok('an unknown aspect is foreign', tierOf('someone-else.us.their-aspect') === Tier.FOREIGN);
  // The tier is keyed on the aspect ID, because the same aspect comes back
  // qualified by project NUMBER where we wrote project ID.
  ok('project-number and project-id forms resolve to the same tier',
     tierOf('404799090046.us.okf') === tierOf('royston-dev-8253.us.okf'));

  // TIER C IS A RUNTIME SWITCH, NOT A THIRD BEHAVIOUR — the single most
  // load-bearing claim in the ownership model, so it is asserted rather than
  // asserted in prose.
  const D = '655216118709.global.descriptions';
  ok('tier C at userManaged=true behaves as OWNED (tier B)',
     behavesAsOwned(D, { userManaged: true }) === true);
  ok('tier C at userManaged=false behaves as CACHE (tier A)',
     behavesAsOwned(D, { userManaged: false }) === false);
  ok('tier B is owned regardless of any flag',
     behavesAsOwned('dataplex-types.global.overview', {}) === true);
  ok('tier A is never owned',
     behavesAsOwned('655216118709.global.schema', { userManaged: true }) === false);
}

// ---------------------------------------------------------------------------
console.log('the comparator, against recorded getEntry responses');

function planFor(rel: string, entryId: string, assetBacked: boolean): ConceptPlan {
  const content = fs.readFileSync(path.join(BUNDLE, `${rel}.md`), 'utf8');
  const type = assetBacked ? 'dataplex-types.global.bigquery-table' : GENERIC;
  const exp = expectedAspects(content, OKF_KEY, rel, type, assetBacked,
                              assetBacked ? PUB_A : PUB_B)!;
  return {
    rel, entryName: rel, entryId, expected: exp.aspects, body: exp.body,
    actual: undefined, findings: [], needsPush: true, reason: '',
  };
}

const CASES: Array<[string, string, boolean]> = [
  ['references/grain/accounts', 'trackB_grain_accounts', false],
  ['tables/investors', 'trackA_investors', true],
];

for (const [rel, fixture, assetBacked] of CASES) {
  const actual = JSON.parse(fs.readFileSync(path.join(FIX, `${fixture}.json`), 'utf8'));
  const p = compareConcept({ ...planFor(rel, fixture, assetBacked), actual });
  const bad = p.findings.filter((f) => f.verdict !== 'ok');
  ok(`${rel}: comparator reports clean`, bad.length === 0,
     `(${JSON.stringify(bad.map((f) => `${f.channel}:${f.verdict}`))})`);
  ok(`${rel}: nothing needs pushing`, p.needsPush === false, `(${p.reason})`);
}

// The Track A fixture carries schema/storage/bigquery-* — the tier-A aspects we
// never assert. A comparator that reported those as drift would fail on a
// healthy system, which is the way a differ becomes something people ignore.
{
  const actual = JSON.parse(fs.readFileSync(path.join(FIX, 'trackA_investors.json'), 'utf8'));
  const p = compareConcept({ ...planFor('tables/investors', 'x', true), actual });
  const platform = p.findings.filter((f) => f.tier === Tier.PLATFORM);
  ok('the 4 platform aspects present on the entry are recognised, not flagged',
     platform.length >= 4 && platform.every((f) => f.verdict === 'ok'),
     `(${platform.map((f) => `${f.channel}:${f.verdict}`).join(', ')})`);
  ok('no tier-A aspect is ever in `expected`',
     Object.keys(p.expected).every((k) => tierOf(k) !== Tier.PLATFORM),
     `(${Object.keys(p.expected).join(', ')})`);
}

// ---------------------------------------------------------------------------
console.log('the comparator FIRES — the check that makes it worth having');
{
  const base = JSON.parse(fs.readFileSync(path.join(FIX, 'trackA_investors.json'), 'utf8'));

  // (a) tier B content changed -> DRIFT
  {
    const actual = JSON.parse(JSON.stringify(base));
    const k = Object.keys(actual.aspects).find((x) => x.endsWith('.overview'))!;
    actual.aspects[k].data.content = 'someone edited this in the UI';
    const p = compareConcept({ ...planFor('tables/investors', 'x', true), actual });
    const f = p.findings.find((x) => x.channel === 'overview');
    ok('an edited overview is DRIFT', f?.verdict === 'drift', `(${f?.verdict})`);
    ok('and it needs a push', p.needsPush === true);
  }

  // (b) tier C at userManaged=TRUE, content changed -> DRIFT (ownership failed)
  {
    const actual = JSON.parse(JSON.stringify(base));
    const k = Object.keys(actual.aspects).find((x) => x.endsWith('.descriptions'))!;
    actual.aspects[k].data.description = 'the scan rewrote this';
    const p = compareConcept({ ...planFor('tables/investors', 'x', true), actual });
    const f = p.findings.find((x) => x.channel === 'descriptions');
    ok('a scan overwriting a VERIFIED concept is DRIFT', f?.verdict === 'drift',
       `(${f?.verdict})`);
  }

  // (c) THE SAME OBSERVATION at userManaged=FALSE -> STALE CACHE.
  // Same signal, opposite meaning, decided by nothing but the flag. This is the
  // tier-C switch, and it is the reason the two verdicts exist: conflate them
  // and every routine scan run shows up red, people stop reading the report,
  // and a genuine ownership failure is ignored along with the noise.
  {
    const actual = JSON.parse(JSON.stringify(base));
    const k = Object.keys(actual.aspects).find((x) => x.endsWith('.descriptions'))!;
    actual.aspects[k].data.description = 'the scan rewrote this';
    const p0 = planFor('tables/investors', 'x', true);
    const ek = Object.keys(p0.expected).find((x) => x.endsWith('.descriptions'))!;
    p0.expected[ek] = { ...p0.expected[ek], userManaged: false };
    actual.aspects[k].data.userManaged = false;
    const p = compareConcept({ ...p0, actual });
    const f = p.findings.find((x) => x.channel === 'descriptions');
    ok('the SAME change on an UNVERIFIED concept is STALE CACHE',
       f?.verdict === 'stale-cache', `(${f?.verdict})`);
  }

  // (d) the ownership invariant, reported on its own
  {
    const actual = JSON.parse(JSON.stringify(base));
    const k = Object.keys(actual.aspects).find((x) => x.endsWith('.queries'))!;
    actual.aspects[k].data.userManaged = false;
    const p = compareConcept({ ...planFor('tables/investors', 'x', true), actual });
    const f = p.findings.find((x) => x.channel === 'queries.userManaged');
    ok('a userManaged mismatch is reported as its own finding',
       f?.verdict === 'drift', `(${f?.verdict})`);
  }

  // (e) an aspect we assert that the catalog does not have
  {
    const actual = JSON.parse(JSON.stringify(base));
    const k = Object.keys(actual.aspects).find((x) => x.endsWith('.okf'))!;
    delete actual.aspects[k];
    const p = compareConcept({ ...planFor('tables/investors', 'x', true), actual });
    const f = p.findings.find((x) => x.channel === 'okf');
    ok('a missing owned aspect is DRIFT', f?.verdict === 'drift', `(${f?.verdict})`);
  }

  // (f) somebody else's aspect: noted, never failed on
  {
    const actual = JSON.parse(JSON.stringify(base));
    actual.aspects['some-other-team.us.lineage'] = { data: { x: 1 } };
    const p = compareConcept({ ...planFor('tables/investors', 'x', true), actual });
    const f = p.findings.find((x) => x.channel === 'lineage');
    ok('a foreign aspect is noted, not failed on', f?.verdict === 'foreign',
       `(${f?.verdict})`);
    ok('and it does not force a push', p.needsPush === false);
  }

  // (g) SERIALIZER NOISE IS NOT DRIFT. Measurement F needed a canonicaliser
  // because it compared Python-written TEXT to JS-written TEXT. This compares
  // parsed structures, so key order cannot register — asserted, because "it
  // cannot happen by construction" is exactly the claim that rots.
  {
    const actual = JSON.parse(JSON.stringify(base));
    const k = Object.keys(actual.aspects).find((x) => x.endsWith('.okf'))!;
    const d = actual.aspects[k].data;
    actual.aspects[k].data = Object.fromEntries(Object.keys(d).reverse().map((x) => [x, d[x]]));
    const p = compareConcept({ ...planFor('tables/investors', 'x', true), actual });
    ok('reordering an aspect\'s keys is not a difference', p.needsPush === false,
       `(${p.findings.filter((f) => f.verdict !== 'ok').map((f) => f.channel)})`);
  }

  // (h) a missing entry stages, and is not silently "clean"
  {
    const p = compareConcept({ ...planFor('tables/investors', 'x', true), actual: undefined });
    ok('an absent entry is MISSING and needs a push',
       p.needsPush === true && p.findings[0]?.verdict === 'missing');
  }
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
