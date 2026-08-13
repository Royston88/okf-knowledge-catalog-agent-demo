// Offline tests for the projection rule. No catalog, no scans.
//   bun kcmd/demo/okf/ownership.test.ts
//
// The rule: the bundle always projects overview + descriptions + queries, and
// `userManaged` on descriptions/queries equals whether the concept is verified.
import * as fs from 'node:fs';
import { splitFrontmatter, assetAspects, schemaFields, queryPatterns } from './okf';

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

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
