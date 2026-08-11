// Catalog layout registry/factory. The layout CONTRACTS (CatalogLayout /
// Layouts / rootDirForLayout) live in ./core/layout and are re-exported here for
// back-compat; this module wires the concrete layout implementations under
// ./layouts/ via createLayout().
//

import {CatalogLayout, Layouts} from './core/layout';
import {DocumentsLayout} from './layouts/documents';
import {OkfLayout} from './layouts/okf';
import {StandardLayout} from './layouts/standard';
import {CatalogManifest} from './manifest';

export * from './core/layout';

/**
 * Factory that constructs the {@link CatalogLayout} implementation matching the
 * requested layout scheme, wired to the given catalog path and optional
 * manifest. Throws if the layout type is unrecognized.
 */
export function createLayout(
  layout: Layouts,
  catalogPath: string,
  manifest?: CatalogManifest,
): CatalogLayout {
  switch (layout) {
    case Layouts.STANDARD:
      return new StandardLayout(catalogPath, manifest);
    case Layouts.DOCUMENTS:
      return new DocumentsLayout(catalogPath);
    case Layouts.OKF:
      return new OkfLayout(catalogPath, manifest);
    default:
      throw new Error(`Unknown layout type: ${layout}`);
  }
}
