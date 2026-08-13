// Track A: project the OKF signal layer onto the entries Dataplex ALREADY has.
//
// Track B (push.ts) creates standalone concept entries in our own EntryGroup.
// Track A instead attaches the `okf` aspect to the *ingested* `@bigquery`
// entries for the same tables — which is the projection that matters for the
// agent story, because an analyst's tooling looks at the BigQuery entries, not
// at a side catalog of abstract concepts.
//
// Only the 14 asset-backed concepts participate: `tables/*.md` and
// `datasets/*.md`. Joins and metrics have no ingested entry to attach to; they
// exist only in Track B.
//
// SCOPE. The bundle owns four aspects on each ingested entry:
//   okf           the signal layer (custom type, no scan touches it)
//   overview      the concept body    — reaches an agent only at view=ALL
//   descriptions  table + column docs — what the BigQuery/Dataplex UI renders
//   queries       the concept's query patterns
//
// The last two are SCAN-OWNED, so they are written with `userManaged: true`.
// Measurement G showed content written to them without that flag is destroyed
// by the next DATA_DOCUMENTATION run, silently. Verified after this change: a
// successful re-scan left all of it byte-identical.
//
// Note that NONE of overview/descriptions/queries is returned at an MCP
// client's default `view=FULL` — all three are non-required aspects, and FULL
// returns non-required aspects as keys only. Owning them is about the UI and
// about ownership, not about agent reach; reach needs `view=ALL`.
//
// `catalog.yaml` lists all four in BOTH `snapshot.aspects` and
// `publishing.aspects` — kcmd rejects a publishing aspect that is not also
// snapshotted ("Publishing aspect type ... is not listed in snapshot aspects"),
// loudly, which is a welcome change from its usual silence.
//
// Differences from Track B that the mapping has to respect:
//   - local names are `bigquery/<project>/<dataset>/<table>` (BigQueryDatasetSource.localName)
//   - the entry type is fixed by ingestion and must be echoed back, not
//     replaced with `generic`
//   - `ingestedEntries` is true, so no synthetic index entries may be created

import * as cp from 'child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { toStaging, splitFrontmatter } from './okf';
import { okfKey, kcmdMain, project, location } from './config';

const BQ_DATASET = process.env.OKF_BQ_DATASET;
if (!BQ_DATASET) {
  throw new Error('OKF_BQ_DATASET is not set (e.g. cymbal_bank_v6z_scaffold_demo_copy)');
}

const root = process.cwd();
const bundleDir = path.resolve(root, process.env.OKF_BUNDLE ?? '../okf-bundle');
const stagingDir = path.join(root, '.staging');
const stagingCatalog = path.join(stagingDir, 'catalog');

// Entry types are READ FROM THE CATALOG, not assumed.
//
// These entries are ingested, so Dataplex already assigned each one a native
// type. An earlier version of this script hardcoded `tables/* ->
// bigquery-table`, which was correct only because this dataset happens to hold
// 13 BASE TABLEs: BigQuery entries can equally be `bigquery-view`,
// `bigquery-model` or `bigquery-routine`, and a view would have been stamped
// `bigquery-table`.
//
// The type is not cosmetic. `snapshot.ts:446` uses it as a PUBLISHING FILTER —
// an entry whose `type` is absent from `catalog.yaml`'s `publishing.entries` is
// silently dropped and `push` still reports success. That is the Phase 5
// blocker's exact failure mode, so a wrong type here loses entries quietly.
//
// Normalisation matters too: the service returns the built-in types qualified
// by project NUMBER (`655216118709.global.bigquery-table`) while the allowlist
// is written with the project ID alias (`dataplex-types.global.…`). Comparing
// the raw form against the allowlist would drop everything.
const BUILTIN_TYPE_PROJECT = 'dataplex-types';

fs.rmSync(stagingDir, { recursive: true, force: true });
fs.mkdirSync(stagingCatalog, { recursive: true });
fs.copyFileSync(path.join(root, 'catalog.yaml'), path.join(stagingDir, 'catalog.yaml'));

// `tables/<t>.md` -> bigquery/<project>/<dataset>/<t>
// `datasets/<d>.md` -> bigquery/<project>/<d>
function localNameFor(rel: string): { name: string; entryId: string } | undefined {
  const id = path.basename(rel, '.md');
  if (id === 'index') return undefined;
  const dir = path.dirname(rel);
  const prefix = `bigquery.googleapis.com/projects/${project}/datasets/${BQ_DATASET}`;
  if (dir === 'tables') {
    return { name: `bigquery/${project}/${BQ_DATASET}/${id}`, entryId: `${prefix}/tables/${id}` };
  }
  if (dir === 'datasets') {
    return { name: `bigquery/${project}/${id}`, entryId: prefix };
  }
  return undefined;
}

/** The allowlist the derived type has to satisfy, read from catalog.yaml. */
function publishingEntryTypes(): string[] {
  const text = fs.readFileSync(path.join(root, 'catalog.yaml'), 'utf8');
  const out: string[] = [];
  let inPublishing = false, inEntries = false;
  for (const raw of text.split(/\r?\n/)) {
    if (/^publishing:/.test(raw)) { inPublishing = true; continue; }
    if (/^\S/.test(raw)) { inPublishing = false; inEntries = false; continue; }
    if (!inPublishing) continue;
    if (/^\s{2}entries:/.test(raw)) { inEntries = true; continue; }
    if (/^\s{2}\S/.test(raw)) { inEntries = false; continue; }
    const m = inEntries && raw.match(/^\s*-\s*(\S+)/);
    if (m) out.push(m[1]);
  }
  return out;
}

// `getEntry`'s aspect filter takes FULL RESOURCE NAMES, not the dotted alias.
// Passing the alias returns HTTP 400 — and, because the aspect map on a failed
// response is simply empty, a naive caller reads that as "nothing is held" and
// releases nothing while reporting success. Measured; hence the status check in
// releaseIfHeld.
const DESCRIPTIONS_TYPE = 'projects/dataplex-types/locations/global/aspectTypes/descriptions';
const QUERIES_TYPE = 'projects/dataplex-types/locations/global/aspectTypes/queries';
const SCHEMA_TYPE = 'projects/dataplex-types/locations/global/aspectTypes/schema';

/**
 * Hand a contested aspect back to the scan.
 *
 * Ownership is DECLARATIVE: a concept with `verified` claims `descriptions` and
 * `queries`; one without does not. But dropping an aspect from the push payload
 * is a NO-OP, not a release — measured: kcmd only writes the aspects present in
 * the staged entry and never deletes the ones it omits. So a concept that loses
 * its `verified` flag would keep a stale `userManaged: true` claim forever.
 *
 * This flips the flag back to false in place, leaving the content alone. The
 * next DATA_DOCUMENTATION run then regenerates it, which is the point: the scan
 * resumes managing what no human has vouched for.
 */
async function releaseIfHeld(client: any, entryId: string, label: string): Promise<boolean> {
  const res = await client.getEntry(project, location, '@bigquery', entryId,
                                    [DESCRIPTIONS_TYPE, QUERIES_TYPE]);
  if (res.status !== 200 || !res.result) {
    throw new Error(`Cannot read contested aspects for ${label}: HTTP ${res.status}`);
  }
  const aspects = res.result.aspects ?? {};
  const held = Object.entries(aspects).filter(
    ([k, v]: [string, any]) => /\.(descriptions|queries)$/.test(k) && v?.data?.userManaged === true,
  );
  if (!held.length) return false;
  const entry: any = { name: res.result.name, aspects: {} };
  for (const [k, v] of held as Array<[string, any]>) {
    entry.aspects[k] = { aspectType: v.aspectType, data: { ...v.data, userManaged: false } };
  }
  const upd = await client.updateEntry(entry, ['aspects'], Object.keys(entry.aspects));
  if (upd.status !== 200) {
    throw new Error(`Failed to release ${label}: HTTP ${upd.status}`);
  }
  console.log(`  ${label}: released ${Object.keys(entry.aspects).length} aspect(s) back to the scan`);
  return true;
}

/**
 * The live entry type (as a `dataplex-types.<loc>.<id>` ref) and the entry's
 * real column list, read from its own `schema` aspect.
 *
 * The columns feed the completeness gate: claiming `descriptions` freezes it,
 * so an owned concept that omits a column would blank it permanently. Taking
 * the list from the catalog rather than the bundle means the gate checks
 * against ground truth.
 */
async function liveEntryInfo(
  client: any,
  entryId: string,
): Promise<{ type: string; columns: string[] }> {
  const res = await client.getEntry(project, location, '@bigquery', entryId, [SCHEMA_TYPE]);
  if (res.status !== 200 || !res.result) {
    throw new Error(`Cannot read entry ${entryId} (HTTP ${res.status}). ` +
      `Track A only writes to entries Dataplex has already ingested.`);
  }
  const parts = String(res.result.entryType).split('/');
  const type = `${BUILTIN_TYPE_PROJECT}.${parts[3]}.${parts[5]}`;
  const schema: any = Object.entries(res.result.aspects ?? {})
    .find(([k]) => k.endsWith('.schema'))?.[1];
  const columns: string[] = (schema?.data?.fields ?? []).map((f: any) => f.name);
  return { type, columns };
}

const allowed = publishingEntryTypes();
const kcmd = await import(path.resolve(import.meta.dirname ?? __dirname,
  '../../build/ts/tool/libts/index.js'));
const token = process.env.KCMD_ACCESS_TOKEN;
if (!token) {
  throw new Error(
    'KCMD_ACCESS_TOKEN is not set.\n' +
    '  The kcmd CLI mints its own token from the GLOBALLY ACTIVE gcloud config, ' +
    'which is not necessarily the identity you think you are using. Set it ' +
    'explicitly so the push identity is deliberate:\n' +
    '    export KCMD_ACCESS_TOKEN=$(gcloud auth print-access-token)');
}
const catalogClient = new kcmd.dataplex.CatalogClient(
  new kcmd.gcp.ApiContext(project, location, token));

let n = 0, released = 0;
const toRelease: Array<{ entryId: string; label: string }> = [];
for (const sub of ['tables', 'datasets']) {
  const dir = path.join(bundleDir, sub);
  if (!fs.existsSync(dir)) continue;
  for (const file of fs.readdirSync(dir)) {
    if (!file.endsWith('.md')) continue;
    const rel = `${sub}/${file}`;
    const mapped = localNameFor(rel);
    if (!mapped) continue;
    const { type: entryType, columns } = await liveEntryInfo(catalogClient, mapped.entryId);
    if (!allowed.includes(entryType)) {
      throw new Error(
        `Entry ${mapped.entryId} has type ${entryType}, which is NOT in ` +
        `catalog.yaml publishing.entries [${allowed.join(', ')}]. kcmd would ` +
        `drop it silently and still report success — add the type or exclude ` +
        `the concept.`);
    }
    const src = fs.readFileSync(path.join(bundleDir, rel), 'utf8');
    if (!splitFrontmatter(src).meta?.verified) {
      toRelease.push({ entryId: mapped.entryId, label: rel });
    }
    const dest = path.join(stagingCatalog, `${mapped.name}.md`);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(
      dest,
      toStaging(src, okfKey, mapped.name, entryType, /* withAssetAspects */ true, columns, rel),
    );
    console.log(`  ${rel} -> ${mapped.name}  [${entryType}]`);
    n++;
  }
}
console.log(`staged ${n} asset-backed concept(s) -> ${stagingDir}`);

// Release BEFORE the push, so a concept that just lost its `verified` flag is
// handed back in the same run that stops claiming it.
for (const r of toRelease) {
  if (await releaseIfHeld(catalogClient, r.entryId, r.label)) released++;
}
console.log(`unverified concepts: ${toRelease.length} (released ${released} stale claim(s))`);

cp.execFileSync('node', [kcmdMain, 'push', ...process.argv.slice(2)],
                { cwd: stagingDir, stdio: 'inherit' });

if (!process.env.OKF_KEEP_STAGING) {
  fs.rmSync(stagingDir, { recursive: true, force: true });
}
