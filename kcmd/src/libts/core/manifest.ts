// Manifest CONTRACTS (pure config shapes + the subdir-facing manifest view) --
// the leaf shared by the layout implementations under ../layouts/. The concrete
// `CatalogManifest` class (which uses the source registry) stays in
// ../manifest.ts and implements `CatalogManifestLike`.

import {CatalogSource} from './source';

/**
 * Describes an entry link emitted locally for a manifest: the fully-qualified
 * entry link type together with the entry references it connects.
 */
export interface LocalEntryLink {
  type: string;
  references: string[];
}

/**
 * Selects which entries, aspects and entry links are included when taking a
 * snapshot of a catalog source.
 */
export interface SnapshotConfig {
  entries?: string[];
  aspects?: string[];
  entryLinks?: string[];
}

/**
 * Selects which entries, aspects and entry links are published from a snapshot.
 * Every type listed here must also appear in the corresponding
 * {@link SnapshotConfig}.
 */
export interface PublishingConfig {
  entries?: string[];
  aspects?: string[];
  entryLinks?: string[];
}

/**
 * Identifies a single catalog scope by its source type and resource name.
 */
export interface Scope {
  type: string;
  name: string;
}

/**
 * Configures a reference catalog (a secondary scope and optional snapshot) used
 * to resolve cross-catalog links during publishing.
 */
export interface ReferenceConfig {
  scope: string | string[];
  snapshot?: SnapshotConfig;
}

/**
 * The read-only view of a catalog manifest that layout implementations depend
 * on (its source plus snapshot/publishing config). The concrete
 * `CatalogManifest` class implements this; depending on the interface keeps the
 * layout directory free of the source-registry machinery.
 */
export interface CatalogManifestLike {
  readonly source: CatalogSource;
  readonly snapshotConfig?: SnapshotConfig;
  readonly publishingConfig?: PublishingConfig;
}
