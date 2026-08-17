// Explicit identity + binary resolution for the OKF demo scripts.
//
// PORT NOTE. Upstream's push.ts/pull.ts/setup.ts do:
//     import * as kcmd from 'kcmd';
//     const context = kcmd.gcp.ApiContext.default();
// Neither works in this fork:
//   1. `package.json` "exports" points at ./build/ts/kcmd/index.js, which this
//      fork does not build (the real path is ./build/ts/tool/libts/index.js), so
//      the bare `kcmd` import fails to resolve.
//   2. `ApiContext.default()` shells out to gcloud and reads the GLOBALLY ACTIVE
//      configuration. On this workstation that resolved to an unrelated qwiklabs
//      project — it would silently target the wrong catalog.
//
// So identity is passed explicitly, per CLAUDE.md rule 3 ("project routing is
// explicit, not inherited from whichever gcloud config is active").
//
// ONE THING WE CANNOT PASS EXPLICITLY. The kcmd CLI subprocess builds its own
// ApiContext, and `ApiContext.default()` resolves the catalog location from
// `gcloud -q config get-value compute/region`. That property is unset on the
// admin--royston-dev-8253 profile, so the CLI dies with "Unable to retrieve
// project, location, or token". Export `CLOUDSDK_COMPUTE_REGION=us` for the
// invocation — gcloud honours it per-process, so no profile is mutated. (`us`
// is the catalog location where the @bigquery entries live; it is not a compute
// region, but that is the property kcmd reads.)

import * as path from 'node:path';

function resolveEnv(name: string, fallbackName?: string, defaultVal?: string): string {
  const v = process.env[name] ?? (fallbackName ? process.env[fallbackName] : undefined) ?? defaultVal;
  if (!v) {
    throw new Error(
      `${name}${fallbackName ? ` (or ${fallbackName})` : ''} is not set. Required: OKF_PROJECT/GOOGLE_CLOUD_PROJECT, OKF_LOCATION/GOOGLE_CLOUD_LOCATION, OKF_ENTRY_GROUP.\n` +
      `  e.g. GOOGLE_CLOUD_PROJECT=your-project GOOGLE_CLOUD_LOCATION=us OKF_ENTRY_GROUP=okf_cymbal_v6z`,
    );
  }
  return v;
}

export const project = resolveEnv('OKF_PROJECT', 'GOOGLE_CLOUD_PROJECT');
export const location = resolveEnv('OKF_LOCATION', 'GOOGLE_CLOUD_LOCATION', 'us');
export const entryGroup = resolveEnv('OKF_ENTRY_GROUP', undefined, 'okf_cymbal_v6z');

/** Aspect key as Dataplex renders it: <project>.<location>.<aspectTypeId>. */
export const okfKey = `${project}.${location}.okf`;

/**
 * The kcmd CLI entry point. Upstream invokes the bun-compiled `dist/kcmd`
 * binary; this fork is built with `npm run build:mcp` (tsc), so we invoke the
 * compiled JS with node and avoid a bun dependency for the demo path.
 */
export const kcmdMain = process.env.KCMD_MAIN
  ?? path.resolve(import.meta.dirname ?? __dirname, '../../build/ts/tool/tool/main.js');
