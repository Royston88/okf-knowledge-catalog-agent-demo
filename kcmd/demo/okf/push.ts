// Push clean OKF -> Dataplex, preserving the OKF signal layer.
//
// The on-disk `okf-bundle/` is clean OKF and kcmd never sees it. We translate
// each concept into a kcmd-NATIVE staged tree — OKF frontmatter plus the
// `x-kcmd` stash, the form `OkfLayout` reads — in a throwaway `.staging/`, then
// delegate to the real kcmd CLI. See `okf.ts::toOkfStaging` for why the staged
// form is a build artifact rather than a second source of truth.
//
// PORTED from knowledge-catalog @ 374e0bc, toolbox/mdcode/demo/okf/push.ts.
// Divergence: identity + binary come from ./config (see the note there); the
// staged form is `x-kcmd` rather than `catalogEntry`.

import * as cp from 'child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { stagingEmitter, splitFrontmatter } from './okf';
import { planPush } from './planner';
import { okfKey, kcmdMain } from './config';

const root = process.cwd();
const bundleDir = path.resolve(root, process.env.OKF_BUNDLE ?? '../okf-bundle');
const stagingDir = path.join(root, '.staging');
const { emit, form, layout, rootDir } = stagingEmitter();

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

// WHAT MAY BE STAGED — AN ALLOWLIST, NOT A DENYLIST, and that is deliberate.
//
// `OkfLayout` special-cases exactly one filename: `index.md`. Every OTHER
// frontmatter-less `.md` is indexed by its path-derived name and `_loadLayer`
// treats it as "a default generic entry whose body is the overview" — so
// `okf-bundle/log.md` would be pushed to Dataplex as a spurious `log` entry,
// silently and with no error. A denylist would have to be extended every time a
// non-concept file is added to the bundle, and the failure mode of forgetting
// is a junk catalog entry that nobody looks for. An allowlist fails closed.
//
// Two kinds are allowed:
//   - a CONCEPT: has YAML frontmatter (§11.1 requires it)
//   - an `index.md`: OKF §8 directory listing, which OkfLayout turns into a
//     synthetic directory entry so the Dataplex hierarchy is recreated
type Staged = { rel: string; kind: 'concept' | 'index' } | { rel: string; kind: 'skip'; why: string };

function classify(rel: string, content: string): Staged {
  const base = path.basename(rel);
  if (base === 'index.md') return { rel, kind: 'index' };
  const { meta } = splitFrontmatter(content);
  if (!meta) return { rel, kind: 'skip', why: 'no frontmatter and not index.md' };
  // A concept with a top-level `resource:` names a BigQuery asset Dataplex has
  // ALREADY ingested, so it belongs ON that entry. Publishing it here too
  // creates a second catalog object for the same table — which is what a
  // Knowledge Catalog search then shows the user: "Accounts" (ours) next to
  // `accounts` (native). That de-duplication took a search from 28 hits to 14.
  // Track A (`push-track-a.ts`) owns these.
  if (meta.resource) return { rel, kind: 'skip', why: 'asset-backed; Track A owns it' };
  return { rel, kind: 'concept' };
}

// PULL -> COMPARE -> STAGE ONLY WHAT DIFFERS. Aborts before writing anything if
// an owned channel was edited by a third party since the last recorded sweep.
const plan = await planPush('B', process.argv.includes('--force'));

fs.rmSync(stagingDir, { recursive: true, force: true });
fs.mkdirSync(path.join(stagingDir, rootDir), { recursive: true });
fs.copyFileSync(path.join(root, 'catalog.yaml'), path.join(stagingDir, 'catalog.yaml'));

let n = 0, indexes = 0, unchanged = 0;
const indexFiles: Array<{ rel: string; content: string }> = [];
const skipped: Record<string, number> = {};
for (const file of listMd(bundleDir)) {
  const rel = path.relative(bundleDir, file).replace(/\\/g, '/');
  const content = fs.readFileSync(file, 'utf8');
  const c = classify(rel, content);
  if (c.kind === 'skip') {
    skipped[c.why] = (skipped[c.why] ?? 0) + 1;
    continue;
  }
  // DO NOT copy `tables/index.md` or `datasets/index.md`. `OkfLayout.init()`
  // registers EVERY index.md it finds, so those would create index entries
  // pointing at directories this tree has no concepts in.
  if (c.kind === 'index') {
    const dir = path.dirname(rel);
    const hasConcepts = listMd(path.join(bundleDir, dir === '.' ? '' : dir)).some((f) => {
      const r = path.relative(bundleDir, f).replace(/\\/g, '/');
      return classify(r, fs.readFileSync(f, 'utf8')).kind === 'concept';
    });
    if (!hasConcepts && dir !== '.') {
      skipped['index.md for a directory with no Track B concepts'] =
        (skipped['index.md for a directory with no Track B concepts'] ?? 0) + 1;
      continue;
    }
  }

  // INDEX FILES ARE DEFERRED, not written yet. `OkfLayout` turns each one into
  // a synthetic directory entry, and `sync.ts` orders parents before children
  // and validates that `parentEntry` already exists — so an index entry is
  // needed whenever a CONCEPT is staged, and is pure churn when none is. They
  // are decided below, once the concept count is known.
  if (c.kind === 'index') {
    indexFiles.push({ rel, content });
    continue;
  }
  const relNoExt = rel.replace(/\.md$/, '');
  if (plan.enabled && !plan.stage.has(relNoExt)) {
    unchanged++;
    continue;
  }
  // The entry id is the bundle-relative path minus `.md`, POSIX-separated —
  // the same derivation `OkfLayout.deriveEntryName` uses, so the stashed name
  // and the path-derived fallback agree.
  const dest = path.join(stagingDir, rootDir, rel);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(dest, emit(content, okfKey, relNoExt));
  n++;
}

// A NO-OP PUSH MUST BE A GENUINE NO-OP — that is what makes the entry-level
// `updateTime` mean "we wrote this" rather than "we ran". Staging the 7 index
// files when no concept changed would `modifyEntry` all 7 for nothing.
if (n > 0 || !plan.enabled) {
  for (const { rel, content } of indexFiles) {
    const dest = path.join(stagingDir, rootDir, rel);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(dest, content);
    indexes++;
  }
}

console.log(`staged ${n} concept file(s) + ${indexes} index.md -> ${stagingDir}/${rootDir} ` +
            `[form=${form} layout=${layout}]`);
if (unchanged) console.log(`  ${unchanged} identical to the catalog — not staged`);
if (n === 0 && plan.enabled && indexFiles.length) {
  console.log(`  ${indexFiles.length} index.md held back — nothing to parent`);
}
for (const [why, count] of Object.entries(skipped).sort()) {
  console.log(`  skipped ${count}: ${why}`);
}

if (n === 0 && indexes === 0) {
  console.log('nothing to push — skipping the kcmd invocation entirely');
} else {
  const args = ['push', ...process.argv.slice(2)];
  cp.execFileSync('node', [kcmdMain, ...args], { cwd: stagingDir, stdio: 'inherit' });
}

// RELINK AFTER EVERY PUSH — BOTH TRACKS NEED THIS.
// kcmd reconciles EntryLinks against the local bundle and deletes what it does
// not find there. A `related` link touches BOTH a table entry and a concept
// entry, so Track B's push (which owns the concept entries) deletes them just
// as Track A's does — measured: a Track B push alone took 53 links down to 14.
// Set OKF_BQ_DATASET to enable; skipped with a warning when it is absent, since
// Track B is otherwise usable without knowing the BigQuery dataset.
if (process.env.OKF_BQ_DATASET || process.env.BIGQUERY_DATASET) {
  const { reconcileRelatedLinks } = await import('./link-concepts');
  await reconcileRelatedLinks();
} else {
  console.warn('OKF_BQ_DATASET / BIGQUERY_DATASET unset — skipping `related` link reconciliation. ' +
               'Any table<->concept links this push deleted stay deleted.');
}

// Keep .staging on request so a failed push can be inspected. It is gitignored
// under `**/.staging/`, so an inspected tree cannot be committed by accident.
if (!process.env.OKF_KEEP_STAGING) {
  fs.rmSync(stagingDir, { recursive: true, force: true });
}
