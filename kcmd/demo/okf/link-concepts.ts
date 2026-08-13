// Project the bundle's table <-> concept references as Dataplex `related`
// EntryLinks, declaratively.
//
// WHY THIS EXISTS. Track A puts concepts ON the ingested @bigquery entries;
// Track B puts joins and metrics in a separate EntryGroup. Nothing connected
// the two, and that gap has a measured cost: on Phase 8's q4 the agent fetched
// the `accounts` table concept on all three reps while the answer sat in
// `metrics/accounts__avg_txns_per_account`, one lookup away, in a document it
// never thought to ask for. The bundle's own `[accounts](../../tables/…)` links
// are relative FILE paths — alive for a bundle reader, dead in the catalog.
//
// WHY `related` AND NOT SOMETHING ELSE, all measured:
//   `related`      any target, UNDIRECTED (both refs UNSPECIFIED; SOURCE/TARGET
//                  is rejected). Traversable via `lookupEntryLinks`.  <- chosen
//   `definition`   readable, and rendered inline by `lookup_context` — but the
//                  target MUST be a glossary term; a generic entry is refused.
//   `schema-join`  table<->table only, scan-owned, and v7 measured it is not
//                  consumed as a join hint.
//
// Note the reach limit: the prebuilt dataplex MCP toolbox has no link tool, so
// these are invisible to it. A custom ADK agent reads them with a small
// `lookupEntryLinks` tool. That is the intended consumer.
//
// DECLARATIVE. Links are reconciled, not appended: what the bundle says is what
// ends up in the catalog. Stale links from a renamed or deleted concept are
// removed. Without that, a concept that stops referencing a table would keep
// its link forever — the same trap that made ownership need an explicit release.

import { createHash } from 'node:crypto';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { splitFrontmatter } from './okf';
import { project, location, entryGroup, kcmdMain } from './config';

const RELATED_TYPE = 'projects/655216118709/locations/global/entryLinkTypes/related';
const BQ_DATASET = process.env.OKF_BQ_DATASET;
if (!BQ_DATASET) throw new Error('OKF_BQ_DATASET is not set');

export async function reconcileRelatedLinks(): Promise<void> {
const root = process.cwd();
const bundleDir = path.resolve(root, process.env.OKF_BUNDLE ?? '../okf-bundle');

const token = process.env.KCMD_ACCESS_TOKEN;
if (!token) {
  throw new Error(
    'KCMD_ACCESS_TOKEN is not set. The kcmd CLI otherwise mints a token from ' +
    'the globally active gcloud config, which is not necessarily the identity ' +
    'you intend.\n    export KCMD_ACCESS_TOKEN=$(gcloud auth print-access-token)');
}
const kcmd = await import(path.resolve(import.meta.dirname ?? __dirname,
  '../../build/ts/tool/libts/index.js'));
const client = new kcmd.dataplex.CatalogClient(
  new kcmd.gcp.ApiContext(project, location, token));

const tableEntry = (t: string) =>
  `projects/${project}/locations/${location}/entryGroups/@bigquery/entries/` +
  `bigquery.googleapis.com/projects/${project}/datasets/${BQ_DATASET}/tables/${t}`;
const conceptEntry = (rel: string) =>
  `projects/${project}/locations/${location}/entryGroups/${entryGroup}/entries/${rel}`;

// Link ids must be deterministic (so reconciliation recognises its own) and
// SHORT: the full `okf-related-<table>-<concept path>` form reached 87 chars and
// the API rejects it with a bare HTTP 400 and no message. Keep the table name
// for legibility and hash the concept path.
const slug = (s: string) => s.replace(/[/_]/g, '-').replace(/[^a-z0-9-]/gi, '').toLowerCase();
const linkId = (table: string, rel: string) => {
  const h = createHash('sha1').update(`${table}|${rel}`).digest('hex').slice(0, 10);
  return `okf-rel-${slug(table).slice(0, 28)}-${h}`;
};

function walk(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).flatMap((n) => {
    const full = path.join(dir, n);
    return fs.statSync(full).isDirectory() ? walk(full)
         : n.endsWith('.md') && n !== 'index.md' ? [full] : [];
  });
}

// Which tables does each reference concept talk about? Take it from the body's
// own markdown links (`[accounts](../../tables/accounts.md)`) rather than from
// `tags` — tags carry non-table words too ("join", "one-to-many"), and the
// links are the concept's actual, explicit references.
const wanted = new Map<string, Set<string>>();   // table -> set(concept rel path)
for (const file of walk(path.join(bundleDir, 'references'))) {
  const rel = path.relative(bundleDir, file).replace(/\\/g, '/').replace(/\.md$/, '');
  const { meta, body } = splitFrontmatter(fs.readFileSync(file, 'utf8'));
  if (!meta) continue;
  for (const m of body.matchAll(/\]\((?:\.\.\/)*tables\/([a-z0-9_]+)\.md\)/gi)) {
    if (!wanted.has(m[1])) wanted.set(m[1], new Set());
    wanted.get(m[1])!.add(rel);
  }
}

const tables = [...wanted.keys()].sort();
console.log(`bundle declares ${[...wanted.values()].reduce((n, s) => n + s.size, 0)} ` +
            `table->concept reference(s) across ${tables.length} table(s)`);

let created = 0, removed = 0, kept = 0;
for (const table of tables) {
  const entry = tableEntry(table);
  const want = new Map([...wanted.get(table)!].map((rel) => [linkId(table, rel), rel]));

  const res = await client.lookupEntryLinks(project, location, entry, [RELATED_TYPE]);
  if (res.status !== 200) {
    throw new Error(`lookupEntryLinks failed for ${table}: HTTP ${res.status}`);
  }
  // Keep the owning entry group per link: a link lives in ONE group, and ours
  // are created under `entryGroup`, but lookupEntryLinks returns links from
  // either end so a foreign group can appear here.
  const existing = new Map<string, string>();
  for (const l of res.result?.entryLinks ?? []) {
    const parts = String(l.name).split('/');
    const id = parts.pop()!;
    parts.pop();                       // 'entryLinks'
    const grp = parts.pop()!;          // owning entry group
    if (id.startsWith('okf-rel-')) existing.set(id, grp);
  }

  for (const [id, rel] of want) {
    if (existing.has(id)) { kept++; continue; }
    const link = {
      entryLinkType: RELATED_TYPE,
      // `related` is UNDIRECTED: both references must be UNSPECIFIED. Sending
      // SOURCE/TARGET is rejected outright.
      entryReferences: [{ name: entry }, { name: conceptEntry(rel) }],
    };
    const c = await client.createEntryLink(project, location, entryGroup, id, link);
    if (c.status !== 200) throw new Error(`create ${id} (len ${id.length}) failed: HTTP ${c.status} ${JSON.stringify((c as any).error ?? c.result ?? '').slice(0,300)}`);
    created++;
  }
  for (const [id, grp] of existing) {
    if (want.has(id)) continue;
    const d = await client.deleteEntryLink(project, location, grp, id);
    if (d.status !== 200) throw new Error(`delete ${id} failed: HTTP ${d.status}`);
    removed++;
  }
}
console.log(`related links: ${created} created, ${kept} already correct, ${removed} stale removed`);
}

// Run standalone: `bun link-concepts.ts`. push-track-a.ts also calls the export
// directly, so linking cannot be forgotten after a push.
if (import.meta.main) {
  await reconcileRelatedLinks();
}
