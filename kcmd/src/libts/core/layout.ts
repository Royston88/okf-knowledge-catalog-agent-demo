// Catalog layout CONTRACTS (interface/enum + a pure helper) -- the leaf shared
// by the layout implementations under ../layouts/ and the parent registry
// (../layout.ts). Registry-free so per-directory ts_libraries stay acyclic.

import * as md from './metadata';

/**
 * Identifies the on-disk catalog layout schemes supported by the tool. Each
 * value selects a different directory structure and serialization strategy for
 * catalog entries.
 */
export enum Layouts {
  STANDARD = 'standard',
  DOCUMENTS = 'documents',
  OKF = 'okf',
}

/**
 * Returns the on-disk root directory name used by the given layout. OKF bundles
 * live under `bundle/`; the kcmd-native layouts use `catalog/`.
 */
export function rootDirForLayout(layout: Layouts): string {
  return layout === Layouts.OKF ? 'bundle' : 'catalog';
}

/**
 * Abstraction over a catalog's on-disk representation. Implementations handle
 * reading, writing, and deleting catalog entries for a particular layout
 * scheme, hiding the directory structure and serialization details from
 * callers.
 */
export interface CatalogLayout {
  init(): Promise<void>;

  entryExists(name: string): boolean;
  listEntries(): string[];
  loadEntry(name: string): Promise<md.Entry>;
  saveEntry(name: string, entry: md.Entry): Promise<void>;
  deleteEntry(name: string): Promise<void>;
  getEntryPaths(name: string): {local?: string; ref?: string} | undefined;

  // Optional post-sync hook (e.g. OKF regenerates reserved index.md listings
  // after a pull). Layouts that don't need it simply omit it.
  finalize?(): Promise<void>;
}
