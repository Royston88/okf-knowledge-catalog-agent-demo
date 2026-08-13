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
import { toStaging } from './okf';
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

let n = 0;
for (const file of listMd(catalogDir)) {
  const rel = path.relative(catalogDir, file);
  const dest = path.join(stagingDir, 'catalog', rel);
  // The entry id is the bundle-relative path minus `.md`, POSIX-separated —
  // the same derivation the fork's OkfLayout uses. toStaging stamps it onto
  // `catalogEntry.name`, without which the documents layout indexes nothing.
  const entryName = rel.replace(/\\/g, '/').replace(/\.md$/, '');
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(dest, toStaging(fs.readFileSync(file, 'utf8'), okfKey, entryName));
  n++;
}
console.log(`staged ${n} concept file(s) -> ${stagingDir}`);

const args = ['push', ...process.argv.slice(2)];
cp.execFileSync('node', [kcmdMain, ...args], { cwd: stagingDir, stdio: 'inherit' });

// Keep .staging on request so a failed push can be inspected.
if (!process.env.OKF_KEEP_STAGING) {
  fs.rmSync(stagingDir, { recursive: true, force: true });
}
