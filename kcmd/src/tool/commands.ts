// CLI command handlers
//

import * as fs from 'node:fs';

import * as kcmd from '../libts';
import * as context from '../libts/gcp/context';
import * as dataplex from '../libts/gcp/dataplex';

/**
 * Options accepted by the `init` command, controlling which catalog source the
 * local manifest is initialized from and how it is laid out and optionally
 * pulled.
 */
export interface InitOptions {
  entryGroup?: string;
  bigqueryDataset?: string | string[];
  biglakeNamespace?: string;
  iceberg?: boolean;
  kb?: string;
  glossary?: string;
  pull?: boolean;
  format?: string;
}

/**
 * Options accepted by the `pull` command, controlling whether the pull is a dry
 * run and which on-disk layout format to use.
 */
export interface PullOptions {
  dryRun?: boolean;
  format?: string;
}

/**
 * Options accepted by the `push` command, controlling force/validate-only/dry-run
 * behavior and which on-disk layout format to use.
 */
export interface PushOptions {
  force?: boolean;
  validateOnly?: boolean;
  dryRun?: boolean;
  format?: string;
}

/**
 * Initializes a local `catalog.yaml` manifest from the requested catalog source
 * (entry group, knowledge base, glossary, BigQuery dataset(s), or BigLake
 * namespace), writes it to disk, and optionally performs an initial pull.
 *
 * @param options Source selection and layout/pull options for initialization.
 * @return A process exit code (0 on success, non-zero on error).
 */
export async function init(options: InitOptions): Promise<number> {
  const ctx = context.ApiContext.default();

  let manifest: kcmd.CatalogManifest;
  if (options.entryGroup) {
    manifest = await kcmd.CatalogManifest.initWithEntryGroup(
      options.entryGroup,
      ctx,
    );
  } else if (options.kb) {
    manifest = await kcmd.CatalogManifest.initWithKnowledgeBase(
      options.kb,
      ctx,
    );
  } else if (options.glossary) {
    manifest = await kcmd.CatalogManifest.initWithGlossary(
      options.glossary,
      ctx,
    );
  } else if (options.bigqueryDataset) {
    let datasets = '';
    if (Array.isArray(options.bigqueryDataset)) {
      datasets = options.bigqueryDataset.join(',');
    } else {
      datasets = options.bigqueryDataset!;
    }
    manifest = await kcmd.CatalogManifest.initWithBigQuery(datasets, ctx);
  } else if (options.biglakeNamespace) {
    if (!options.iceberg) {
      console.error(
        'Error: Must specify --iceberg when initializing a BigLake namespace (other metastores are not supported yet)',
      );
      return 1;
    }
    manifest = await kcmd.CatalogManifest.initWithBigLakeNamespace(
      options.biglakeNamespace,
      'iceberg',
      ctx,
    );
  } else {
    console.error(
      'Error: Must provide either --entry-group, --bigquery-dataset, --biglake-namespace, --kb, or --glossary',
    );
    return 1;
  }

  if (options.format) {
    manifest.layout = options.format;
  }

  manifest.save('catalog.yaml');
  console.log(fs.readFileSync('catalog.yaml', 'utf8'));

  if (options.pull) {
    return await pull({format: options.format});
  }

  return 0;
}

/**
 * Pulls catalog entries from the remote catalog into the local snapshot,
 * finalizing the on-disk layout on success.
 *
 * @param options Optional dry-run and layout format options for the pull.
 * @return A process exit code (0 on success, non-zero on error).
 */
export async function pull(options?: PullOptions): Promise<number> {
  const ctx = context.ApiContext.default();
  const snapshot = await kcmd.CatalogSnapshot.fromPath(
    '.',
    ctx,
    false,
    options?.format,
  );

  const catalog = new dataplex.CatalogClient(ctx);
  const sync = new kcmd.CatalogSync(catalog, snapshot);

  console.log('Pulling catalog entries...');
  const result = await sync.pull(options);

  if (result.success) {
    // OKF regenerates reserved index.md listings after the pull; no-op for
    // other layouts.
    await snapshot.finalize();
    console.log('Successfully updated local snapshot.');
    return 0;
  } else {
    console.error('Error pulling catalog entries:', result.details);
    return 1;
  }
}

/**
 * Pushes local catalog entries from the snapshot to the remote catalog.
 *
 * @param options Force/validate-only/dry-run and layout format options for the
 *     push.
 * @return A process exit code (0 on success, non-zero on error).
 */
export async function push(options: PushOptions): Promise<number> {
  const ctx = context.ApiContext.default();
  const snapshot = await kcmd.CatalogSnapshot.fromPath(
    '.',
    ctx,
    false,
    options.format,
  );

  const catalog = new dataplex.CatalogClient(ctx);
  const sync = new kcmd.CatalogSync(catalog, snapshot);

  console.log('Pushing catalog entries...');
  const result = await sync.push(options);

  if (result.success) {
    console.log('Successfully pushed catalog entries.');
    return 0;
  } else {
    console.error('Error pushing catalog entries:', result.details);
    return 1;
  }
}

/**
 * Options accepted by the `reference` command, controlling which on-disk layout
 * format to use when pulling reference entries.
 */
export interface ReferenceOptions {
  format?: string;
}

/**
 * Pulls reference entries from the remote catalog into the local snapshot,
 * finalizing the on-disk layout on success.
 *
 * @param options Optional layout format options for the reference pull.
 * @return A process exit code (0 on success, non-zero on error).
 */
export async function reference(options?: ReferenceOptions): Promise<number> {
  const ctx = context.ApiContext.default();

  const snapshot = await kcmd.CatalogSnapshot.fromPath(
    '.',
    ctx,
    true,
    options?.format,
  );

  const catalog = new dataplex.CatalogClient(ctx);
  const sync = new kcmd.CatalogSync(catalog, snapshot);

  console.log('Pulling reference entries...');
  const result = await sync.reference();

  if (result.success) {
    // OKF regenerates reserved index.md listings after pulling references.
    await snapshot.finalize();
    console.log('Successfully updated local reference entries snapshot.');
    return 0;
  } else {
    console.error('Error pulling reference entries:', result.details);
    return 1;
  }
}
