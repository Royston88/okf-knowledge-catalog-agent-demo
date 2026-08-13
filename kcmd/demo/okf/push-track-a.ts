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
import { okfKey, kcmdMain, project } from './config';

const BQ_DATASET = process.env.OKF_BQ_DATASET;
if (!BQ_DATASET) {
  throw new Error('OKF_BQ_DATASET is not set (e.g. cymbal_bank_v6z_scaffold_demo_copy)');
}

const root = process.cwd();
const bundleDir = path.resolve(root, process.env.OKF_BUNDLE ?? '../okf-bundle');
const stagingDir = path.join(root, '.staging');
const stagingCatalog = path.join(stagingDir, 'catalog');

const TABLE_TYPE = 'dataplex-types.global.bigquery-table';
const DATASET_TYPE = 'dataplex-types.global.bigquery-dataset';

fs.rmSync(stagingDir, { recursive: true, force: true });
fs.mkdirSync(stagingCatalog, { recursive: true });
fs.copyFileSync(path.join(root, 'catalog.yaml'), path.join(stagingDir, 'catalog.yaml'));

// `tables/<t>.md` -> bigquery/<project>/<dataset>/<t>
// `datasets/<d>.md` -> bigquery/<project>/<d>
function localNameFor(rel: string): { name: string; type: string } | undefined {
  const id = path.basename(rel, '.md');
  if (id === 'index') return undefined;
  const dir = path.dirname(rel);
  if (dir === 'tables') {
    return { name: `bigquery/${project}/${BQ_DATASET}/${id}`, type: TABLE_TYPE };
  }
  if (dir === 'datasets') {
    return { name: `bigquery/${project}/${id}`, type: DATASET_TYPE };
  }
  return undefined;
}

let n = 0;
for (const sub of ['tables', 'datasets']) {
  const dir = path.join(bundleDir, sub);
  if (!fs.existsSync(dir)) continue;
  for (const file of fs.readdirSync(dir)) {
    if (!file.endsWith('.md')) continue;
    const rel = `${sub}/${file}`;
    const mapped = localNameFor(rel);
    if (!mapped) continue;
    const dest = path.join(stagingCatalog, `${mapped.name}.md`);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(
      dest,
      toStaging(fs.readFileSync(path.join(bundleDir, rel), 'utf8'), okfKey, mapped.name, mapped.type),
    );
    console.log(`  ${rel} -> ${mapped.name}`);
    n++;
  }
}
console.log(`staged ${n} asset-backed concept(s) -> ${stagingDir}`);

cp.execFileSync('node', [kcmdMain, 'push', ...process.argv.slice(2)],
                { cwd: stagingDir, stdio: 'inherit' });

if (!process.env.OKF_KEEP_STAGING) {
  fs.rmSync(stagingDir, { recursive: true, force: true });
}
