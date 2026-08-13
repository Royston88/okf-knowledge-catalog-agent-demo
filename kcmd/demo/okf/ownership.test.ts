// Offline tests for the ownership rule (T5, T6, and the isOwned predicate).
// Fast and deterministic — no catalog, no scans. Run: bun kcmd/demo/okf/ownership.test.ts
import * as fs from 'node:fs';
import { splitFrontmatter, isOwned, assetAspects, OwnershipError, schemaFields } from './okf';

let pass = 0, fail = 0;
const ok = (name: string, cond: boolean, detail = '') => {
  if (cond) { pass++; console.log(`  PASS  ${name}`); }
  else { fail++; console.log(`  FAIL  ${name} ${detail}`); }
};
const throws = (name: string, fn: () => unknown, needle: string) => {
  try { fn(); fail++; console.log(`  FAIL  ${name} (expected a throw)`); }
  catch (e: any) {
    const good = e instanceof OwnershipError && String(e.message).includes(needle);
    good ? (pass++, console.log(`  PASS  ${name}`))
         : (fail++, console.log(`  FAIL  ${name} — wrong error: ${e.message?.slice(0, 90)}`));
  }
};

const ROOT = '/home/user/agentic-data-cloud-demo/okf-knowledge-catalog-agent-demo';
const read = (p: string) => splitFrontmatter(fs.readFileSync(`${ROOT}/${p}`, 'utf8'));
const V = [{ by: 'human:x', at: '2026-01-01T00:00:00+00:00' }];

console.log('T6 — status gate');
ok('verified alone owns',            isOwned({ verified: V }));
ok('draft does not own',             !isOwned({ verified: V, status: 'draft' }));
ok('deprecated does not own',        !isOwned({ verified: V, status: 'deprecated' }));
ok('stable owns',                    isOwned({ verified: V, status: 'stable' }));
ok('status case-insensitive',        !isOwned({ verified: V, status: 'DRAFT' }));
ok('no verified does not own',       !isOwned({ status: 'stable' }));
ok('empty verified does not own',    !isOwned({ verified: [] }));

console.log('T5 — completeness gate');
const { meta, body } = read('okf-bundle/tables/customers.md');
const cols = ['customer_id','name','segment','region','signup_date','referred_by','state','city'];
ok('complete concept claims both aspects',
   Object.keys(assetAspects(meta, body, cols, 'customers')).length === 2);
throws('missing column is refused', () => assetAspects(meta, body, [...cols, 'ghost'], 'customers'),
       'does not document');
const trimmed = body.replace(/^\|\s*`?\*{0,2}city.*$/m, '');
throws('undocumented real column is refused', () => assetAspects(meta, trimmed, cols, 'customers'),
       'city');
ok('unowned concept skips the gate entirely',
   Object.keys(assetAspects({ ...meta, verified: undefined }, body, [...cols, 'ghost'])).length === 0);

console.log('parser regression — a column literally called `name`');
ok('`name` is not eaten by header detection',
   schemaFields(body).some((f) => f.name === 'name'));
ok('every real column is documented in the bundle',
   cols.every((c) => schemaFields(body).some((f) => f.name === c)));

console.log('the whole bundle passes the gate it will be pushed under');
let checked = 0;
for (const f of fs.readdirSync(`${ROOT}/okf-bundle/tables`)) {
  if (!f.endsWith('.md') || f === 'index.md') continue;
  const d = read(`okf-bundle/tables/${f}`);
  if (!isOwned(d.meta)) continue;
  checked++;
  ok(`${f} claims cleanly`, Object.keys(assetAspects(d.meta, d.body, undefined, f)).length === 2);
}
ok('at least one owned table exercised', checked > 0, `(checked ${checked})`);

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
