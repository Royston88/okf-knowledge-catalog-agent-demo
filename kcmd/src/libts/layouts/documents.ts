// Implements the documents layout (markdown files in directory)
//

import * as glob from 'glob';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as yaml from 'yaml';
import {CatalogLayout} from '../core/layout';
import * as md from '../core/metadata';

const OVERVIEW_ASPECT_KEY = 'dataplex-types.global.overview';

/** Bundle-relative path minus `.md` / `.ref.md` — the id a file indexes under. */
function deriveEntryNameFromPath(localPath: string, catalogPath: string): string {
  let rel = path.relative(catalogPath, localPath).replace(/\\/g, '/');
  if (rel.endsWith('.ref.md')) rel = rel.slice(0, -'.ref.md'.length);
  else if (rel.endsWith('.md')) rel = rel.slice(0, -'.md'.length);
  return rel;
}

/**
 * Shape of the YAML frontmatter found at the top of a documents-layout
 * Markdown file. These fields mirror the human-authored frontmatter and the
 * stashed `catalogEntry`. `type` is always emitted by `toMarkdown`; the
 * remaining fields are optional because they are written only when present.
 */
interface DocumentFrontmatter {
  type: string;
  title?: string;
  description?: string;
  tags?: string[];
  timeStamp?: string;
  catalogEntry?: md.Entry;
}

/**
 * Catalog layout that stores each entry as a standalone Markdown file (with
 * YAML frontmatter for structured metadata and the Markdown body as the
 * entry's overview aspect) under a directory tree rooted at `catalogPath`.
 */
// FIX: the pull path aliases `dataplex-types.global.overview` to the short form
// `overview` (`ResourceAlias._defaultResource`, applied by `toLocalEntry`), but
// this layout only ever looked for the long key. Push therefore worked and pull
// silently returned every concept with an EMPTY BODY. Accept both forms.
function overviewKeyOf(aspects: Record<string, unknown> | undefined): string | undefined {
  if (!aspects) return undefined;
  if (aspects[OVERVIEW_ASPECT_KEY] !== undefined) return OVERVIEW_ASPECT_KEY;
  return Object.keys(aspects).find((k) => k === 'overview' || k.endsWith('.overview'));
}

export class DocumentsLayout implements CatalogLayout {
  private _catalogPath = '';

  private readonly _index = new Map<string, string>();

  constructor(catalogPath: string) {
    this._catalogPath = catalogPath;
  }

  async init(): Promise<void> {
    this._index.clear();

    if (!fs.existsSync(this._catalogPath)) {
      return;
    }

    const matches = await glob.glob('**/*.md', {
      cwd: this._catalogPath,
      absolute: true,
      nodir: true,
    });

    for (const localPath of matches) {
      try {
        const content = await fs.promises.readFile(localPath, 'utf8');
        const {entry} = parseMarkdown(content);
        // FIX: this used to require `entry.name`, which `parseMarkdown` never
        // sets — it rebuilds the entry from `catalogEntry` and derives no name
        // from the path. Any file without an explicit `catalogEntry.name` was
        // therefore skipped SILENTLY, and `push` then reported success over an
        // empty index. Fall back to a path-derived id, matching what
        // `OkfLayout.deriveEntryName` already does for hand-authored files.
        const name =
          entry?.name || deriveEntryNameFromPath(localPath, this._catalogPath);
        if (entry && name) {
          entry.name = name;
          this._index.set(name, localPath);
        }
      } catch (err) {
        // Skip unreadable/invalid files during indexing
      }
    }
  }

  entryExists(name: string): boolean {
    const entryPath = this._index.get(name);
    return !!entryPath && fs.existsSync(entryPath);
  }

  listEntries(): string[] {
    return Array.from(this._index.keys());
  }

  async loadEntry(name: string): Promise<md.Entry> {
    const entryPath = this._index.get(name);
    if (!entryPath || !fs.existsSync(entryPath)) {
      throw new Error(`Entry not found: ${name}`);
    }
    const content = await fs.promises.readFile(entryPath, 'utf8');
    const {entry, body} = parseMarkdown(content);

    if (!entry) {
      throw new Error(
        `Missing YAML frontmatter in Markdown file: ${entryPath}`,
      );
    }

    const bodyTrimmed = body.trim();
    if (bodyTrimmed) {
      if (!entry.aspects) {
        entry.aspects = {};
      }
      if (!entry.aspects[OVERVIEW_ASPECT_KEY]) {
        entry.aspects[OVERVIEW_ASPECT_KEY] = {};
      }
      entry.aspects[OVERVIEW_ASPECT_KEY].content = bodyTrimmed;
      entry.aspects[OVERVIEW_ASPECT_KEY].contentType = 'MARKDOWN';
    }
    return entry;
  }

  async saveEntry(name: string, entry: md.Entry): Promise<void> {
    const entryPath = path.join(this._catalogPath, `${name}.md`);
    await fs.promises.mkdir(path.dirname(entryPath), {recursive: true});

    // Clone to avoid mutating original entry aspects
    const clonedEntry = JSON.parse(JSON.stringify(entry)) as md.Entry;
    let body = '';

    const ovKey = overviewKeyOf(clonedEntry.aspects) ?? OVERVIEW_ASPECT_KEY;
    if (clonedEntry.aspects?.[ovKey]) {
      const aspect = clonedEntry.aspects[ovKey];
      if (aspect.content !== undefined) {
        body = aspect.content;
        delete aspect.content;
        delete aspect.contentType;
      }
    }

    const fileContent = toMarkdown(clonedEntry, body);

    await fs.promises.writeFile(entryPath, fileContent, 'utf8');
    this._index.set(name, entryPath);
  }

  async deleteEntry(name: string): Promise<void> {
    const entryPath = this._index.get(name);
    if (!entryPath || !fs.existsSync(entryPath)) {
      throw new Error(`Entry not found: ${name}`);
    }

    await fs.promises.unlink(entryPath);
    this._index.delete(name);
  }

  getEntryPaths(name: string): {local?: string; ref?: string} | undefined {
    const entryPath = this._index.get(name);
    return entryPath ? {local: entryPath} : undefined;
  }
}

/**
 * Parses a documents-layout Markdown file into its catalog entry and body.
 * Reads the optional leading YAML frontmatter, reconstructs the `md.Entry`
 * (merging frontmatter fields such as title, description, tags and timestamps
 * into the stashed `catalogEntry`), and returns the remaining Markdown body.
 * Returns a null entry when no valid frontmatter block is present.
 */
export function parseMarkdown(content: string): {
  entry: md.Entry | null;
  body: string;
} {
  const lines = content.split(/\r?\n/);
  if (lines[0] !== '---') {
    return {entry: null, body: content};
  }
  const endIndex = lines.indexOf('---', 1);
  if (endIndex === -1) {
    return {entry: null, body: content};
  }

  const frontmatter = lines.slice(1, endIndex).join('\n');
  const metadata = yaml.parse(frontmatter) as DocumentFrontmatter;
  const body = lines.slice(endIndex + 1).join('\n');

  const entry = (metadata.catalogEntry ?? {}) as md.Entry;
  entry.type = metadata.type;
  entry.resource = entry.resource ?? {};
  entry.resource.displayName = metadata.title;
  entry.resource.description = metadata.description;
  if (metadata.tags) {
    entry.resource.labels = entry.resource.labels ?? {};
    for (const tag of metadata.tags) {
      entry.resource.labels[tag] = 'true';
    }
  }
  if (metadata.timeStamp) {
    entry.resource.updateTime = metadata.timeStamp;
    if (!entry.resource.createTime) {
      entry.resource.createTime = metadata.timeStamp;
    }
  }

  return {entry, body};
}

/**
 * Serializes a Dataplex entry plus its Markdown body into a documents-layout
 * file: YAML frontmatter derived from the entry (type, title, description,
 * tags, timestamp) with the full entry stashed under `catalogEntry` for
 * lossless round-tripping, followed by the Markdown body. The stashed clone is
 * stripped of fields that are already surfaced as dedicated frontmatter keys to
 * avoid duplicating them.
 */
export function toMarkdown(entry: md.Entry, body: string): string {
  // Clone to be able to make modifications. `type` is widened to optional so
  // it can be deleted from the stash once promoted to a top-level key.
  const entryClone = JSON.parse(JSON.stringify(entry)) as Omit<
    md.Entry,
    'type'
  > & {type?: string};

  const tags: string[] = [];
  if (entry.resource.labels) {
    for (const [k, v] of Object.entries(entryClone.resource.labels ?? {})) {
      if (v === 'true') {
        tags.push(k);
      }
    }
  }

  const metadata = {
    type: entry.type,
    title: entry.resource.displayName ?? entry.resource.name,
    description: entry.resource.description ?? undefined,
    tags: tags.length ? tags : undefined,
    timeStamp:
      entry.resource.updateTime ?? entry.resource.createTime ?? undefined,
    catalogEntry: entryClone,
  };

  delete entryClone.resource.displayName;
  delete entryClone.resource.description;
  delete entryClone.resource.updateTime;
  delete entryClone.resource.createTime;
  delete entryClone.type;
  for (const tag of tags) {
    delete entryClone.resource.labels?.[tag];
  }

  const frontmatter = yaml.stringify(metadata).trim();
  return `---\n${frontmatter}\n---\n${body}`;
}
