// Pure, offline derivations over the OKF bundle on disk.
//
// Separate from `link-concepts.ts` deliberately: that module imports `./config`,
// which THROWS at module scope when OKF_PROJECT / OKF_LOCATION /
// OKF_ENTRY_GROUP are unset, and it throws again on a missing OKF_BQ_DATASET.
// Correct for a script that talks to Dataplex, fatal for `ownership.test.ts`,
// which is the offline suite and must run with no credentials and no
// environment. Anything here reads files and returns data — no client, no
// config, no network.

import * as fs from 'node:fs';
import * as path from 'node:path';
import { splitFrontmatter } from './okf';

/** Every concept file under `dir`, recursively. `index.md` is a listing, not a concept. */
export function walkConcepts(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).flatMap((n) => {
    const full = path.join(dir, n);
    return fs.statSync(full).isDirectory() ? walkConcepts(full)
         : n.endsWith('.md') && n !== 'index.md' ? [full] : [];
  });
}

// A markdown link to a table concept, in every form OKF §6.1 permits:
//   /tables/accounts.md        absolute (bundle-relative) — the RECOMMENDED form
//   ../../tables/accounts.md   relative
//   tables/accounts.md         bare
//
// ACCEPTING BOTH FORMS IS LOAD-BEARING. The previous pattern was
// `\]\((?:\.\./)*tables/([a-z0-9_]+)\.md\)` — relative only. The bundle has
// since migrated to the absolute form (190 links, 0 relative), and under the
// old pattern that migration would have taken this map, and with it all 58
// `related` EntryLinks, silently to ZERO while every other check stayed green.
const TABLE_REF = /\]\((?:\.{1,2}\/)*\/?tables\/([a-z0-9_]+)\.md\)/gi;

/**
 * table name -> the reference concepts that reference it.
 *
 * ONE DERIVATION, THREE RENDERINGS — this is the derivation:
 *
 *   concept -> table   the authored body links this reads       (the source)
 *   table -> concepts  the `# Related concepts` section rendered by
 *                      `okf-review/postauthor.py`                (generated)
 *   undirected         the `related` EntryLinks that
 *                      `link-concepts.ts` reconciles             (generated)
 *
 * Taken from each concept's own body links rather than from `tags`: tags carry
 * non-table words too ("join", "one-to-many"), while the links are the
 * concept's actual, explicit references.
 *
 * OKF §6.1 treats links as DIRECTED, so concept->table and table->concept are
 * two distinct assertions and the back-link is new information rather than
 * duplication. Dataplex `related` is undirected and collapses them into one —
 * the bundle carries strictly more structure than the catalog can express.
 */
export function desiredRelatedLinks(bundleDir: string): Map<string, Set<string>> {
  const wanted = new Map<string, Set<string>>();
  for (const file of walkConcepts(path.join(bundleDir, 'references'))) {
    const rel = path.relative(bundleDir, file).replace(/\\/g, '/').replace(/\.md$/, '');
    const { meta, body } = splitFrontmatter(fs.readFileSync(file, 'utf8'));
    if (!meta) continue;
    for (const m of body.matchAll(TABLE_REF)) {
      if (!wanted.has(m[1])) wanted.set(m[1], new Set());
      wanted.get(m[1])!.add(rel);
    }
  }
  return wanted;
}
