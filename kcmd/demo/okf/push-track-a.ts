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
// SCOPE (deliberate). We publish the `okf` aspect and NOTHING else. The body is
// not written into the entries' `overview`, so Dataplex's own generated
// documentation is left exactly as the Phase 2 scan produced it. That keeps an
// untouched control for Phase 7 / Measurement G, which has to distinguish "the
// re-scan overwrote curated content" from "the content was never there".
// `catalog.yaml`'s `publishing.aspects` is what enforces this.
//
// Differences from Track B that the mapping has to respect:
//   - local names are `bigquery/<project>/<dataset>/<table>` (BigQueryDatasetSource.localName)
//   - the entry type is fixed by ingestion and must be echoed back, not
//     replaced with `generic`
//   - `ingestedEntries` is true, so no synthetic index entries may be created

import * as cp from 'child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { toStaging } from './okf';
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

/** The live entry type for an ingested entry, as a `dataplex-types.<loc>.<id>` ref. */
async function liveEntryType(client: any, entryId: string): Promise<string> {
  const res = await client.getEntry(project, location, '@bigquery', entryId);
  if (!res.result) {
    throw new Error(`Cannot read entry type for ${entryId} (HTTP ${res.status}). ` +
      `Track A only writes to entries Dataplex has already ingested.`);
  }
  const parts = String(res.result.entryType).split('/');
  const loc = parts[3], id = parts[5];
  return `${BUILTIN_TYPE_PROJECT}.${loc}.${id}`;
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

let n = 0;
for (const sub of ['tables', 'datasets']) {
  const dir = path.join(bundleDir, sub);
  if (!fs.existsSync(dir)) continue;
  for (const file of fs.readdirSync(dir)) {
    if (!file.endsWith('.md')) continue;
    const rel = `${sub}/${file}`;
    const mapped = localNameFor(rel);
    if (!mapped) continue;
    const entryType = await liveEntryType(catalogClient, mapped.entryId);
    if (!allowed.includes(entryType)) {
      throw new Error(
        `Entry ${mapped.entryId} has type ${entryType}, which is NOT in ` +
        `catalog.yaml publishing.entries [${allowed.join(', ')}]. kcmd would ` +
        `drop it silently and still report success — add the type or exclude ` +
        `the concept.`);
    }
    const dest = path.join(stagingCatalog, `${mapped.name}.md`);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(
      dest,
      toStaging(fs.readFileSync(path.join(bundleDir, rel), 'utf8'), okfKey, mapped.name, entryType),
    );
    console.log(`  ${rel} -> ${mapped.name}  [${entryType}]`);
    n++;
  }
}
console.log(`staged ${n} asset-backed concept(s) -> ${stagingDir}`);

cp.execFileSync('node', [kcmdMain, 'push', ...process.argv.slice(2)],
                { cwd: stagingDir, stdio: 'inherit' });

if (!process.env.OKF_KEEP_STAGING) {
  fs.rmSync(stagingDir, { recursive: true, force: true });
}
