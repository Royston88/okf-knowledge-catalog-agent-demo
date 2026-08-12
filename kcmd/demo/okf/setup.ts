// Create the EntryGroup + custom `okf` AspectType, and write catalog.yaml.
//
// PORTED from knowledge-catalog @ 374e0bc, toolbox/mdcode/demo/okf/setup.ts.
// Divergences:
//   * identity from ./config, not ApiContext (see the note there)
//   * plain `yaml` + fs instead of bun's YAML/Bun.file, so this runs under node
//   * every gcloud call passes --project explicitly (CLAUDE.md rule 3)
//   * idempotent: describes before creating, and reports which path it took

import * as cp from 'child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as yaml from 'yaml';
import { project, location, entryGroup, okfKey } from './config';

const here = import.meta.dirname ?? __dirname;

function gcloud(args: string, capture = false): string | null {
  const cmd = `gcloud dataplex ${args} --project=${project} --location=${location}`;
  try {
    return cp.execSync(cmd, {
      encoding: 'utf8',
      stdio: capture ? ['ignore', 'pipe', 'pipe'] : 'inherit',
    });
  } catch {
    return null;
  }
}

// --- EntryGroup -------------------------------------------------------------
if (gcloud(`entry-groups describe ${entryGroup} --format=value(name)`, true)) {
  console.log(`entry group ${entryGroup} already exists`);
} else {
  gcloud(`entry-groups create ${entryGroup}`);
  console.log(`created entry group ${entryGroup}`);
}

// --- custom aspect type -----------------------------------------------------
const aspectFile = path.join(here, 'okf-aspect.json');
if (gcloud('aspect-types describe okf --format=value(name)', true)) {
  gcloud(`aspect-types update okf --metadata-template-file-name=${aspectFile}`);
  console.log('updated custom aspect type okf');
} else {
  gcloud(`aspect-types create okf --metadata-template-file-name=${aspectFile}`);
  console.log('created custom aspect type okf');
}

// --- manifest ---------------------------------------------------------------
const manifest = {
  scope: `kb.${project}.${location}.${entryGroup}`,
  snapshot: {
    entries: ['dataplex-types.global.generic'],
    aspects: ['dataplex-types.global.generic', 'dataplex-types.global.overview', okfKey],
  },
  publishing: {
    entries: ['dataplex-types.global.generic'],
    aspects: ['dataplex-types.global.generic', 'dataplex-types.global.overview', okfKey],
  },
};
fs.writeFileSync(path.join(process.cwd(), 'catalog.yaml'), yaml.stringify(manifest));
console.log(`wrote catalog.yaml (scope ${manifest.scope}, okf aspect ${okfKey})`);
