// Defines metadata objects provided by the catalog snapshot
//

/**
 * An aspect attached to a catalog entry or entry link. Aspects carry
 * schema-defined metadata whose concrete shape varies by aspect type, so the
 * field values are modeled as `unknown` and must be narrowed before use.
 */
export interface Aspect {
  content?: string;
  contentType?: string;
  [key: string]: unknown;
}

/**
 * A catalog entry from the Dataplex catalog snapshot, describing a single
 * resource together with its identifying metadata, aspects, and links to
 * related entries.
 */
export interface Entry {
  name: string;
  type: string;
  resource: {
    name?: string;
    displayName?: string;
    description?: string;
    labels?: Record<string, string>;
    location?: string;
    parent?: string;
    ancestors?: Array<{
      name: string;
      type: string;
    }>;
    createTime?: string;
    updateTime?: string;
  };
  aspects?: Record<string, Aspect>;
  links?: Record<string, EntryLink[]>;
}

/**
 * A directed link from a catalog entry to a related target, optionally carrying
 * an identifier and its own aspects describing the relationship.
 */
export interface EntryLink {
  target: string;
  id?: string;
  aspects?: Record<string, Aspect>;
}
