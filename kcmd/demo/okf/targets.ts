// Where each bundle concept lands in the catalog — ONE derivation, used by the
// two push scripts and by the differ.
//
// This existed three times before: `push.ts` derived Track B ids inline,
// `push-track-a.ts` derived Track A ids inline, and the differ would have
// needed both. Three copies of "which entry is this concept" is three chances
// for the differ to compare a concept against the wrong entry and report a
// clean bill of health, which is the worst failure this tool can have.

import * as fs from 'node:fs';
import * as path from 'node:path';
import { splitFrontmatter } from './okf';
import { walkConcepts } from './bundle';

export type Track = 'A' | 'B';

export interface Target {
  track: Track;
  /** bundle-relative path without `.md` — `tables/accounts`, `references/joins/x` */
  rel: string;
  /** absolute path to the source concept */
  file: string;
  /** kcmd local name, i.e. the staged file path without `.md` */
  entryName: string;
  /** the Dataplex entry id within its entry group */
  entryId: string;
  entryGroup: string;
  /** true for Track A: `descriptions` + `queries` are projected too */
  withAssetAspects: boolean;
}

export interface Resolver {
  project: string;
  location: string;
  dataset: string;
  entryGroup: string;
}

/**
 * Every concept in the bundle, split across the two tracks by the one property
 * the bundle already carries: a top-level `resource:` names an asset Dataplex
 * has ALREADY ingested, so the concept belongs ON that entry (Track A);
 * everything else needs an entry of its own (Track B). That single rule is what
 * took a catalog search from 28 hits to 14.
 */
export function resolveTargets(bundleDir: string, r: Resolver): Target[] {
  const out: Target[] = [];
  const bqPrefix =
    `bigquery.googleapis.com/projects/${r.project}/datasets/${r.dataset}`;

  for (const file of walkConcepts(bundleDir)) {
    const rel = path.relative(bundleDir, file).replace(/\\/g, '/').replace(/\.md$/, '');
    const { meta } = splitFrontmatter(fs.readFileSync(file, 'utf8'));
    // No frontmatter is not a concept. `log.md` is the live example, and
    // `OkfLayout` would happily publish it as a generic entry called `log`.
    if (!meta) continue;

    if (meta.resource) {
      const id = rel.split('/').pop()!;
      if (rel.startsWith('tables/')) {
        out.push({
          track: 'A', rel, file,
          entryName: `bigquery/${r.project}/${r.dataset}/${id}`,
          entryId: `${bqPrefix}/tables/${id}`,
          entryGroup: '@bigquery',
          withAssetAspects: true,
        });
      } else if (rel.startsWith('datasets/')) {
        out.push({
          track: 'A', rel, file,
          entryName: `bigquery/${r.project}/${id}`,
          entryId: bqPrefix,
          entryGroup: '@bigquery',
          withAssetAspects: true,
        });
      } else {
        throw new Error(
          `${rel} carries a top-level \`resource:\` but is not under tables/ or ` +
          `datasets/, so there is no rule for which ingested entry it belongs to. ` +
          `Refusing to guess — an asset-backed concept pushed to the wrong entry ` +
          `is silent and total.`);
      }
      continue;
    }

    out.push({
      track: 'B', rel, file,
      entryName: rel,
      entryId: rel,
      entryGroup: r.entryGroup,
      withAssetAspects: false,
    });
  }
  return out.sort((a, b) => a.rel.localeCompare(b.rel));
}
