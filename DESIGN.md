# OKF ⇄ Knowledge Catalog — design as built

What exists, why it is shaped this way, and what was wrong with the tooling
underneath. Every "measured" claim has evidence in `MEASUREMENTS.md`; this file
cites it rather than restating it. `RESULTS.md` holds the conclusions,
`HANDOFF.md` the operational state, `ARCHITECTURE.md` the as-built diagrams
and the Phase 8 harness. There is no separate forward plan: `PROPOSAL.md` was
delivered in full and deleted, and what remains open is §12 below.

---

## 1. The model

```
spec.yaml ──> gen_okf.py ─────> okf-bundle/references/**   (44 concepts)
          └─> reference_agent ─> okf-bundle/tables|datasets/** (14 concepts)
                                        │
                          postauthor.py │ (absolute links, status,
                          canonicalize  │  `# Related concepts` back-links)
                          mirror.py     │ (the tier-A cache, from BigQuery)
                                        ▼
                                 okf-bundle/   ← git = the source of truth
```

**The bundle is the source of truth. The catalog is a projection.** Git holds
the bundle; a push makes the catalog match it.

### 1.1 `.staging/` is the interface

Every phase below is a consequence of this picture, so it is worth stating once.

```
okf-bundle/            clean OKF v0.2 · tool-agnostic · git = source of truth
    │                                                    ▲
    │  project: toOkfStaging()            refresh (tier A / C-at-false only)
    ▼                                                    │
.staging/bundle/       kcmd-native: OKF + x-kcmd · disposable · gitignored
    │  ▲                                                 │
    │  └── compare `expected` vs `actual` ── the planner ─┤
    │      (decides what to stage; also the drift report) │
    ▼                                                    │
  kcmd push (only what differs)                    getEntry(view=ALL)
    │                                                    ▲
    ▼                                                    │
Dataplex Knowledge Catalog
```

**kcmd never sees `okf-bundle/`.** It reads and writes only the staged tree.

- The **inner loop** (staging ↔ catalog) is kcmd's job and is lossless *by
  stash*. Making the staged tree kcmd-native is what buys that.
- The **outer loop** (bundle ↔ staging) is ours and is a *mapping*.
  Deliberately lossy on the return leg: we do not want the catalog's shape back.

The bundle staying **agnostic** is the payoff, not an aesthetic. It carries no
Dataplex vocabulary, so a second projector — LookML, a CA API `Context`, another
catalog — could consume the same bundle without disturbing the first.

Both directions use the same interface; **only the last hop differs.** Push's
last hop writes to the catalog. Pull's last hop writes a *report* for
owned-behaviour content and a *refresh* for cache-behaviour content — and which
is which is decided by the tiers in §3.

### 1.2 Which track a concept goes to

A concept with a top-level `resource:` names an asset Dataplex has already
ingested, so it belongs **on** that entry (Track A). Everything else needs an
entry of its own (Track B). That one rule is the whole split, and it is what
stopped the catalog showing two objects per table — a dataset-scoped search went
from **28 hits to 14**, and still returns 14 after the index entries landed.

`targets.ts` is the single derivation; the two push scripts and the differ all
use it. It existed three times before, and three copies of "which entry is this
concept" is three chances for the differ to compare against the wrong entry and
report a clean bill of health.

---

## 2. Concept types, and what each body actually contains

| type | n | source |
|---|---|---|
| `BigQuery Table` / `BigQuery Dataset` | 14 | `reference_agent` |
| `Metric` | 26 | `spec.layer2_semantics.measures` |
| `Join` | 13 | `relationships` + `bridges` |
| `Grain Rule` | 3 | `dedup`, `snapshots`, `accumulating` |
| `Hierarchy` | 1 | `hierarchies` |
| `Derived Table` | 1 | `unpivot` |

**58 concepts, and all 11 spec constructs represented.** `columns` stay as
`# Schema` rows on the table concept; `m2n` stays inside the bridge `Join`,
because the bridge already *is* that concept.

`Join`, `Grain Rule`, `Hierarchy` and `Derived Table` are **producer-defined**,
not OKF types. §4.1 is explicit that type values are not centrally registered
and consumers must tolerate unknown ones; §11 requires only that `type` be
present and non-empty.

**What earns a type of its own is addressability.** A rule that lives only as a
sentence inside another document cannot be retrieved, linked, verified or signed
off independently. `dedup`, `snapshots` and `accumulating` are each a
table-level correctness rule with its own lifecycle, so each became a `Grain
Rule`. `m2n` did not, because the bridge `Join` already *is* that concept.
`references/` as the home for them is **our convention** — OKF §6.3 describes
that directory as mirroring "external material, run instructions, or code" and
is explicit that it is "a naming convention, not a requirement", so our usage
violates nothing, but the spec does not endorse it either.

**`BigQuery Table`** (13) is the only type using `#` headings, and the only one
projecting into tier C:

- intro prose, then `### Grain and Batch Updates` and `### Key Relationships`
- **`# Related concepts`** — generated; see §5
- **`# Schema`** — `| Field | Type | Description |`, 68 rows. Feeds
  `descriptions.fields[]`
- **`# Data characteristics`** — generated; the mirror. See §3
- **`# Common query patterns`** — `### 1. …` with fenced SQL, feeding
  `queries[]`. All 53 blocks dry-run clean against BigQuery

**`Join`** (13), **`Grain Rule`** (3), **`Metric`** (26), **`Hierarchy`** (1),
**`Derived Table`** (1) have no `#` headings at all, and a consistent four-part
shape: a **bold lead line** stating the hazard, a **two-column key/value table**,
a **fenced SQL** block, and **blockquote warnings** carrying the cross-cutting
hazard. Having no `# Schema` or `# Common query patterns`, they project **only**
to `overview` — pure tier B, no contested surface at all. Which is why the 44
Track B concepts are wholly bundle-owned: there is nothing in them for a scan to
contest.

---

## 3. Three ownership tiers, and the switch between them

**The bundle covers everything the catalog captures**, so a bundle-only reader
stays on the agnostic path and never needs a catalog round trip. But the bundle
is **not merely a cache** — it holds authority over some of what it covers.

| | **A — platform-owned** | **B — bundle-owned** | **C — contested** |
|---|---|---|---|
| examples | `schema`, `storage`, `bigquery-*`, and BigQuery's own table/column descriptions | the `okf` aspect, `overview` (the concept body), `related` links, all 44 Track B concepts | the Dataplex `descriptions` aspect, `queries` |
| source of truth | **the warehouse/catalog** | **the bundle** | **whichever `userManaged` says** |
| pushed? | never | yes, total replace | yes, always, carrying the computed flag |
| pull refreshes the bundle? | **yes** — this is how the cache stays current | never | **only at `userManaged=false`** |
| in the forward diff? | no — report **stale cache** | yes — report **drift** | at `true` drift, at `false` stale cache |

**Tier C is not a third behaviour — it is a runtime switch between the other
two, thrown by `userManaged`.** Two behaviours, three content classes, no third
code path in the differ or the refresh. `tiers.ts` is the table; `drift.test.ts`
asserts the switch both ways.

| `userManaged` | tier C behaves as | because |
|---|---|---|
| `false` | **tier A** — cache; pull refreshes; report stale cache | the scan owns it and will overwrite |
| `true` | **tier B** — owned; diffed; pull never touches it | the scan will not overwrite |

Since we compute `userManaged = verified`, **sign-off is the switch**, and the
workflow that falls out is the human-in-the-loop enrichment loop kcmd's own spec
§1.1 describes: the scan drafts → the diff reports a stale cache → refresh →
review in git → certify → push → the bundle wins from then on.

**`userManaged` is stored nowhere.** Not in the bundle, not in config — it is
computed from `verified` at push time, because it is a Knowledge-Catalog-specific
projection policy and KC is one target among possible others.

### 3.1 Five surfaces are called "description"

Conflating any two of them has already cost us once.

| surface | what it holds | tier | written by |
|---|---|---|---|
| BigQuery `Table.description` | the warehouse's table description | **A** | DDL / warehouse owner |
| BigQuery column descriptions | the warehouse's column prose | **A** | DDL |
| Dataplex `entrySource.description` | ingestion's copy of the source description | **A** | ingestion; kcmd never sends it on ingested scopes |
| Dataplex `descriptions` aspect | the doc scan's table and column prose. We overwrite it with the OKF frontmatter `description` and the `# Schema` rows | **C** | the scan, or us when `userManaged` |
| Dataplex `overview` aspect | rich markdown: **the concept body** | **B** | only ever us. Measurement G found it **absent, not blank**, on all 14 entries before we wrote it |

So the concept body is **not** the BigQuery table description — unrelated
stores. It **is** the Dataplex entry overview. And the OKF frontmatter
`description` goes somewhere different again, into the tier-C `descriptions`
aspect, so **two OKF fields land in two Dataplex places under two ownership
rules**.

**The consequence, accepted deliberately.** The BQ CA API reads BigQuery's own
column descriptions and *not* the Dataplex aspect (the v7 finding). Declaring
BigQuery's descriptions tier A therefore means **the bundle has no reach into a
BQ CA agent** pointed at this dataset. Reaching it would need a `tables.patch`
writer and would make a **third writer**, against the two-path policy. Not doing
it — recorded so the limitation is a decision rather than a surprise. It costs
nothing measurable today: 0/68 columns and 13/14 tables carry any native
description at all.

### 3.2 The mirrored tier — what it is and is not

The rule is **distilled and authored, never mirrored**, and the test is
**authority**, not knowledge-versus-data. Column types and null rates are
plainly knowledge; OKF §4.2 makes `# Schema` a conventional heading for exactly
this. But `schema` and `storage` are authored by BigQuery, and kcmd correctly
*drops* them on push for ingested entries — a bundle field that can never be
pushed misrepresents what the bundle is. So they are **cached and never
pushed**, asserted offline for all 58 concepts.

`mirror.py` refreshes two things on the 13 table concepts:

- **`# Schema` Type and Mode**, merged **keyed on column name**. Description is
  ours and is not touched — 68/68 survived byte-identical, and `--selftest`
  asserts it offline. A new warehouse column is added and **flagged
  undocumented**; a vanished one is **flagged and kept**, not deleted.
- **`# Data characteristics`**, computed **from BigQuery** — null rate, distinct
  count, range, top values for low-cardinality strings.

Computed from BigQuery rather than from the `data-profile` aspect for two
reasons: the aspect **does not exist** on any of these entries, and the catalog's
profile is reproducible but not accurate (1,201 distinct `account_id` against an
actual 1,200 — RESULTS §1's burn was that number copied into prose unchecked).

`kc-capture/` keeps its distinct job: the *frozen, hash-manifested* input that
makes authoring runs reproducible. The mirror is *current*. Overlapping content,
different purpose.

---

## 4. What the emitter produces — source vs staged

`okf-bundle/tables/accounts.md` **(the source — no stash, ever)**:

```markdown
---
type: BigQuery Table
resource: https://bigquery.googleapis.com/v2/projects/…/tables/accounts
title: Accounts
description: Core table containing checking, savings, and credit accounts…
tags: [core, accounts, finance]
status: stable
generated: {by: reference_agent/gemini-3.5-flash, at: '2026-08-12T20:50:24+00:00'}
verified: [{by: human:kenly@google.com, at: '2026-08-13T00:00:00+00:00'}]
stale_after: '2026-11-13'
sources: [{id: bq-metadata, …}]
---

The `accounts` table stores…[^bq-metadata]
### Grain and Batch Updates / ### Key Relationships
# Related concepts   # Schema   # Data characteristics   # Common query patterns
```

`.staging/bundle/bigquery/<project>/<dataset>/accounts.md` **(generated)**:

```markdown
---
type: BigQuery Table                    ← UNCHANGED; not 3-part, so parseOkf
title: Accounts                            falls back to the STASHED type
description: Core table containing…     ← still a top-level OKF key
tags: [core, accounts, finance]
x-kcmd:                                 ← ADDED — a SIBLING of description
  name: bigquery/<project>/<dataset>/accounts
  type: dataplex-types.global.bigquery-table   ← read live by liveEntryInfo
  resource: {displayName, description, labels}
  aspects:
    dataplex-types.global.descriptions:
      userManaged: true                 ← computed from `verified`
      description: …                    ← COPIED from the frontmatter key
      fields: [...]                     ← DERIVED from the `# Schema` rows
    dataplex-types.global.queries:
      userManaged: true
      queries: [...]                    ← DERIVED from `# Common query patterns`
    <project>.us.okf:
      okf_type: BigQuery Table
      generated / verified / status / stale_after / sources
      title / tags                      ← must ride here; entrySource is dropped
---

The `accounts` table stores…            ← same body, verbatim
```

Three things this makes concrete:

- **`description` is never *inside* `x-kcmd` alone.** It is a top-level OKF key
  in both files and *also* inside the stash, because that is where the
  projection puts it. The value exists twice in the staged file and once in the
  source — which is exactly why the stash is generated, not committed.
- **Everything after the closing `---` is the concept body**, carried through
  verbatim; `OkfLayout._loadLayer` promotes it to `overview.content`. The stash
  therefore carries **no** `overview`, or the body would be pushed twice.
- **The body is read twice more on the way out**: `# Schema` →
  `descriptions.fields`, `# Common query patterns` → `queries`. One markdown
  section lands in two Dataplex aspects under two ownership tiers.

### 4.1 `title` and `tags` ride on the `okf` aspect

Measured: on an ingested entry `displayName` stays the native `accounts` and
`labels`/`description` stay absent no matter what is pushed, so without this
they could not survive a round trip.

**The explanation used to be wrong, and the correction matters.** It is not that
`entry_source` is platform-owned and Dataplex refuses the write. It is that
**kcmd never makes the write**: `toServiceEntry` early-returns
`{name, entryType, aspects}` when `source.ingestedEntries`, so displayName,
description, labels, resource and both timestamps are dropped **client-side**.
The fix is still right — it is the only thing that survives an unmodified kcmd —
but the cause is a fixable client behaviour, not a platform constraint.

---

## 5. Discovery — and the one measured agent failure this fixes

Phase 8's q4: the answer sat in `metrics/accounts__avg_txns_per_account`,
curated, correct, one lookup away, and the agent fetched the `accounts` table
concept on all three reps and never found it.

> *The ceiling is not what someone curated — it is what is reachable from where
> the agent starts.*

**One derivation, three renderings.** `bundle.ts::desiredRelatedLinks` reads the
reference concepts' own body links and produces `table → {concepts}`:

| rendering | direction | who reads it |
|---|---|---|
| the authored concept body links | concept → table | everyone; this is the source |
| **a generated `# Related concepts` section on each table concept** | **table → concepts** | **a bundle reader — Arm K** |
| **58 `related` EntryLinks** | undirected | a catalog reader with a link tool |

The back-links are **new information, not duplication**: OKF §6.1 treats links
as **directed**, so concept→table and table→concept are two distinct assertions.
Dataplex `related` is *undirected* and collapses the two into one, which means
the bundle carries strictly more structure than the catalog can express —
the opposite of the usual direction.

The `related` links closed the reachability hole on the **catalog** path. Arm K —
the arm that scored 11/15 — reads the bundle over MCP with no catalog access at
all, so for the winning arm the hole stayed open until the back-links landed.

The two derivations (TS for the links, Python for the sections) are duplicated
across languages, like `canonicalize.py` duplicating `reference_agent`'s key
order, and guarded the same way: `ownership.test.ts` compares the TS map against
the sections in the bundle, so a divergence fails offline instead of silently
halving the link layer.

**Link types, all tested:**

| link | target | readable |
|---|---|---|
| **`related`** | any entry, **undirected** (both refs `UNSPECIFIED`) | via `lookupEntryLinks` — **chosen** |
| `definition` | **glossary term only**; a generic entry is refused | via `lookup_context`, inline on the column |
| `schema-join` | table ↔ table | scan-owned, and v7 measured it unconsumed as a join hint |

Traversal from the table entry works — the link is undirected and
`lookupEntryLinks` returns links touching an entry from either end, which is how
reconciliation reports "0 created, 58 already correct" while querying the
`@bigquery` end. Reach differs by consumer:

| channel | prebuilt dataplex MCP toolbox | custom ADK agent | BQ CA API |
|---|---|---|---|
| `overview` / `descriptions` / `queries` | `lookup_context` yes; `lookup_entry` only at `view=ALL` | yes | **no** — CA reads BigQuery's own descriptions (§3.1) |
| `definition` → glossary term | yes | yes | **yes** |
| `related` → concept | **no link tool among its 24** | **yes** — `lookupEntryLinks` | no |

So a custom ADK agent needs three things, and the second is the one most easily
got wrong:

1. **A `lookupEntryLinks` function tool** — the traversal the toolbox lacks.
2. **Force `view=ALL` on `lookup_entry`.** Its default `FULL` returns
   non-required aspects as *keys only*, so `overview`, `descriptions` and
   `queries` are all withheld — measured 4,064 chars against 17,080 on the same
   entry. A `before_tool_callback` is deterministic where a prompt instruction
   is not.
3. **Prefer `lookup_context`** — the one call that returns the whole projection
   resolved, glossary terms included.

---

## 6. Redundancy — a cost and a feature, and they look alike

**Projection redundancy is a cost.** `assetAspects()` reads the body to extract
`descriptions.fields` and `queries`, and removes nothing, so a catalog reader at
`view=ALL` receives the schema twice and the query patterns twice.

```
13 table-concept bodies            67,567 chars
  # Common query patterns          22,071  32.7%   overview AND queries[]
  intro / grain / key relationships 16,009  23.7%   overview only
  # Related concepts               11,797  17.5%   overview only
  # Schema                          9,178  13.6%   overview AND descriptions.fields
  # Data characteristics            8,525  12.6%   overview only
                                   ────────────
  duplicated                       31,249  46.2%   (was 66% before §3.2 and §5)
```

**Decision: keep it.** RESULTS §4 found retrieval is the binding constraint —
the agent does not ask in 24 of 30 attempts on the questions that need it. When
it does ask, one aspect holding the whole coherent document beats three
fragments it must reassemble, and the UI needs the structured forms regardless.
Stripping the two sections would leave `overview` a stub — a worse document for
the only consumer that reads documents. **If agent context ever becomes the
binding constraint, this is the first lever to pull.**

**A bundle reader does not pay this at all.** The file holds the body once; the
duplication is manufactured by the projection, because Dataplex wants prose in
`overview` and structure in `descriptions`/`queries`.

**Authoring redundancy is the opposite, and deliberate.** 12 of 57 concepts
mention the de-duplication hazard; the exact blockquote appears verbatim 4×. An
agent retrieves *one concept*, not the bundle, so a cross-cutting hazard must
appear in every concept it affects or it is only found by landing on the right
document.

| | same content in… | readers | verdict |
|---|---|---|---|
| **projection redundancy** | two *shapes*, one entry | **one** reader sees both | a cost |
| **authoring redundancy** | one shape, many *entries* | each reader sees one | a feature |

---

## 7. Identity and freshness

The bundle carries **no content-derived identifier** — no `id`, `hash`, `sha`,
`checksum` or `version` key anywhere. **Identity is the file path**, which is
also what becomes the Dataplex entry id.

**What OKF recommends for freshness is nothing computed.** SPEC.md has zero
occurrences of hash / checksum / etag / fingerprint / revision / commit, and
content addressing is not even in §12's "Considered and deferred". The specified
signals are all *declared*: `generated.at` (§5.2), `verified[].at` (§5.2),
`status` (§5.4), `stale_after` (§5.5), `log.md` (§9), `okf_version` (§12).
Versioning is delegated to git by design — §1: *"no required tooling… if you can
`git clone` a repo, you can ship it"*.

State: `status` **58/58**; `generated.at` 58/58 and **content-accurate**;
`verified[].at` 34/58; `stale_after` **13/58** (the 13 mirrored table concepts,
its first defensible use); `log.md` present.

**`generated.at` is content-accurate**, which is stronger than deterministic and
is what §5.2 asks for: "the content's last meaningful change". It used to be a
batch run stamp — 39 of 44 shared one value — so equal timestamps did not imply
equal content and a body edit did not move one. `merge_with_existing` renders,
compares against disk, and carries the old timestamp forward when nothing
meaningful changed. "Meaningful" excludes `generated.at` itself, YAML serializer
style (both sides are compared as parsed structures) and markdown link **form**.
Re-emission moves 0 of 44; a one-line spec edit moves exactly 1.

**A content hash on the `okf` aspect: considered and declined**, and the reason
is stronger than "not needed yet" — **Dataplex already stamps everything.**

### 7.1 The catalog's four native timestamp tiers

| timestamp | means | reached the bundle? |
|---|---|---|
| `Entry.createTime` / `updateTime` | when the **catalog record** changed | **now yes** — was declared in kcmd's type and dropped by `toLocalEntry` |
| `Entry.entrySource.*` | the **source system's** times | yes — the only one kcmd ever kept |
| `Aspect.createTime` / `updateTime` | when **that aspect** changed — the per-channel signal | **now yes** — was dropped TWICE (defect 7) |
| `EntryLink.createTime` / `updateTime` | when the link changed | not used; still absent from kcmd's interface |

Plus `Aspect.aspectSource.{createTime, updateTime, dataVersion}`, which the plan
had not enumerated: populated **only** on the five ingestion-authored aspects
(all `dataVersion: Ingestion/1.0.0`) and empty on the four we or the scan write.
So it is a **provenance marker for tier A**, not merely another clock. And the
DATA_DOCUMENTATION scan writes `job` and `run_time` *into* the
`descriptions`/`queries` payload — already read by `okf-review/measure_g.py`.

### 7.2 The one we cannot write is the one that is trustworthy

`toServiceEntry` builds `{name, entryType, parentEntry, entrySource, aspects}`.
It sets **no** top-level `createTime`/`updateTime` and sends aspects as
`{aspectType, data}` only, so kcmd never attempts to write either. Dataplex
generates them. The one timestamp we *can* set — `entrySource.updateTime` — is
client-supplied and therefore worthless as evidence, and it is the only one kcmd
kept.

**And Dataplex's per-aspect `updateTime` is content-addressed.** Measured: 14
`modifyEntry` calls carrying byte-identical aspect data moved the entry-level
`updateTime` on all 14 and the aspect-level `updateTime` on **0 of 241**. So a
moved aspect timestamp means that aspect's *content* changed, not merely that
something wrote to the entry.

That is what makes multi-writer detection exact, and it is why there is no hash:
the server is the authority on "did this change", and there is no digest of ours
that can be wrong or stale.

---

## 8. The differ — drift vs stale cache

`drift.ts` compares **forward**, in the catalog's shape:

```
expected = buildStagedEntry(okf-bundle/<concept>)   the object push sends
actual   = CatalogClient.getEntry(<entry>, view=ALL)
compare aspect by aspect
```

`expected` is not a model of what the bundle claims about the catalog — it **is**
what the bundle claims, because it is the same value. A reverse mapping is lossy,
and a reverse-mapped diff is blind to exactly the fields the reverse mapping does
not know about. Two consequences fall out: the Measurement F false-drift class
disappears (parsed structures, not text), and the differ depends on **none** of
the kcmd defects — in particular not defect 2, because it never uses `kcmd pull`.

Normalisation is only this much: aspect keys come back qualified by project
**number** where we wrote project **id**, so tiers are keyed on the aspect id;
and JSON key order, handled by comparing key-sorted serialisations.

**Drift is reported per channel, because each has a different owner and remedy:**

| channel | drift means |
|---|---|
| `okf` aspect fields | the signal layer was edited in the catalog, or a push landed partially |
| `overview` | UI edit, or the body never landed |
| `descriptions` / `queries` | **a scan overwrote us** — only reachable at `userManaged=false` |
| `userManaged` vs `verified` | the ownership invariant broke; policy and catalog disagree |
| `related` links | link layer damaged |
| **orphan entries** | an entry exists in the EntryGroup the bundle does not declare |

### 8.1 "Stale cache" vs "drift" — same observation, opposite meaning

| | **drift** | **stale cache** |
|---|---|---|
| applies to | owned-behaviour content — tier B, and tier C at `userManaged=true` | cache-behaviour content — tier A, and tier C at `userManaged=false` |
| means | the catalog no longer matches what the bundle **asserts** | the bundle no longer matches what the catalog **holds** |
| is it a fault? | **yes** | **no** — routine and expected |
| remedy | re-push, and find out who wrote it | refresh, review the diff, commit |

Worked: BigQuery gains a column → **stale cache**, refresh. The doc scan rewrites
`descriptions` on an **unverified** concept → **stale cache**, the system
working. The same scan rewrites it on a **verified** concept → **drift**, and
specifically an ownership failure. Someone edits `overview` in the UI → **drift**.

**Why it earns its keep:** conflate them and every scan run and every warehouse
change shows up red, people stop reading the report, and a genuine ownership
failure is ignored along with the noise. A healthy system shows stale caches
routinely.

> **Current state: only one case is live.** All 14 asset-backed concepts are
> verified, so `userManaged=true` everywhere that matters and the scan is
> already locked out. The switch still has to exist: a newly-added table arrives
> unverified, flags can be revoked, and `references` is 20/44 verified — flags
> that are inert for ownership today but unearned.
>
> **"Just set `userManaged=true` everywhere" is rejected on policy, not
> capability.** Claiming a contested aspect unconditionally means writing
> unreviewed LLM output into the field a human reads and then freezing it
> against every future scan; the scan's version at least gets refreshed, a
> frozen guess does not. Freezing is a maintenance commitment; take it only
> where someone vouched.

Exit codes: **0 = no drift** (stale caches are listed and do not fail),
**1 = drift**, **2 = tool error**. `--strict` makes stale caches fail for a CI
refresh gate.

### 8.2 The differ is also the push planner

`drift` is the planner with the apply step omitted; `push` is the planner
followed by it. They cannot disagree about what a difference is because they are
the same function. Three things fall out, none needing a kcmd patch: we control
`.staging/`, so "skip the unchanged" is just not staging them; the read is
already paid for (`sync.ts:297` issues a `lookupEntry` per entry and discards
it); and it satisfies both `sync.ts` TODOs and kcmd spec §3.3 from outside the
tool.

**Fail-fast, against server truth.** A concept that differs because *the bundle*
was edited is not a conflict — the catalog has not moved, so its aspect
timestamps still match `_state/last_push.json`. One that differs because
*something else* wrote is, and the push **aborts entirely** rather than landing a
partial projection. `--force` overrides. That flag is declared at `sync.ts:227`
and read nowhere; here it is read, on our side of the boundary. This is §3.3's
fail-fast without the `.catalog.state` file §3.7 proposes.

**The risk this introduces, named because it is the repo's signature failure.** A
false no-change verdict silently drops a real change. So the comparison is
**conservative — any uncertainty pushes**: a read failure, an absent entry, an
unrecognised shape and an unparsed concept all stage. `OKF_NO_PLAN=1` disables
planning entirely. Tested on one string three levels deep
(`descriptions.fields[2].description`): exactly one concept staged.

**What it deliberately cannot do: write to `okf-bundle/`.** No flag, no escape
hatch. The remedy for drift is always *fix the bundle and re-push* — also the
remedy shown to work, since all four historical projection breakages recovered
that way. `pull.ts` is **deleted**; that removes the last code path that could
write into the bundle, which is what makes rule 3 structural rather than a
convention. HANDOFF §2.7 has the scratch-pull recipe for inspecting a raw pull
by hand.

### 8.3 The multi-writer assumption

Policy is that exactly two writers touch the catalog: our push, and the Dataplex
scans. That is enforced by process, not by the platform — and because the server
timestamps are unforgeable, a violation is **visible rather than silent**. The
differ reports a third-party write as *unexplained*: newer than our recorded
push, and not a scan.

---

## 9. Direction of authority — kcmd's stated intent vs its implementation

**kcmd's stated intent is the same as ours.** `kcmd/docs/concept.md`, Tenets —
verbatim in GoogleCloudPlatform/knowledge-catalog @ 374e0bc, so it is the product
team's own words, inherited unmodified by the fork:

> *Enable bi-directional sync with Knowledge Catalog and metadata fidelity. The
> code artifacts should be amenable to **serving as authoring and management
> source of truth**. They should enable a user to **fully inspect and author
> metadata that exists in the Catalog service**.*

`spec.md` goes further: §3.3 specifies conflict handling ("**fail fast** if…
modified in the catalog in the interim", abort, report, require a pull, with a
force override), §3.7 a `.catalog.state` checksum file, §3.8 deletion intent.

**None of it is implemented.** `grep -ri "checksum\|catalog.state\|etag"` over
`kcmd/src` returns **0**. Two conflict TODOs (`sync.ts:98`, `sync.ts:295`).
`force` is plumbed from `main.ts:141` into the options type at `sync.ts:227` and
**read nowhere** — the same accepted-plumbed-unread family as `--validate-only`
(defect 3) and the top-level `entryLinkTypes` (declared in the manifest schema,
consumed by nothing).

**So kcmd is not remote-authoritative *by design*. It is remote-authoritative
because the version-control half of its own spec was never built.** The previous
version of this section framed the difference as a direction mismatch between
two legitimate designs. That was wrong, and it mattered: it made the gap look
like a philosophical difference to be worked around rather than a missing layer
to be built.

### 9.1 `x-kcmd` is a substitute for that missing layer, and a latent state layer

It stashes the whole `md.Entry` so a pull can be replayed. Its real job is the
tenet's *second* clause — without it a pulled `.md` shows a title, a description,
tags and a body, and every other aspect is invisible.

**And it tracks no sync state — not via `x-kcmd`, not via anything.** On push,
`sync.ts:297` calls `lookupEntry` and uses the result *only* as an existence
test; the live remote entry it just fetched is discarded without comparison. On
pull, `_storeResource` overwrites unconditionally. EntryLinks are the sole
exception.

The irony worth recording: **`x-kcmd` already *is* a per-entry last-known-remote
snapshot** — the same information `.catalog.state` would hold, sitting inline in
every file. Comparing it against the live entry before writing would deliver
§3.3 with no state file at all. It is a latent state layer that nothing reads,
and a second, independent route to the guarantee §8 gets from the bundle side.

### 9.2 What a pull would do to our source — measured, not hypothesised

A pristine `kcmd pull` of our own concepts returns:

```yaml
type: dataplex-types.global.generic     # OVERWRITES the OKF type `Join`
x-kcmd:
  name: okf_interop_scratch/royston-dev-8253/us/references/joins/accounts__transactions
  aspects:
    royston-dev-8253.us.okf:
      okf_type: Join                    # the source's vocabulary, DEMOTED
```

…with an **empty body** (44 of 54 concepts, defect 2) and the entry renamed into
the KB source's `<group>/<project>/<location>/<path>` form. Three inversions in
one file: the platform's vocabulary replaces the source's, the catalog's state is
embedded in the source, and a first-class OKF trust field becomes an
implementation detail of the stash.

### 9.3 The four rules, restated

1. **No stash in the SOURCE; the stash is a build artifact.** The old wording
   was "no stash, either way", and it was overclaimed: `toStaging` always wrote
   a full Dataplex entry into `catalogEntry:`, and kcmd's own comment at
   `documents.ts:148` calls that *"the stashed `catalogEntry`"*. We never
   escaped the stash — we kept it out of git. The difference that matters is
   **derived vs committed**, and `ownership.test.ts` now asserts it.
2. **Push is total and declarative.** Owned aspects are fully replaced,
   ownership is computed from `verified`, links are reconciled with stale
   removal. Push twice now changes **nothing at all** — 0 staged, 0
   `modifyEntry`, 0 timestamps moved.
3. **Pull is a diff for OWNED content and a refresh for MIRRORED content, and
   it never writes an owned field.** The original "pull is a diff, not a source"
   was too broad: the two-sources-of-truth danger is specific to authored
   content; for mirrored content there is only ever one source, the platform.
   **Implemented, and structural** — the write path is deleted.
4. **The source keeps its own vocabulary.** `type: BigQuery Table` survives a
   round trip; the Dataplex entry type is a *derived* value carried in the
   stash, never a replacement.

### 9.4 The upstream shape

Not another layout but a declared **direction**: a manifest-level
`authority: local | remote`. Under `local` kcmd would never write `x-kcmd` over
a hand-authored file, never overwrite the source's `type`, treat pull as a
read-only diff, and require an explicit mapping for the OKF signal families
instead of dropping them. Under `remote`, today's behaviour is correct.

*Upstream target is Royston's fork only; no PR to Google's repo.* Note the limit
on the interop claim: **`OkfLayout` is fork-only**, absent from Google's repo, so
"an unmodified kcmd can consume this" means an unmodified *fork*.

---

## 10. kcmd defects — plain bugs vs symptoms of the missing layer

`kcmd/src/` was pristine; all eight are fixed at source and upstreamable. **The
shim workarounds were kept** — harmless against a patched fork, necessary
against an unpatched one.

| # | defect | kind | fires on the OKF path? |
|---|---|---|---|
| 1 | `DocumentsLayout.init()` indexed on `entry.name`, which `parseMarkdown` never sets — files skipped **silently** while `push` reported success | plain bug; **breaks kcmd's own primary verb** | **no** — `OkfLayout` has its own `deriveEntryName`; 68/68 files index |
| 2 | the pull path aliases `…global.overview` → `overview`; both layouts read only the long key, so pull returned **every concept with an empty body** | plain bug | **yes, totally** — 44 of 54 concepts came back empty |
| 3 | `--validate-only` accepted, plumbed, **never read** — it created every entry it "validated" | plain bug | **yes** — deleted entry, ran it, entry was back |
| 4 | EntryLink reconciliation ran **unguarded**; undeclared `entryLinks` makes the lookup unfiltered, so every link the bundle did not describe was deleted | plain bug | **yes** — one pristine push deleted the probe link |
| 5 | `package.json` `exports` pointed at a path this fork does not build | plain bug | n/a |
| 6 | `lookupEntryLinks` returned only the **first page**, though its own response type declares `nextPageToken` | plain bug | **reachable at TEN links** — 2 of 13 table entries already cross it |
| 7 | `_fixEntry` rebuilt every aspect as `{aspectType, data}`, discarding `createTime`, `updateTime` and `aspectSource`; the `Aspect` interface declared none of them | **direction mismatch** — the version-control layer's evidence, thrown away | it made the differ's fast path impossible |
| 8 | `getEntry` could express `BASIC` and `CUSTOM` and had **no way to ask for `ALL`** | **direction mismatch** — a capability the client cannot express | foreign-aspect detection is impossible without it |

Defects 1 and 4 are **unreachable from kcmd's own workflow** and only bite a
hand-authored bundle; 2, 3, 5, 6 bite anyone. 7 and 8 are the two that are not
bugs so much as consequences of §9: a tool that never intended to compare has no
reason to keep the evidence for comparison, or to be able to see an aspect it
did not expect.

### 10.1 The pattern worth naming

Five of the first six fail **silently and plausibly**. A push that wrote
nothing, a pull that returned nothing, a validate-only that wrote everything, a
reconciliation that deleted a scan's entire relationship layer, a paginated
lookup that saw a third of the data — each reported success. Not one threw.

That is why nearly every check in this repo counts something. It is also not a
solved problem: while writing up defect 6 this session, the first version of
`count_links.py` **did not paginate either**, and reported 47 links where there
are 58.

### 10.2 Our own shim defects (also fixed)

- `toStaging` omitted `catalogEntry.name` (defect 1 is why it failed silently)
- `fromStaging` dropped `description` and `tags`, and mangled `title`/`resource`
- the entry type was hardcoded `bigquery-table`, correct only by luck
- `schemaFields` blacklisted any column literally called `name`
- `getEntry`'s aspect filter was passed the dotted alias, which 400s
- **`gen_okf.py` deleted `verified` on every run** — it emitted seven
  frontmatter keys and wrote the file wholesale, so a plain re-emission silently
  removed the human sign-off from 20 concepts. Latent for two days; found only
  because the content-accurate timestamp work started comparing against disk.

---

## 11. Verification

```bash
# offline — no GCP, no credentials
python okf-review/conformance.py                 # CONFORMANT, 58 concepts, 9 index files
python okf-review/canonicalize.py --check okf-bundle
python okf-review/canonicalize.py --selftest
python okf-review/postauthor.py --check
python okf-review/mirror.py --selftest
kcmd/node_modules/.bin/bun kcmd/demo/okf/ownership.test.ts   # 38 assertions
kcmd/node_modules/.bin/bun kcmd/demo/okf/drift.test.ts       # 27 assertions

# live — needs KCMD_ACCESS_TOKEN (see HANDOFF §2)
kcmd/node_modules/.bin/bun kcmd/demo/okf/drift.ts            # 0 = no drift
kcmd/node_modules/.bin/bun kcmd/demo/okf/drift.ts --sweep    # record the baseline
python okf-review/count_entrygroup.py okf_cymbal_v6z --expect-concepts 44 --expect-indexes 7
python okf-review/count_links.py
python okf-review/probe_entries.py
python okf-review/mirror.py --check
```

Current state:

```
OKF v0.2 conformance      CONFORMANT — 0 failures, 0 warnings (58 concepts, 9 index files)
cross-concept links       190 absolute (§6.1 recommended), 0 relative, 0 bare, all resolve
canonical formatting      0 non-canonical, idempotent
post-authored form        0 pending, idempotent
mirrored cache            0 stale, idempotent
offline suites            38 + 27 passed
SQL in the bundle         53/53 blocks dry-run clean against BigQuery
columns                   68/68 real, 0 invented; 68/68 descriptions survive a mirror refresh
status                    58/58 explicit;  stale_after 13/58 (the mirrored concepts)
generated.at              16 distinct values; re-emission moves 0
Track B entries           44 concepts + 7 synthetic index entries
Track A aspects           4 on 14/14;  userManaged == verified on 13/13
catalog links             24 schema-join (untouched) + 58 related (ours)
push idempotence          0 staged, 0 modifyEntry, 0 of 241 timestamps moved
drift                     58 concepts, 0 findings, exit 0
interop                   an UNMODIFIED kcmd pushed 44 concepts + 7 index entries
```

### 11.1 Operational notes

- **`build/` is gitignored.** A fresh clone must `npm run build:mcp` in `kcmd/`.
- **Set `KCMD_ACCESS_TOKEN` explicitly.** Otherwise the CLI mints a token from
  the *globally active* gcloud config. Both push scripts refuse without it, and
  `mirror.py` uses the same token so BigQuery is read as the same identity.
- **Do not declare `entryLinks:` in the manifests.** With defect 4 fixed,
  omitting it means the patched kcmd leaves links alone and `link-concepts.ts`
  owns them. But see the header of both manifests: against an **unmodified**
  kcmd, omitting it is *destructive*.
- **`_state/last_push.json` is tracked, deliberately.** A drift baseline that
  does not survive a clone cannot support the CI use it is for. The cost is a
  small diff on every push that changes anything.
- **Nothing pulls into `okf-bundle/`, and there is no longer any code that
  could.**
- **`drift.test.ts`'s fixtures are a cache and go stale.** They record a
  `view=ALL` response taken right after a clean push, so a bundle change makes
  the offline suite fail on `okf:drift` / `overview:drift` — which is the suite
  working, not a bug. Re-capture with
  `bun kcmd/demo/okf/drift.ts --capture-fixtures`, which **refuses** to run
  while anything differs, because capturing from a drifted catalog would bake
  the drift in as the expected answer and the suite would never fail again.

---

## 12. Known gaps

- **`Attested Computation` is not implemented, and deferring it is a decision.**
  §10.4 is explicit that `Metric` and `Attested Computation` are complementary
  rather than alternatives — a Metric holds the meaning and *links to* a
  computation carrying sanctioned SQL plus an attester. Two reasons to wait:
  **22 of 26 measures have no liftable standalone SQL** (only the 4 window/PoP
  measures emit executable `derived_table` blocks; the rest are measure
  expressions needing Looker's compiler and the explore join graph, so deriving
  standalone SQL is new work *and* a second definition free to drift), and **the
  attester runs consumer-side**, where our harness runs none, so it would be
  inert today. When it is built: one per measure, `runtime: bigquery`, linked
  from the `Metric`. Note §10.6 — `verified` and attestation are different
  guarantees and we have only the first.
- **The joins arm of Phase 7 was never run.** The original plan's arms 3 and 4 —
  "joins kept (`userManaged: true`) preserved" and "joins deleted, re-created by
  the generator" — remain untouched; nothing here has ever modified an entry
  link's contents. `okf-review/join_triage.yaml` holds the verdicts (11 keep, 1
  JT2 reject) written before the deletion that never happened.
- **The bundle has no reach into a BQ CA agent.** §3.1: that channel is
  BigQuery's own column descriptions, declared tier A, and writing them would
  make a third writer.
- **`stale_after` is 13/58.** The 44 reference concepts have no honest ageing
  date; inventing one is worse than omitting it.
- **The `verified` flag is doing two jobs.** It is both Phase 7's deliberately
  arbitrary control population and the authorisation signal gating catalog
  ownership. A control wants to be uncorrelated with merit; an authorisation
  wants the opposite. The Phase 6 test for the tier-C switch therefore needs a
  concept de-verified via a separate experiment-only marker, not by moving
  `verified`.
- **`EntryLink` timestamps are still dropped.** Defect 7 fixed `Aspect`; the
  `EntryLink` interface still declares neither, though the API returns both. Not
  needed yet — link reconciliation compares by id, not by time.
- **Multi-writer detection has not been exercised against a real scan run.** The
  mechanism is verified against a synthetic out-of-band edit and the tier-C
  switch is verified offline both ways, but a live DATA_DOCUMENTATION run has
  not been triggered since the differ landed.
- **Retrieval, not content, is the binding constraint.** Across 75 Arm-D runs
  score tracked the *lookup rate*, not the metadata: Arm K 11/15 with lookups on
  14/15, the D family 6–8/15 with 1–5/15. On the two questions only the catalog
  can settle, calling it gave **2 correct of 6 against 1 of 24 without**. Three
  successive content improvements — `overview`, then `descriptions`/`queries`,
  then forcing `view=ALL` — moved the D family by two points. **The bottleneck
  is that the agent does not ask**, so the tool surface has to make retrieval
  the path of least resistance. Everything above is necessary and none
  of it is sufficient. The `# Related concepts` back-links are the first change
  aimed squarely at reachability rather than content, and **their effect on the
  score is unmeasured** — no eval has been re-run since they landed.
