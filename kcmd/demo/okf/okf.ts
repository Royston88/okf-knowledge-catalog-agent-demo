// Translation between clean OKF frontmatter and the kcmd "pushable" form.
//
// kcmd's generic Documents Layout only maps title/description/tags + body and
// passes a `catalogEntry:` block through verbatim. The OKF signal layer
// (type, resource, generated, sources, verified, status, stale_after) has no
// generic home, so we move it into a custom `okf` Dataplex aspect carried
// through that passthrough. This keeps the library generic — all OKF knowledge
// lives here in the demo.
//
// PORTED from GoogleCloudPlatform/knowledge-catalog @ 374e0bc,
// toolbox/mdcode/demo/okf/okf.ts. Divergence from upstream: SIGNAL_KEYS is
// extended with `verified`, `status` and `stale_after` (OKF v0.2 trust and
// lifecycle), which the shipped aspect schema omits. See ../../../PROVENANCE.md.

import * as yaml from 'yaml';

export interface Split { meta: any | null; body: string; }

// The OKF frontmatter keys carried on the custom aspect. `okf_type` is stored
// under that name because `type` is reserved on the Dataplex entry itself.
const SIGNAL_KEYS = ['okf_type', 'generated', 'sources', 'verified', 'status', 'stale_after',
                     'title', 'tags'];

// WHY `title` AND `tags` RIDE ON THE ASPECT.
//
// The MEASUREMENT is unchanged and still holds: on an INGESTED entry
// (`@bigquery`) `displayName` stays the native `accounts` and
// `labels`/`description` stay absent no matter what we push, so a pull returned
// the platform's title and no tags and the round trip was not an inverse.
// Re-confirmed at `view=ALL` — see `_state/probe_entries.json`.
//
// THE EXPLANATION WAS WRONG, and it is worth correcting because it changes what
// kind of problem this is. It is not that `entry_source` is platform-owned and
// Dataplex refuses the write. It is that **kcmd never makes the write**:
// `toServiceEntry` (snapshot.ts) early-returns `{name, entryType, aspects}` when
// `manifest.source.ingestedEntries`, so displayName, description, labels,
// resource and both timestamps are dropped CLIENT-SIDE and never sent. The
// fix below is still the right one — it is the only thing that survives an
// unmodified kcmd — but the underlying cause is a fixable client behaviour, not
// a platform constraint, and it belongs on the upstream defect list.
//
// Track B entries are ours and would round-trip either way; carrying them here
// uniformly keeps one code path. `description` needs no such treatment — it
// round-trips via the `descriptions` aspect, which we own on Track A.

// The Dataplex entry type every OKF concept is stored as. OKF's own `type` is
// freeform ("BigQuery Table", "Join", "Metric") and is not a Dataplex type ref,
// so it rides on the okf aspect as `okf_type` and the entry itself is generic.
const ENTRY_TYPE = 'dataplex-types.global.generic';

// Dataplex REQUIRES the aspect that corresponds to an entry's type to be
// present on create: an entry of type `…/aspectTypes/generic` without a
// `dataplex-types.global.generic` aspect is rejected with
//   400 "Missing required Aspect(s): …/aspectTypes/generic".
// The fork's own OkfLayout stamps the same aspect (with `type`/`system`) on
// every index entry it synthesizes; concepts need it for the same reason.
const GENERIC_ASPECT_KEY = 'dataplex-types.global.generic';

export function splitFrontmatter(content: string): Split {
  const lines = content.split(/\r?\n/);
  if (lines[0] !== '---') {
    return { meta: null, body: content };
  }
  const end = lines.indexOf('---', 1);
  if (end === -1) {
    return { meta: null, body: content };
  }
  const meta = yaml.parse(lines.slice(1, end).join('\n'));
  const body = lines.slice(end + 1).join('\n');
  return { meta, body };
}

function render(meta: any, body: string): string {
  const fm = yaml.stringify(meta).trimEnd();
  return `---\n${fm}\n---\n\n${body.trim()}\n`;
}

// Keep only present keys, in a stable order, so round-trips are deterministic.
function pick(obj: any, keys: string[]): any {
  const out: any = {};
  for (const k of keys) {
    if (obj && obj[k] !== undefined && obj[k] !== null) {
      out[k] = obj[k];
    }
  }
  return out;
}

// clean OKF -> pushable (signal moved into catalogEntry / okf aspect)
//
// `entryName` is the entry id the concept is indexed and pushed under — the
// bundle-relative path without its `.md` suffix (`tables/accounts`). It is
// REQUIRED, and the reason is the Phase 5 blocker:
//
//   DocumentsLayout.init() indexes on `entry.name` and nothing else
//   (`if (entry && entry.name) this._index.set(entry.name, localPath)`), while
//   `parseMarkdown` reconstructs the entry as `metadata.catalogEntry ?? {}` and
//   never derives a name from the file path. toStaging used to emit only
//   `catalogEntry.resource.name` (a BigQuery resource URI, not an entry name),
//   so every one of the 59 staged files parsed fine, indexed as nothing, and
//   `push` reported success over an empty index.
//
// A bare multi-segment id is correct here: `KnowledgeBaseSource.serviceName`
// strips the `<namespace>/<project>/<location>/` prefix only when present and
// otherwise treats the whole name as the entry id, so `tables/accounts` maps to
// `<entryGroup>/entries/tables/accounts`. This mirrors what the fork's own
// `OkfLayout.deriveEntryName` does for x-kcmd-less files.
//
// `entryType` defaults to the generic Dataplex type used for Track B's
// standalone concepts. Track A projects onto entries that Dataplex has ALREADY
// ingested (`@bigquery` tables and datasets), whose type is fixed and must be
// echoed back rather than overwritten with `generic` — so it passes the real
// one. The `generic` aspect is emitted only for generic entries, since it is
// required exactly when the entry type requires it.
export function toStaging(
  content: string,
  okfKey: string,
  entryName: string,
  entryType: string = ENTRY_TYPE,
  withAssetAspects = false,
): string {
  const { meta, body } = splitFrontmatter(content);
  if (!meta) {
    return content;
  }
  const staged = pick(meta, ['title', 'description', 'tags']);
  // FORK DIVERGENCE (measured). Upstream's documents layout validates the
  // frontmatter `type` and falls back to generic when it is not a 3-part
  // Dataplex ref:
  //     entry.type = (typeof metadata.type === 'string'
  //                   && metadata.type.split('.').length === 3) ? ... : GENERIC
  // This fork assigns it verbatim (`entry.type = metadata.type`). Since
  // toStaging deliberately does NOT carry the OKF `type` in the staged
  // frontmatter — it belongs on the okf aspect as `okf_type` — entries arrived
  // with `type: undefined` and `push` skipped every one of them while still
  // reporting "Successfully pushed catalog entries". Setting the Dataplex entry
  // type explicitly reproduces upstream's effective behaviour.
  staged.type = entryType;
  const aspects: any = {};
  if (entryType === ENTRY_TYPE) {
    aspects[GENERIC_ASPECT_KEY] = { type: meta.type, system: 'okf' };
  }
  if (withAssetAspects) {
    Object.assign(aspects, assetAspects(meta, body));
  }
  staged.catalogEntry = {
    name: entryName,
    resource: { name: meta.resource },
    aspects: Object.assign(aspects, {
      [okfKey]: pick(
        {
          okf_type: meta.type,
          generated: meta.generated,
          sources: meta.sources,
          verified: meta.verified,
          status: meta.status,
          stale_after: meta.stale_after,
          title: meta.title,
          tags: meta.tags,
        },
        SIGNAL_KEYS,
      ),
    }),
  };
  return render(staged, body);
}

// ---------------------------------------------------------------------------
// The kcmd-NATIVE staging form: OKF frontmatter + the `x-kcmd` stash.
//
// WHY THIS EXISTS, and why it is not a reversal of rule 1.
//
// `toStaging` above emits `catalogEntry:`, which is DocumentsLayout's
// passthrough. `toOkfStaging` emits `x-kcmd`, which is OkfLayout's. They are the
// same idea — kcmd's own comment at documents.ts:148 calls `catalogEntry` "the
// stashed catalogEntry" — so the honest statement of rule 1 was never "no stash,
// either way": it is **no stash in the SOURCE; the stash is a build artifact**.
// `okf-bundle/` has never contained either key and never will; `.staging/` is
// gitignored and deleted on exit. What changes here is which of kcmd's two
// stash keys the throwaway tree uses, and the answer is now the one kcmd's own
// OKF layout reads.
//
// WHAT THAT BUYS, measured in Phase 3:
//   - an UNMODIFIED kcmd can consume the staged tree. The `catalogEntry` form
//     could not: `type: BigQuery Table` is not 3-part-dotted, so upstream's
//     parse falls through to `generic`, and the publishing filter then compares
//     `…generic` against `[bigquery-dataset, bigquery-table]` and drops all 14
//     asset-backed concepts WHILE REPORTING SUCCESS.
//   - `index.md` handling for free. OkfLayout synthesises a directory `index`
//     entry per folder and regenerates the listings in `finalize()`; the
//     documents layout does neither, which is the whole of the `index.md` gap.
//   - kcmd's MCP server (`src/tool/mcp.ts`, Google's, not the fork's) can read
//     the same tree.
//
// THE SHAPE, and the two things that are load-bearing about it:
//
//   type: BigQuery Table        <- UNCHANGED. `parseOkf` requires a 3-part
//                                  dotted Dataplex ref to honour a frontmatter
//                                  type and otherwise falls back to the STASHED
//                                  type. So the source keeps its own vocabulary
//                                  (rule 4) and the entry still gets the right
//                                  Dataplex type — from `x-kcmd.type`.
//   x-kcmd.aspects[generic]     <- REQUIRED on a generic entry. Dataplex rejects
//                                  create with 400 "Missing required Aspect(s)"
//                                  without it.
//
// `overview` is deliberately NOT in the stash: `OkfLayout._loadLayer` promotes
// the markdown body into it. Putting it in both would push the body twice.
export function toOkfStaging(
  content: string,
  okfKey: string,
  entryName: string,
  entryType: string = ENTRY_TYPE,
  withAssetAspects = false,
): string {
  const { meta, body } = splitFrontmatter(content);
  if (!meta) {
    return content;
  }

  const aspects: any = {};
  if (entryType === ENTRY_TYPE) {
    aspects[GENERIC_ASPECT_KEY] = { type: meta.type, system: 'okf' };
  }
  if (withAssetAspects) {
    Object.assign(aspects, assetAspects(meta, body));
  }
  aspects[okfKey] = pick(
    {
      okf_type: meta.type,
      generated: meta.generated,
      sources: meta.sources,
      verified: meta.verified,
      status: meta.status,
      stale_after: meta.stale_after,
      title: meta.title,
      tags: meta.tags,
    },
    SIGNAL_KEYS,
  );

  // A complete `md.Entry`. `parseOkf` would rebuild `resource` from the OKF
  // keys above it, so this is redundant against THIS file — but a stash is only
  // worth the name if it stands alone, and kcmd's contract is that `x-kcmd`
  // reconstructs the entry by itself.
  const stash: any = {
    name: entryName,
    type: entryType,
    resource: pick(
      {
        name: meta.resource,
        displayName: meta.title,
        description: meta.description,
        labels: Array.isArray(meta.tags)
          ? Object.fromEntries(meta.tags.map((t: string) => [t, 'true']))
          : undefined,
      },
      ['name', 'displayName', 'description', 'labels'],
    ),
    aspects,
  };

  const staged = pick(meta, ['type', 'title', 'description', 'tags']);
  // DEEP-CLONE THE STASH. `tags` (and `generated`, `sources`, `verified`) are
  // the SAME object references as the ones already in `staged`, and
  // `yaml.stringify` renders a repeated reference as an anchor + alias:
  //
  //     tags: &a1
  //       - metric
  //     ...
  //         tags: *a1
  //
  // Legal YAML that every parser resolves, and still wrong here: the staged
  // file is an interop artifact meant to be read by an unmodified kcmd, by
  // kcmd's MCP server, and by a human debugging a push, and an alias makes the
  // stash non-self-contained in exactly the way `x-kcmd` exists to prevent.
  staged['x-kcmd'] = JSON.parse(JSON.stringify(stash));
  return render(staged, body);
}

/**
 * Which staging form to emit. `x-kcmd` is the default and the interop path;
 * `catalogEntry` is kept because it is the only form that works against a fork
 * WITHOUT `OkfLayout` — which is every checkout of Google's repo, since
 * `layouts/okf.ts` is fork-only.
 *
 *     OKF_STAGING_FORM=catalogEntry   fall back to the documents-layout stash
 */
export function stagingEmitter(): {
  emit: typeof toOkfStaging;
  form: string;
  layout: string;
  rootDir: string;
} {
  const form = process.env.OKF_STAGING_FORM ?? 'x-kcmd';
  if (form === 'catalogEntry') {
    // `rootDirForLayout` in kcmd returns `bundle` for okf and `catalog`
    // otherwise, and the staged tree has to match or the layout globs nothing.
    return { emit: toStaging, form, layout: 'documents', rootDir: 'catalog' };
  }
  if (form !== 'x-kcmd') {
    throw new Error(`OKF_STAGING_FORM must be x-kcmd or catalogEntry, got ${form}`);
  }
  return { emit: toOkfStaging, form, layout: 'okf', rootDir: 'bundle' };
}

// ---------------------------------------------------------------------------
// Track A only: the two aspects the DATA_DOCUMENTATION scan owns.
//
// `descriptions` is what the BigQuery/Dataplex UI renders as a table's
// description and its per-column docs, and `queries` is the suggested-SQL list.
// If the bundle is the source of truth it has to own them, or the scan's
// generated prose is what a human actually reads.
//
// MEASURED, AND NOT WHAT WE FIRST ASSUMED: this does NOT make the content
// reachable at an MCP client's default read. Dataplex's `view=FULL` returns
// required aspects plus only the KEYS of non-required ones, and `descriptions`,
// `queries` and `overview` are ALL non-required — so all three are withheld
// unless the caller asks for `view=ALL`. (A `view=FULL` response still mentions
// `load_batch_id`, but that is the column NAME from the required `schema`
// aspect, not our description of it. That coincidence is what made the first
// reading wrong.) Owning these aspects is worth doing for the UI and for
// ownership; it does not solve reach.
//
// MEASUREMENT G MAKES `userManaged: true` MANDATORY HERE. These aspects are
// scan-owned: content written to them with the flag left false is destroyed by
// the next scan, silently and with no error. Setting it is the whole difference
// between projecting and appearing to project.
const DESCRIPTIONS_KEY = 'dataplex-types.global.descriptions';
const QUERIES_KEY = 'dataplex-types.global.queries';

/**
 * Rows of the body's `# Schema` markdown table -> [{name, description}].
 *
 * The bundle is NOT uniform — its 13 table concepts were authored by an LLM and
 * it invented two layouts:
 *   | Field      | Type | Description |            with `name` in backticks
 *   | Field Name | Type | Mode | Description |     with **name** in bold
 * so the parser takes the FIRST cell as the name and the LAST as the
 * description, strips either emphasis marker, and drops header and separator
 * rows. Assuming column 3 (as the first version did) silently produced zero
 * fields for 4 of 13 tables.
 */
export function schemaFields(body: string): Array<{ name: string; description: string }> {
  const out: Array<{ name: string; description: string }> = [];
  let inSection = false;
  let pastSeparator = false;
  for (const line of body.split(/\r?\n/)) {
    if (/^#\s/.test(line)) {
      inSection = /^#\s+Schema\s*$/i.test(line);
      pastSeparator = false;
      continue;
    }
    if (!inSection || !line.trim().startsWith('|')) continue;
    const cells = line.split('|').slice(1, -1).map((c) => c.trim());
    if (cells.length < 2) continue;
    // The header row is the one BEFORE the `|:---|` separator. Detect it
    // structurally rather than by keyword: an earlier version skipped any first
    // cell matching /^(field|column|name)$/i, which silently ate every column
    // literally called `name` — two of them here — and made the bundle look
    // incomplete when it was not.
    if (cells.every((c) => /^:?-{2,}:?$/.test(c))) { pastSeparator = true; continue; }
    if (!pastSeparator) continue;
    const name = cells[0].replace(/[`*]/g, '').trim();
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) continue;                 // prose row
    const description = cells[cells.length - 1];
    if (description) out.push({ name, description });
  }
  return out;
}

/** `### N. Title` + fenced sql blocks under `# Common query patterns`. */
export function queryPatterns(body: string): Array<{ sql: string; description: string }> {
  const out: Array<{ sql: string; description: string }> = [];
  let inSection = false, title = '', prose: string[] = [], sql: string[] | null = null;
  const flush = () => {
    if (sql && sql.length) {
      const desc = [title, prose.join(' ').trim()].filter(Boolean).join(' — ');
      out.push({ sql: sql.join('\n').trim(), description: desc.trim() });
    }
    sql = null;
  };
  for (const line of body.split(/\r?\n/)) {
    if (/^#\s/.test(line)) {
      flush();
      inSection = /^#\s+Common query patterns\s*$/i.test(line);
      title = ''; prose = [];
      continue;
    }
    if (!inSection) continue;
    const h = line.match(/^#{2,4}\s+(?:\d+\.\s*)?(.+?)\s*$/);
    if (h && sql === null) { flush(); title = h[1]; prose = []; continue; }
    if (/^```/.test(line)) {
      if (sql === null) { sql = []; } else { flush(); }
      continue;
    }
    if (sql !== null) { sql.push(line); }
    else if (line.trim()) { prose.push(line.trim()); }
  }
  flush();
  return out;
}

/**
 * The `descriptions` + `queries` aspects for an asset-backed concept.
 *
 * OWNERSHIP IS GATED ON `verified`, and that is the whole point.
 *
 * These two aspects are CONTESTED — the DATA_DOCUMENTATION scan wants them, and
 * `userManaged` decides who wins. Claiming them unconditionally means writing
 * UNREVIEWED LLM output into the field a human reads in the UI and then freezing
 * it against every future scan. The scan's version at least gets refreshed; a
 * frozen guess does not. `verified` is exactly the signal that separates "a
 * human vouched for this" from "a machine guessed", so it is the right gate.
 *
 * Unverified concepts are not abandoned: they still project their body to
 * `overview` and their signal layer to `okf`, both uncontested and both
 * bundle-owned. They simply do not override the scan on the aspects the scan
 * owns. The bundle remains the complete record; what it CLAIMS in a downstream
 * implementation is governed by its own trust tier.
 *
 * Note where `userManaged` therefore lives: nowhere. It is not an OKF field and
 * not a config value — it is COMPUTED from `verified` at projection time, which
 * is correct if Knowledge Catalog is one projection target among several.
 */
/**
 * The `descriptions` + `queries` aspects for an asset-backed concept.
 *
 * THE RULE, AND IT IS THE WHOLE RULE:
 *
 *   the bundle always projects overview + descriptions + queries
 *   `userManaged` = whether the concept is `verified`
 *
 * Verified content is frozen against the DATA_DOCUMENTATION scan; unverified
 * content is written too, but left unprotected, so the next scan replaces it.
 * That is the intended meaning of a trust tier: the bundle is always the source,
 * and sign-off is what makes the catalog stop second-guessing it.
 *
 * `overview` is handled by the normal body projection and carries no flag — the
 * aspect type has no `userManaged` field (`content`/`links`/`contentType` only)
 * and the scan does not write it, so it is unconditionally safe. That asymmetry
 * is a property of Dataplex, not a decision here.
 *
 * `userManaged` is stored nowhere — not in the bundle, not in config. It is
 * computed at push time, which is correct if Knowledge Catalog is one
 * projection target among several rather than the system of record.
 */
export function assetAspects(meta: any, body: string): Record<string, any> {
  const userManaged = Array.isArray(meta?.verified) && meta.verified.length > 0;
  const aspects: Record<string, any> = {};

  const fields = schemaFields(body);
  if (meta.description || fields.length) {
    aspects[DESCRIPTIONS_KEY] = {
      userManaged,
      ...(meta.description ? { description: meta.description } : {}),
      ...(fields.length ? { fields } : {}),
    };
  }

  const patterns = queryPatterns(body);
  if (patterns.length) {
    aspects[QUERIES_KEY] = {
      userManaged,
      queries: patterns.map((q) => ({
        sql: q.sql,
        description: q.description,
        source: 'AGENT',
        sqlDialect: 'GOOGLE_SQL',
      })),
    };
  }
  return aspects;
}

/** `projects/P/datasets/D[/tables/T]` -> the REST URL form the bundle uses. */
export function toBigQueryResourceUrl(name: string): string {
  return /^projects\/[^/]+\/datasets\/[^/]+(\/tables\/[^/]+)?$/.test(name)
    ? `https://bigquery.googleapis.com/v2/${name}`
    : name;
}

// pushable (as returned by `kcmd pull`) -> clean OKF
export function fromStaging(content: string, okfKey: string): string {
  const { meta, body } = splitFrontmatter(content);
  if (!meta) {
    return content;
  }
  const ce = meta.catalogEntry ?? {};
  // MEASURED (Phase 3 smoke test): Dataplex accepts an aspect key qualified by
  // project ID on write but returns it qualified by project NUMBER on read
  // (`royston-dev-8253.us.okf` in -> `404799090046.us.okf` out), exactly as the
  // built-in types surface as `655216118709.global.overview`. Matching only the
  // configured key silently drops the whole signal layer on pull, so accept any
  // key with the same `<location>.okf` suffix.
  const aspects = ce.aspects ?? {};
  const suffix = okfKey.slice(okfKey.indexOf('.'));   // ".<location>.okf"
  const matched = Object.keys(aspects).find((k) => k === okfKey || k.endsWith(suffix));
  const okf = matched ? aspects[matched] : {};

  // MEASURED (Measurement A): on pull the concept BODY does not come back as the
  // markdown body — it comes back stashed inside `catalogEntry.aspects` under the
  // bare key `overview`, and the body is empty.
  //
  // The cause is an alias asymmetry in the fork. `ResourceAlias._defaultResource`
  // maps `dataplex-types.global.overview` -> the short alias `overview`, and
  // `toLocalEntry` applies it to every aspect key on the way in
  // (`aspects[aliasMap.lookupResource(key, ASPECT)]`). But DocumentsLayout —
  // and the fork's own OkfLayout — promote the body to/from the *unaliased*
  // constant `OVERVIEW_ASPECT_KEY = 'dataplex-types.global.overview'`. So the
  // push direction works (loadEntry writes the long key, lookupAlias passes it
  // through untouched) and the pull direction silently does not. `standard.ts`
  // is the only layout that handles both forms (`key === 'overview'`).
  //
  // For OKF the body IS the concept, so this is a total content loss, not churn.
  // Recover it here: accept the short alias, the long key, and the
  // project-number-qualified service form.
  const ovKey = Object.keys(aspects).find(
    (k) => k === 'overview' || k.endsWith('.overview'),
  );
  const ovContent = ovKey ? (aspects[ovKey]?.content ?? '') : '';
  const effectiveBody = body.trim() ? body : ovContent;

  // Directory index entries carry no OKF signal — emit body only, matching the
  // frontmatter-free index files in the source bundle.
  const isOkf = SIGNAL_KEYS.some((k) => okf[k] !== undefined)
    || ce.resource?.name !== undefined;
  if (!isOkf) {
    return `${effectiveBody.trim()}\n`;
  }

  // Key order mirrors reference_agent's _PREFERRED_KEY_ORDER so a round trip is
  // byte-stable against agent-authored files (Measurement C).
  // The `descriptions` aspect is where Track A's table description lives; on an
  // ingested entry `entry_source.description` is platform-owned and comes back
  // null, so without this the description is silently dropped on every pull.
  const descKey = Object.keys(aspects).find(
    (k) => k === 'descriptions' || k.endsWith('.descriptions'),
  );
  const aspectDescription = descKey ? aspects[descKey]?.description : undefined;

  const clean: any = {};
  if (okf.okf_type !== undefined) clean.type = okf.okf_type;
  // Dataplex returns a BigQuery resource in its bare form
  // (`projects/P/datasets/D/tables/T`); the bundle writes the REST URL form.
  // Same resource, two notations — normalise so the round trip is an inverse
  // rather than a rewrite.
  if (ce.resource?.name !== undefined) clean.resource = toBigQueryResourceUrl(ce.resource.name);
  // Prefer what the bundle wrote (the okf aspect) over what the platform
  // returns (`meta.title` is `entry_source.displayName`, i.e. the native name).
  const title = okf.title ?? meta.title;
  if (title !== undefined) clean.title = title;
  // OURS WINS. `meta.description` is `entry_source.description`, which the
  // platform populates on some entries — the BigQuery *dataset* carries its own
  // description, so preferring it silently replaced the bundle's text with
  // BigQuery's on every pull. The `descriptions` aspect is the copy we wrote.
  const description = aspectDescription ?? meta.description;
  if (description !== undefined) clean.description = description;
  const tags = okf.tags ?? meta.tags;
  if (tags !== undefined) clean.tags = tags;
  if (okf.status !== undefined) clean.status = okf.status;
  if (okf.generated !== undefined) clean.generated = pick(okf.generated, ['by', 'at']);
  if (okf.verified !== undefined) {
    clean.verified = (okf.verified as any[]).map((v) => pick(v, ['by', 'at']));
  }
  if (okf.stale_after !== undefined) clean.stale_after = okf.stale_after;
  if (okf.sources !== undefined) {
    clean.sources = (okf.sources as any[]).map((s) => pick(s, ['id', 'resource', 'title']));
  }
  return render(clean, effectiveBody);
}
