// Offline tests for the projection rule. No catalog, no scans.
//   bun kcmd/demo/okf/ownership.test.ts
//
// The rule: the bundle always projects overview + descriptions + queries, and
// `userManaged` on descriptions/queries equals whether the concept is verified.
import * as fs from 'node:fs';
import { splitFrontmatter, assetAspects, schemaFields, queryPatterns } from './okf';
import { desiredRelatedLinks } from './bundle';

let pass = 0, fail = 0;
const ok = (name: string, cond: boolean, detail = '') => {
  if (cond) { pass++; console.log(`  PASS  ${name}`); }
  else { fail++; console.log(`  FAIL  ${name} ${detail}`); }
};

const ROOT = '/home/user/agentic-data-cloud-demo/okf-knowledge-catalog-agent-demo';
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

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
