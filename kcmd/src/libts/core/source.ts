// Catalog metadata source CONTRACTS (interface/types/enum) -- the leaf shared by
// the source implementations under ../sources/ and by the parent registry
// (../source.ts). Kept registry-free so per-directory ts_libraries stay acyclic.

import * as gcp from '../gcp';
import * as dataplex from '../gcp/dataplex';
import {Layouts} from './layout';

/**
 * A resource produced by a {@link CatalogSource}. Depending on the source type
 * this is either a Dataplex catalog {@link dataplex.Entry} (entry groups,
 * knowledge bases, BigQuery datasets, BigLake namespaces) or one of the
 * glossary resource shapes ({@link dataplex.Glossary},
 * {@link dataplex.GlossaryCategory}, {@link dataplex.GlossaryTerm}). All
 * variants expose a `name`, which is what consumers rely on to derive local
 * names.
 */
export type SourceResource =
  | dataplex.Entry
  | dataplex.Glossary
  | dataplex.GlossaryCategory
  | dataplex.GlossaryTerm;

/**
 * Enumerates the supported Catalog metadata source types. Each value is the
 * string identifier used in manifests to select the corresponding
 * {@link CatalogSource} implementation.
 */
export enum Sources {
  ENTRYGROUP = 'entryGroup',
  BIGQUERY_DATASET = 'bq-dataset',
  KB = 'kb',
  BIGLAKE_NAMESPACE = 'biglake-namespace',
  BIGLAKE_ICEBERG_NAMESPACE = 'biglake-iceberg-namespace',
  GLOSSARY = 'glossary',
}

/**
 * Abstraction over a Catalog metadata source (e.g. an entry group, BigQuery
 * dataset, knowledge base, BigLake namespace or glossary scope). Implementations
 * know how to enumerate the source's resources and translate between
 * service-side names and the names used in the local snapshot.
 */
export interface CatalogSource {
  readonly type: string;
  readonly name: string;
  readonly namespace: string;
  readonly ingestedEntries: boolean;
  readonly layout: Layouts;

  entries(ctx: gcp.ApiContext): AsyncGenerator<SourceResource, void, unknown>;
  localName(resource: SourceResource, isReference?: boolean): string;
  serviceName(localName: string): string;
  tryGetLocalName(serviceName: string): string | undefined;
}
