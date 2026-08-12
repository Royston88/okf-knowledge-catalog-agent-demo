// Pull from Dataplex -> clean OKF, restoring the OKF signal layer.
//
// kcmd pulls into a throwaway .staging/ tree in the "pushable" form (signal
// carried in the custom `okf` aspect via the catalogEntry passthrough); we then
// translate each file back to clean OKF and write it to catalog/. Inverse of push.ts.
//
// PORTED from knowledge-catalog @ 374e0bc, toolbox/mdcode/demo/okf/pull.ts.
// Divergence: identity + binary come from ./config (see the note there).

import * as cp from 'child_process';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fromStaging } from './okf';
import { okfKey, kcmdMain } from './config';

const root = process.cwd();
const catalogDir = path.join(root, 'catalog');
const stagingDir = path.join(root, '.staging');
const stagingCatalog = path.join(stagingDir, 'catalog');

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
fs.mkdirSync(stagingCatalog, { recursive: true });
fs.copyFileSync(path.join(root, 'catalog.yaml'), path.join(stagingDir, 'catalog.yaml'));

cp.execFileSync('node', [kcmdMain, 'pull', ...process.argv.slice(2)],
                { cwd: stagingDir, stdio: 'inherit' });

let n = 0;
for (const file of listMd(stagingCatalog)) {
  const rel = path.relative(stagingCatalog, file);
  const dest = path.join(catalogDir, rel);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.writeFileSync(dest, fromStaging(fs.readFileSync(file, 'utf8'), okfKey));
  n++;
}
console.log(`restored ${n} concept file(s) -> ${catalogDir}`);

if (!process.env.OKF_KEEP_STAGING) {
  fs.rmSync(stagingDir, { recursive: true, force: true });
}
