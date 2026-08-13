// Push clean OKF -> Dataplex, preserving the OKF signal layer.
//
// The on-disk catalog/ is clean OKF. kcmd's generic Documents Layout only maps
// title/description/tags + body, so we translate each file into the "pushable"
// form (signal moved into a custom `okf` aspect via the catalogEntry passthrough)
// in a throwaway .staging/ tree, then delegate to the real kcmd CLI.
//
// PORTED from knowledge-catalog @ 374e0bc, toolbox/mdcode/demo/okf/push.ts.
// Divergence: identity + binary come from ./config (see the note there).

import * as cp from 'child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { toStaging, splitFrontmatter } from './okf';
import { okfKey, kcmdMain } from './config';

const root = process.cwd();
const catalogDir = path.join(root, 'catalog');
const stagingDir = path.join(root, '.staging');

function listMd(dir: string): string[] {
  const out: string[] = [];
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    if (fs.statSync(full).isDirectory()) {
      out.push(...listMd(full));
    } else if (name.endsWith('.md')) {
      out.push(full);
    }
  }
  return out;
}

fs.rmSync(stagingDir, { recursive: true, force: true });
fs.mkdirSync(path.join(stagingDir, 'catalog'), { recursive: true });
fs.copyFileSync(path.join(root, 'catalog.yaml'), path.join(stagingDir, 'catalog.yaml'));

// A concept with a top-level `resource:` names a BigQuery asset that Dataplex
// has ALREADY ingested as an `@bigquery` entry. Publishing it here too creates a
// second catalog object for the same table — which is what a Knowledge Catalog
// search then shows the user: "Accounts" (ours) next to `accounts` (native).
//
// The 39 joins and metrics have no `resource:` and no native home, so they are
// the concepts that genuinely need entries of their own. The 14 asset-backed
// concepts belong ON their native entry, and Track A (`push-track-a.ts`) puts
// them there — the `okf` signal aspect plus the body as `overview`, a slot the
// ingested entries leave empty.
function isAssetBacked(content: string): boolean {
  const { meta } = splitFrontmatter(content);
  return !!(meta && meta.resource);
}

let n = 0, skipped = 0;
for (const file of listMd(catalogDir)) {
  const rel = path.relative(catalogDir, file);
  if (isAssetBacked(fs.readFileSync(file, 'utf8'))) {
    skipped++;
    continue;
  }
  const dest = path.join(stagingDir, 'catalog', rel);
  // The entry id is the bundle-relative path minus `.md`, POSIX-separated —
  // the same derivation the fork's OkfLayout uses. toStaging stamps it onto
  // `catalogEntry.name`, without which the documents layout indexes nothing.
  const entryName = rel.replace(/\\/g, '/').replace(/\.md$/, '');
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(dest, toStaging(fs.readFileSync(file, 'utf8'), okfKey, entryName));
  n++;
}
console.log(`staged ${n} concept file(s) -> ${stagingDir} ` +
  `(skipped ${skipped} asset-backed concept(s); Track A owns those)`);

const args = ['push', ...process.argv.slice(2)];
cp.execFileSync('node', [kcmdMain, ...args], { cwd: stagingDir, stdio: 'inherit' });

// RELINK AFTER EVERY PUSH — BOTH TRACKS NEED THIS.
// kcmd reconciles EntryLinks against the local bundle and deletes what it does
// not find there. A `related` link touches BOTH a table entry and a concept
// entry, so Track B's push (which owns the concept entries) deletes them just
// as Track A's does — measured: a Track B push alone took 53 links down to 14.
// Set OKF_BQ_DATASET to enable; skipped with a warning when it is absent, since
// Track B is otherwise usable without knowing the BigQuery dataset.
if (process.env.OKF_BQ_DATASET) {
  const { reconcileRelatedLinks } = await import('./link-concepts');
  await reconcileRelatedLinks();
} else {
  console.warn('OKF_BQ_DATASET unset — skipping `related` link reconciliation. ' +
               'Any table<->concept links this push deleted stay deleted.');
}

// Keep .staging on request so a failed push can be inspected.
if (!process.env.OKF_KEEP_STAGING) {
  fs.rmSync(stagingDir, { recursive: true, force: true });
}
