# OKF ⇄ Knowledge Catalog — design as built

What exists, why it is shaped this way, and what was wrong with the tooling
underneath. Every "measured" claim has evidence in `MEASUREMENTS.md`.
`PROPOSAL.md` holds the forward plan; this describes the delivered system.

---

## 1. The model

```
spec.yaml ──> gen_okf.py ─────> okf-bundle/references/**   (44 concepts)
          └─> reference_agent ─> okf-bundle/tables|datasets/** (14 concepts)
                                        │
                                        ├── Track A ──> the 14 ingested @bigquery entries
                                        └── Track B ──> okf_cymbal_v6z (44 generic entries)
                                                   └──> `related` links joining the two
```

**The bundle is the source of truth. The catalog is a projection.** Git holds
the bundle; a push makes the catalog match it.

### 1.1 Which track a concept goes to

A concept with a top-level `resource:` names an asset Dataplex has already
ingested, so it belongs **on** that entry. Everything else needs an entry of its
own. That one rule is the whole split, and it is what stopped the catalog
showing two objects per table — a search went from **28 hits to 14**.

### 1.2 Concept types

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

### 1.3 What gets projected onto an ingested entry

| aspect | content | ownership |
|---|---|---|
| `okf` (custom) | the v0.2 signal layer + `title`/`tags` | always ours — no scan touches a custom type |
| `overview` | the concept body | always ours — the scan does not write it, and the aspect type has no `userManaged` field |
| `descriptions` | table description + 68 column descriptions | **contested** — `userManaged = verified` |
| `queries` | 40 query patterns | **contested** — `userManaged = verified` |

**`userManaged` is stored nowhere.** Not in the bundle, not in config — it is
computed from `verified` at push time, because it is a Knowledge-Catalog-specific
projection policy and KC is one target among possible others. Contested aspects
are *always* written with the computed flag, so writing `false` **is** the
release; there is no separate release path.

`title` and `tags` ride on the `okf` aspect because on an ingested entry
`entry_source` is platform-owned — measured, `displayName` stays the native
`accounts` and `labels` stays null no matter what is pushed. Without that they
could not survive a pull.

### 1.4 Discovery

`related` EntryLinks join each table entry to its Join / Metric / Grain Rule
concepts — **58 links**, reconciled declaratively by `link-concepts.ts`.

Chosen after testing all three link types:

| link | target | readable |
|---|---|---|
| **`related`** | any entry, **undirected** (both refs `UNSPECIFIED`) | via `lookupEntryLinks` — **chosen** |
| `definition` | **glossary term only**; a generic entry is refused | via `lookup_context`, inline on the column |
| `schema-join` | table ↔ table | scan-owned, and v7 measured it unconsumed as a join hint |

Reach differs by consumer, and this is the part most easily got wrong:

| channel | prebuilt dataplex MCP toolbox | custom ADK agent |
|---|---|---|
| `overview` / `descriptions` / `queries` | only at `view=ALL` | yes |
| `related` links | **no link tool among its 24** | **yes** — `lookupEntryLinks` |

A custom ADK agent therefore needs: a `lookupEntryLinks` tool, `view=ALL` forced
via `before_tool_callback` (the default `FULL` returns non-required aspects as
*keys only* — 3,619 chars vs 13,302), and a preference for `lookup_context`.

---

## 1.5 Direction of authority — why this is not kcmd's model

kcmd is built for the **opposite direction**, and the difference is not stylistic.

| | remote-authoritative (kcmd's `OkfLayout`) | local-authoritative (this project) |
|---|---|---|
| system of record | Dataplex | the bundle, in git |
| the files are | a working copy | the source |
| fidelity by | **stashing** the entry in `x-kcmd` | **mapping** each field to a catalog construct |
| primary verb | `pull` | `push` |
| the other verb | replays the working copy | should be a **diff** |

`OkfLayout`'s own header concedes the direction: it stashes the full `md.Entry`
under `x-kcmd` so *Dataplex entries* round-trip losslessly, and notes that
hand-authored OKF "still load, **lossily**".

**Measured what it would do to our source.** Running `OkfLayout.saveEntry` with a
concept as it comes back from the catalog writes a file containing:

```yaml
type: dataplex-types.global.generic     # OVERWRITES the OKF type `BigQuery Table`
x-kcmd:                                  # a full copy of the catalog entry
  aspects:
    royston-dev-8253.us.okf:
      verified: [{by: 'human:x'}]        # `verified` DEMOTED into the stash
```

Three inversions in one file: the source's own vocabulary is replaced by the
platform's, the catalog's state is embedded in the source, and a first-class OKF
trust field becomes an implementation detail of the stash. For a
bundle-authoritative project that is corruption, not round-tripping. It is also
exactly right for kcmd's intended use case — this is a direction mismatch, not a
bug.

### The four rules that follow

1. **No stash, either way.** Nothing catalog-shaped hidden in the bundle,
   nothing bundle-shaped hidden in the catalog. Our `okf` aspect is not a stash:
   it is a declared schema with named, individually queryable fields.
2. **Push is total and declarative.** Owned aspects are fully replaced,
   ownership is computed from `verified`, links are reconciled with stale
   removal. Push twice changes nothing — verified.
3. **Pull is a DIFF, not a source.** This is the reframe that matters. We spent
   effort making pull *reconstruct* the bundle, which is the remote-authoritative
   instinct. Its real job here is drift detection: *does the catalog still match
   the bundle, and where not?* The success criterion is "no false drift", not
   "byte-faithful reconstruction" — and it removes the temptation to build an
   edit-in-the-UI-then-pull workflow, which would reinstate two sources of truth.
4. **The source keeps its own vocabulary.** `type: BigQuery Table` must survive a
   round trip; the Dataplex entry type is a *derived* value, never a replacement.

Rules 1, 2 and 4 are implemented. Rule 3 is satisfied in practice — Track A
round-trips 14/14 and Track B diffs `changed=0`, so drift *would* be visible —
but the code is still shaped as a reconstructor rather than a differ.

### The upstream shape

What kcmd would need is not another layout but a declared **direction**: a
manifest-level `authority: local | remote`. Under `local` it would never write
`x-kcmd`, never overwrite the source's `type`, treat pull as read-only diff, and
require an explicit mapping for the OKF signal families instead of dropping
them. Under `remote`, today's behaviour is correct and should stay.

---

## 2. kcmd defects found and fixed

`kcmd/src/` was pristine; all six were first worked around in `demo/okf/` and
are now fixed at source, so the patches are upstreamable. **The shim workarounds
were kept** — harmless against a patched fork, necessary against an unpatched one.

| # | defect | fix | verified by |
|---|---|---|---|
| 1 | `DocumentsLayout.init()` indexed on `entry.name`, which `parseMarkdown` never sets — files were skipped **silently** and `push` reported success over an empty index | fall back to a path-derived id, as `OkfLayout.deriveEntryName` already does | the raw bundle now indexes **53 where it indexed 0** |
| 2 | the pull path aliases `…global.overview` → `overview`; both layouts read only the long key, so pull returned **every concept with an empty body** | `overviewKeyOf()` accepts both forms, in `documents.ts` and `okf.ts` | a short-key aspect is promoted into the body |
| 3 | `--validate-only` was accepted, plumbed through `main.ts`, and **never read** — it created every entry it "validated" | `skipWrites = dryRun \|\| validateOnly` across all 9 write guards in `push()` | a probe concept **was not created** |
| 4 | EntryLink reconciliation ran **unguarded**; with no `entryLinks` declared the lookup is unfiltered, so every link the bundle did not describe was deleted | return early when the manifest declares no link types | the config that destroyed 12 `schema-join` links now leaves **24 + 58 intact** |
| 5 | `package.json` `exports` pointed at `./build/ts/kcmd/index.js`, which this fork does not build | repointed at `./build/ts/tool/libts/index.js` | — |
| 6 | `lookupEntryLinks` returned only the **first page**, though its own response type declares `nextPageToken` | follow pagination inside the client | link reconciliation went from HTTP 409 crashes to **0 created / 58 correct** |

**Defect 1 is the one to lead with upstream:** an unmodified kcmd cannot consume
a clean OKF bundle at all, and says *"Successfully pushed catalog entries"*
while doing nothing.

### 2.1 The pattern worth naming

Five of the six fail **silently and plausibly**. A push that wrote nothing, a
pull that returned nothing, a validate-only that wrote everything, a
reconciliation that deleted a scan's entire relationship layer, a paginated
lookup that saw a third of the data — each reported success. Not one threw.

That is why nearly every check in this repo counts something.

## 3. Our own shim defects (also fixed)

Fair is fair — these were ours, not kcmd's:

- `toStaging` omitted `catalogEntry.name` (defect 1 is why it failed silently)
- `fromStaging` dropped `description` and `tags`, and mangled `title`/`resource`
- the entry type was hardcoded `bigquery-table`, correct only because this
  dataset holds 13 `BASE TABLE`s
- `schemaFields` blacklisted any column literally called `name`, which silently
  ate two real columns and made the bundle look incomplete
- `getEntry`'s aspect filter was passed the dotted alias, which 400s — and an
  empty aspect map on a failed response reads as "nothing there"

---

## 4. Verification

Everything below is re-runnable.

```bash
python okf-review/conformance.py                    # OKF v0.2 §11 + §5 + §6.1
python okf-review/canonicalize.py --check okf-bundle
python okf-review/canonicalize.py --selftest
kcmd/node_modules/.bin/bun kcmd/demo/okf/ownership.test.ts
```

Current state:

```
OKF v0.2 conformance      CONFORMANT — 0 failures, 0 warnings (58 concepts, 9 index files)
canonical formatting      0 files non-canonical, idempotent
offline suite             26 passed
SQL in the bundle         53/53 blocks dry-run clean against BigQuery
columns                   68/68 real, 0 invented
Track A round trip        14/14 faithful (frontmatter + body)
Track B round trip        changed=0
push idempotence          0 created, 58 already correct, 0 stale removed
catalog links             24 schema-join (untouched) + 58 related (ours)
```

### 4.1 Operational notes

- **`build/` is gitignored.** A fresh clone must `npm run build:mcp` in `kcmd/`
  before push or pull will work, now that `src/` is patched.
- **Set `KCMD_ACCESS_TOKEN` explicitly.** Otherwise the CLI mints a token from
  the *globally active* gcloud config, which is not necessarily the identity you
  intend. `push-track-a.ts` refuses to run without it.
- **Do not declare `entryLinks:` in the manifests.** With defect 4 fixed,
  omitting it means kcmd leaves links alone and `link-concepts.ts` owns them.
  Declaring it makes every push delete and immediately recreate all 58.
- **Push from `okf-bundle/`, not from a pulled tree** — see the known gap below.

---

## 5. Known gaps

- **`pull` is faithful but the bundle is still effectively push-only in
  practice.** Track A round-trips 14/14 now, but the workflow has never been
  "edit in the UI, pull, commit". Treat git as the source and the catalog as
  output.
- **`Attested Computation` is not implemented.** §10 is the right end state —
  and 22 of 26 measures have no liftable standalone SQL, while the attester
  runs consumer-side where our harness runs none.
- **`log.md` absent; `stale_after` unused (0/58).** Both optional under §11.
- **The `verified` flag is doing two jobs.** It is both Phase 7's deliberately
  arbitrary control population and the authorisation signal gating catalog
  ownership. A control wants to be uncorrelated with merit; an authorisation
  wants the opposite.
- **Retrieval, not content, is the binding constraint.** Across 75 Arm-D runs
  score tracked the *lookup rate*, not the metadata: Arm K 11/15 with lookups on
  14/15, the D family 6–8/15 with 1–5/15. Three successive content improvements
  moved it by two points. Everything in §1 is necessary and none of it is
  sufficient.
