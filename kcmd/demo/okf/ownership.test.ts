// Offline tests for the projection rule. No catalog, no scans.
//   bun kcmd/demo/okf/ownership.test.ts
//
// The rule: the bundle always projects overview + descriptions + queries, and
// `userManaged` on descriptions/queries equals whether the concept is verified.
import * as fs from 'node:fs';
import * as path from 'node:path';
import { splitFrontmatter, assetAspects, schemaFields, queryPatterns,
         toOkfStaging } from './okf';
import { desiredRelatedLinks } from './bundle';

let pass = 0, fail = 0;
const ok = (name: string, cond: boolean, detail = '') => {
  if (cond) { pass++; console.log(`  PASS  ${name}`); }
  else { fail++; console.log(`  FAIL  ${name} ${detail}`); }
};

const ROOT = path.resolve(import.meta.dirname ?? __dirname, '../../..');
const read = (p: string) => splitFrontmatter(fs.readFileSync(`${ROOT}/${p}`, 'utf8'));
const D = 'dataplex-types.global.descriptions';
const Q = 'dataplex-types.global.queries';
const V = [{ by: 'human:x', at: '2026-01-01T00:00:00+00:00' }];

const { meta, body } = read('okf-bundle/tables/customers.md');

console.log('userManaged tracks verified');
const yes = assetAspects({ ...meta, verified: V }, body);
const no  = assetAspects({ ...meta, verified: undefined }, body);
ok('verified   -> descriptions.userManaged true',  yes[D].userManaged === true);
ok('verified   -> queries.userManaged true',       yes[Q].userManaged === true);
ok('unverified -> descriptions.userManaged false', no[D].userManaged === false);
ok('unverified -> queries.userManaged false',      no[Q].userManaged === false);
ok('empty verified array counts as unverified',
   assetAspects({ ...meta, verified: [] }, body)[D].userManaged === false);

console.log('content is projected either way — verified only decides protection');
ok('unverified still writes descriptions', !!no[D]);
ok('unverified still writes queries',      !!no[Q]);
ok('same field count regardless of verified',
   yes[D].fields.length === no[D].fields.length);
ok('same query count regardless of verified',
   yes[Q].queries.length === no[Q].queries.length);

console.log('body parsing');
ok('a column literally called `name` is not eaten',
   schemaFields(body).some((f) => f.name === 'name'));
ok('customers documents all 8 columns', schemaFields(body).length === 8);
ok('query patterns are extracted',      queryPatterns(body).length > 0);

console.log('every table in the bundle projects both aspects');
let n = 0;
for (const f of fs.readdirSync(`${ROOT}/okf-bundle/tables`)) {
  if (!f.endsWith('.md') || f === 'index.md') continue;
  const d = read(`okf-bundle/tables/${f}`);
  const a = assetAspects(d.meta, d.body);
  const expected = Array.isArray(d.meta.verified) && d.meta.verified.length > 0;
  ok(`${f}: 2 aspects, userManaged=${expected}`,
     !!a[D] && !!a[Q] && a[D].userManaged === expected && a[Q].userManaged === expected);
  n++;
}
ok('all 13 tables exercised', n === 13, `(got ${n})`);

// ---------------------------------------------------------------------------
// The two derivations of the related map must agree.
//
// `desiredRelatedLinks` (TS, here) drives the 58 `related` EntryLinks;
// `desired_related_links` (Python, okf-review/postauthor.py) drives the
// `# Related concepts` back-link sections in the bundle. Same source, same
// rule, two languages — the same shape as `canonicalize.py` duplicating
// reference_agent's key order, and guarded the same way.
//
// Comparing the TS map against the sections ALREADY IN THE BUNDLE is what makes
// this a real check rather than a restatement: if the link-form migration had
// broken only the TS regex, the map would go to zero here while the bundle's
// sections stayed full, and this fails offline instead of the link layer
// vanishing on the next push.
console.log('the related map: TS derivation vs the bundle back-link sections');
const bundleDir = `${ROOT}/okf-bundle`;
const derived = desiredRelatedLinks(bundleDir);
ok('TS derivation is non-empty', derived.size > 0, `(got ${derived.size} tables)`);

let mismatches = 0, rendered = 0;
for (const [table, concepts] of [...derived].sort()) {
  const file = `${bundleDir}/tables/${table}.md`;
  if (!fs.existsSync(file)) continue;
  const { body } = splitFrontmatter(fs.readFileSync(file, 'utf8'));
  const section = body.split(/^#\s+Related concepts\s*$/m)[1] ?? '';
  const cut = section.split(/^#(?!#)\s/m)[0];
  const listed = new Set(
    [...cut.matchAll(/\]\(\/(references\/[^)]+?)\.md\)/g)].map((m) => m[1]),
  );
  rendered++;
  const missing = [...concepts].filter((c) => !listed.has(c));
  const extra = [...listed].filter((c) => !concepts.has(c));
  if (missing.length || extra.length) {
    mismatches++;
    console.log(`        ${table}: missing ${JSON.stringify(missing)} ` +
                `extra ${JSON.stringify(extra)}`);
  }
}
ok('every table with references has a rendered section',
   rendered === derived.size, `(${rendered}/${derived.size})`);
ok('the two derivations agree on every table', mismatches === 0,
   `(${mismatches} table(s) disagree — run okf-review/postauthor.py --write)`);
const totalRefs = [...derived.values()].reduce((a, s) => a + s.size, 0);
ok('the map still carries all 58 concept->table references', totalRefs === 58,
   `(got ${totalRefs})`);

// ---------------------------------------------------------------------------
// The kcmd-native staged form.
//
// These are the properties an UNMODIFIED kcmd needs, asserted offline so the
// interop claim is not something only a live push can check. Each one
// corresponds to a way the previous `catalogEntry` form failed silently.
console.log('staged form: x-kcmd');
const OKF_KEY = 'royston-dev-8253.us.okf';
const GENERIC = 'dataplex-types.global.generic';
const SIGNAL = ['okf_type', 'generated', 'sources', 'verified', 'status',
                'stale_after', 'title', 'tags'];

let stagedN = 0, badType = 0, noGeneric = 0, lostSignal = 0, bodyChanged = 0;
// Walked, not enumerated. An earlier version listed the concept directories by
// hand and quietly checked 56 of 58 — it had been written before
// `references/hierarchies` and `references/derived` existed, which is the
// silent-undercount shape this suite is supposed to catch, not exhibit.
const walkMd = (d: string, prefix = ''): string[] =>
  fs.readdirSync(d, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walkMd(`${d}/${e.name}`, `${prefix}${e.name}/`)
    : e.name.endsWith('.md') && e.name !== 'index.md' && e.name !== 'log.md'
      ? [`${prefix}${e.name}`] : []);
const bundleFiles = walkMd(bundleDir);

for (const rel of bundleFiles) {
  const src = fs.readFileSync(`${bundleDir}/${rel}`, 'utf8');
  const { meta: srcMeta, body: srcBody } = splitFrontmatter(src);
  const assetBacked = !!srcMeta.resource;
  // Track A echoes the live Dataplex type; offline, stand in the one this
  // dataset's 13 BASE TABLEs actually have. Track B is always generic.
  const entryType = assetBacked
    ? (rel.startsWith('datasets/') ? 'dataplex-types.global.bigquery-dataset'
                                   : 'dataplex-types.global.bigquery-table')
    : GENERIC;
  const name = assetBacked ? `bigquery/p/d/${rel.split('/').pop()!.slice(0, -3)}`
                           : rel.slice(0, -3);
  const out = toOkfStaging(src, OKF_KEY, name, entryType, assetBacked);
  const { meta, body } = splitFrontmatter(out);
  const stash = meta['x-kcmd'];
  stagedN++;

  // DEFECT 4's root cause, as an assertion. An entry type that is not a 3-part
  // dotted ref is silently rewritten to `generic` by `parseOkf`, and the
  // publishing filter then drops the entry against an allowlist it can never
  // match. `type:` in the frontmatter stays the OKF vocabulary (rule 4), so the
  // Dataplex type has to be carried — and carried correctly — in the stash.
  if (!stash || String(stash.type).split('.').length !== 3) badType++;
  if (meta.type !== srcMeta.type) badType++;
  // Dataplex rejects create with 400 "Missing required Aspect(s)" if the
  // aspect matching the entry's type is absent. Required exactly for generic.
  const hasGeneric = !!stash?.aspects?.[GENERIC];
  if ((entryType === GENERIC) !== hasGeneric) noGeneric++;
  // The signal layer has no generic home; losing it loses OKF.
  const okf = stash?.aspects?.[OKF_KEY] ?? {};
  for (const k of SIGNAL) {
    const present = (k === 'okf_type' ? srcMeta.type : srcMeta[k]) !== undefined;
    if (present && okf[k] === undefined) lostSignal++;
  }
  // The body IS the concept and becomes `overview.content` verbatim.
  if (body.trim() !== srcBody.trim()) bodyChanged++;
}
ok('every concept stages', stagedN === 58, `(got ${stagedN})`);
ok('x-kcmd.type is a 3-part Dataplex ref, and `type:` keeps the OKF vocabulary',
   badType === 0, `(${badType} violation(s))`);
ok('the generic aspect is present exactly on generic entries',
   noGeneric === 0, `(${noGeneric} violation(s))`);
ok('no okf signal field is dropped', lostSignal === 0, `(${lostSignal} dropped)`);
ok('the body passes through verbatim', bodyChanged === 0, `(${bodyChanged} changed)`);

// `overview` must NOT be in the stash: OkfLayout._loadLayer promotes the body
// into it, so staging it too would push the body twice.
{
  const src = fs.readFileSync(`${bundleDir}/tables/accounts.md`, 'utf8');
  const st = splitFrontmatter(toOkfStaging(src, OKF_KEY, 'x', 'dataplex-types.global.bigquery-table', true))
    .meta['x-kcmd'];
  const keys = Object.keys(st.aspects);
  ok('the stash carries no overview aspect (the body is the overview)',
     !keys.some((k) => k.endsWith('overview')), `(${keys.join(', ')})`);
  ok('an asset-backed stash carries descriptions + queries + okf',
     keys.includes('dataplex-types.global.descriptions')
     && keys.includes('dataplex-types.global.queries')
     && keys.includes(OKF_KEY), `(${keys.join(', ')})`);
}

// RULE 1, AS AN ASSERTION RATHER THAN A CONVENTION: no stash in the SOURCE.
// The staged tree is a build artifact and gitignored; the bundle is the record.
// This is the check that would fire if someone ever pointed a pull at
// `okf-bundle/`, which is the one accident that would corrupt it.
{
  let stashed = 0;
  const walk = (d: string): string[] => fs.readdirSync(d, { withFileTypes: true })
    .flatMap((e) => e.isDirectory() ? walk(`${d}/${e.name}`)
                  : e.name.endsWith('.md') ? [`${d}/${e.name}`] : []);
  for (const f of walk(bundleDir)) {
    const t = fs.readFileSync(f, 'utf8');
    if (/^x-kcmd:/m.test(t) || /^\s*catalogEntry:/m.test(t)) stashed++;
  }
  ok('no file in okf-bundle/ carries a stash key', stashed === 0,
     `(${stashed} file(s) do)`);
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
