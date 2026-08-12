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
const SIGNAL_KEYS = ['okf_type', 'generated', 'sources', 'verified', 'status', 'stale_after'];

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
export function toStaging(content: string, okfKey: string): string {
  const { meta, body } = splitFrontmatter(content);
  if (!meta) {
    return content;
  }
  const staged = pick(meta, ['title', 'description', 'tags']);
  staged.catalogEntry = {
    resource: { name: meta.resource },
    aspects: {
      [okfKey]: pick(
        {
          okf_type: meta.type,
          generated: meta.generated,
          sources: meta.sources,
          verified: meta.verified,
          status: meta.status,
          stale_after: meta.stale_after,
        },
        SIGNAL_KEYS,
      ),
    },
  };
  return render(staged, body);
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

  // Directory index entries carry no OKF signal — emit body only, matching the
  // frontmatter-free index files in the source bundle.
  const isOkf = SIGNAL_KEYS.some((k) => okf[k] !== undefined)
    || ce.resource?.name !== undefined;
  if (!isOkf) {
    return `${body.trim()}\n`;
  }

  // Key order mirrors reference_agent's _PREFERRED_KEY_ORDER so a round trip is
  // byte-stable against agent-authored files (Measurement C).
  const clean: any = {};
  if (okf.okf_type !== undefined) clean.type = okf.okf_type;
  if (ce.resource?.name !== undefined) clean.resource = ce.resource.name;
  if (meta.title !== undefined) clean.title = meta.title;
  if (meta.description !== undefined) clean.description = meta.description;
  if (meta.tags !== undefined) clean.tags = meta.tags;
  if (okf.status !== undefined) clean.status = okf.status;
  if (okf.generated !== undefined) clean.generated = pick(okf.generated, ['by', 'at']);
  if (okf.verified !== undefined) {
    clean.verified = (okf.verified as any[]).map((v) => pick(v, ['by', 'at']));
  }
  if (okf.stale_after !== undefined) clean.stale_after = okf.stale_after;
  if (okf.sources !== undefined) {
    clean.sources = (okf.sources as any[]).map((s) => pick(s, ['id', 'resource', 'title']));
  }
  return render(clean, body);
}
