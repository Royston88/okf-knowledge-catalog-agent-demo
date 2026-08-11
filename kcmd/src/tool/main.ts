// Main CLI entrypoint
//

import yargs from 'yargs';
import * as commands from './commands';

/**
 * Extracts a human-readable value from a caught error.
 *
 * Catch clause bindings are typed as `unknown`, so this narrows the value and
 * returns its `message` property when present, otherwise falls back to the
 * error value itself. This mirrors the `err.message || err` idiom used when
 * reporting CLI errors.
 */
function errorMessage(err: unknown): unknown {
  if (
    typeof err === 'object' &&
    err !== null &&
    'message' in err &&
    (err as {message: unknown}).message
  ) {
    return (err as {message: unknown}).message;
  }

  return err;
}

const FORMAT_OVERRIDE = 'On-disk layout override: standard | documents | okf';

// CLI built with yargs. Each handler builds the typed `*Options` object from the
// named argv flags (kebab key -> camelCase interface field) so tsc validates the
// mapping against the interface instead of trusting a blanket cast.
void yargs(process.argv.slice(2))
  .scriptName('kcmd')
  .version('1.0.0')
  .command(
    'init',
    'Initialize a new catalog snapshot',
    (y) =>
      y
        .option('entry-group', {
          type: 'string',
          describe: 'Identifier of the EntryGroup (project.location.id)',
        })
        .option('bigquery-dataset', {
          type: 'string',
          array: true,
          describe: 'Identifier of the BigQuery dataset(s) (project.datasetId)',
        })
        .option('biglake-namespace', {
          type: 'string',
          describe:
            'Identifier of the BigLake namespace (project.catalog.namespace)',
        })
        .option('iceberg', {
          type: 'boolean',
          describe: 'Specify that the BigLake namespace is an Iceberg catalog',
        })
        .option('kb', {
          type: 'string',
          describe:
            'Identifier of the Knowledge Base EntryGroup (project.location.id)',
        })
        .option('glossary', {
          type: 'string',
          describe: 'Identifier of the Glossary (project.location.id)',
        })
        .option('pull', {
          type: 'boolean',
          describe: 'Optionally pull catalog entries during initialization',
        })
        .option('format', {
          type: 'string',
          describe: 'On-disk layout: standard (default) | documents | okf',
        }),
    async (argv) => {
      let exitCode = 1;
      try {
        exitCode = await commands.init({
          entryGroup: argv['entry-group'],
          bigqueryDataset: argv['bigquery-dataset'],
          biglakeNamespace: argv['biglake-namespace'],
          iceberg: argv.iceberg,
          kb: argv.kb,
          glossary: argv.glossary,
          pull: argv.pull,
          format: argv.format,
        });
      } catch (err: unknown) {
        console.error('Error:', errorMessage(err));
        exitCode = 1;
      }

      process.exit(exitCode);
    },
  )
  .command(
    'pull',
    'Pull catalog entries',
    (y) =>
      y
        .option('dry-run', {
          type: 'boolean',
          describe: 'Perform a dry run without modifying local files',
        })
        .option('format', {type: 'string', describe: FORMAT_OVERRIDE}),
    async (argv) => {
      let exitCode = 1;
      try {
        exitCode = await commands.pull({
          dryRun: argv['dry-run'],
          format: argv.format,
        });
      } catch (err: unknown) {
        console.error('Error:', errorMessage(err));
        exitCode = 1;
      }

      process.exit(exitCode);
    },
  )
  .command(
    'push',
    'Push catalog entries',
    (y) =>
      y
        .option('force', {type: 'boolean', describe: 'Force push changes'})
        .option('validate-only', {
          type: 'boolean',
          describe: 'Only validate changes without applying',
        })
        .option('dry-run', {
          type: 'boolean',
          describe: 'Perform a dry run without publishing to service',
        })
        .option('format', {type: 'string', describe: FORMAT_OVERRIDE}),
    async (argv) => {
      let exitCode = 1;
      try {
        exitCode = await commands.push({
          force: argv.force,
          validateOnly: argv['validate-only'],
          dryRun: argv['dry-run'],
          format: argv.format,
        });
      } catch (err: unknown) {
        console.error('Error:', errorMessage(err));
        exitCode = 1;
      }

      process.exit(exitCode);
    },
  )
  .command(
    'reference',
    'Pull reference resource entries',
    (y) => y.option('format', {type: 'string', describe: FORMAT_OVERRIDE}),
    async (argv) => {
      let exitCode = 1;
      try {
        exitCode = await commands.reference({
          format: argv.format,
        });
      } catch (err: unknown) {
        console.error('Error:', errorMessage(err));
        exitCode = 1;
      }

      process.exit(exitCode);
    },
  )
  .demandCommand(1, "Error: a command is required (try 'kcmd --help').")
  .strict()
  .help()
  .parseAsync();
