# Measurements — OKF/kcmd mechanism proof

Running log. Each entry records what was measured, the raw result, and what it
constrains. Final synthesis goes in `RESULTS.md`.

Environment: project `royston-dev-8253`, dataset `cymbal_bank_v6z_scaffold_demo_copy`
(13 tables, byte-copy of `lakehouse_dev_cymbal_bank_demo`, itself a copy of
`cymbal_bank_v6z_scaffold_005a_demo`). Branch `v6z-okf-projector`.

---

## Phase 1 — dataset copy

13/13 tables copied, every row count identical to source
(transactions 20000, payments 8000, balance_snapshots 7200, wire_transfers 3000,
loan_investors 2019, support_tickets 1500, accounts 1260, calendar 1096,
customer_segment_history 827, loan_applications 800, customers 500,
account_owners 1380, investors 40).

Dataplex auto-ingest of the new `@bigquery` entries was **immediate** — 14 entries
(13 tables + 1 dataset) present on the first poll, not the "several minutes" the
plan budgeted for.

## Phase 2 — rich KC capture

`capture_kc.py capture` over the copy: 13 DATA_PROFILE + 13 table-scope
DATA_DOCUMENTATION + 1 dataset-scope DATA_DOCUMENTATION. **0 scan failures.**
Frozen as `kc-v6z-scaffold-copy-rich-20260812-2e7ae708`
(digest sha256 `04681f02…`, content sha256 `2e7ae708…`, 29 files).

This is the **first `rich` snapshot** in a library that previously held only
`lean` — it is the first capture anywhere in the repo with `insights/` populated
(13 files: generated overview + column descriptions + suggested SQL per table).

### Measurement B — scan determinism (drift floor)

Fresh rich capture vs the frozen lean snapshot, on identical underlying data
(the copy is a byte-copy; any difference is pure scan non-determinism).

| Artifact | Result |
|---|---|
| **DATA_PROFILE statistics** | **136 / 136 identical, 0 differing** — `distinct_ratio` and `null_ratio` for every column of every table |
| **schema-join relationships** | **18 joins → 12 joins**; 10 identical, 8 dropped, 2 "new" |

The two "new" joins are not new relationships — they are the same pairs with
source and target **reversed**:

```
  customer_segment_history.customer_id -> customers.customer_id     (lean)
  customers.customer_id -> customer_segment_history.customer_id     (rich)
  loan_investors.investor_id -> investors.investor_id               (lean)
  investors.investor_id -> loan_investors.investor_id               (rich)
```

The 6 genuinely lost joins are **every single date→calendar join**:

```
  - balance_snapshots.snapshot_month -> calendar.cal_date
  - payments.payment_date            -> calendar.cal_date
  - support_tickets.created_date     -> calendar.cal_date
  - transactions.txn_date            -> calendar.cal_date
  - wire_transfers.received_date     -> calendar.cal_date
  - wire_transfers.sent_date         -> calendar.cal_date
```

**What this constrains.** The deterministic half of a KC capture is exactly
deterministic; the LLM-backed half is not, and its instability is large — a third
of the joins vanished and two flipped direction between two runs over identical
data. Consequences:

1. **Measurement G must not treat a changed link as evidence the trust flag
   failed.** This is the drift floor it has to clear.
2. The date-dimension joins a modeller would consider essential are the *least*
   stable output. A pipeline that trusts a single relationship scan gets a
   different semantic model each run.
3. The JT3 grain-mismatch triage case from planning
   (`snapshot_month -> cal_date`, month vs day) **is absent from this capture** —
   the triage list is per-capture, as the plan anticipated.

## Phase 3 — projector port

### Gating smoke test 1 — custom aspect on an *ingested* `@bigquery` entry: **PASS**

Wrote the custom `okf` aspect (with our extended v0.2 fields) onto the
`accounts` table entry in `@bigquery`, read it back, then deleted it.

- Write **accepted**; read-back returned `okf_type`, `generated`, `status` and
  `verified` intact.
- This was the load-bearing assumption of the whole Track A design: v0.2 trust
  and provenance signals **can** live on an asset-attached BigQuery entry. They
  were blocked by tooling, never by Knowledge Catalog.

Two porting bugs found and fixed by this test:

- **Project ID vs project number.** The write is accepted with the aspect key
  qualified by project **ID** (`royston-dev-8253.us.okf`) but the entry stores
  and returns it qualified by project **NUMBER** (`404799090046.us.okf`) — the
  same convention as the built-in `655216118709.global.overview`. Matching only
  the configured key silently drops the entire signal layer on pull.
  Fixed in `kcmd/demo/okf/okf.ts` by matching any key with the same
  `.<location>.okf` suffix.
- **Aspect deletion needs `delete_missing_aspects=True`.** An
  `update_entry` with an empty `aspects` map and `aspect_keys=[key]` is a silent
  no-op — it reports success and changes nothing. The working form (from
  `v7_iceberg_catalog_agent/channels/manage_relationships.py`) also requires the
  canonical project-number key.

## Phase 4b — the deterministic emitter

`okf-emitter/gen_okf.py`, a sibling module importing `validate_spec` and helpers
from the copied `generate_models.py`. **No existing function was modified** — a
smaller change than the planned in-file emitter, and it leaves the copy
byte-identical to its source.

- **Faithful-copy check: PASS.** Original vs copy on the same spec → `diff -r`
  empty, 18 files. (First attempt diffed against run 009's *archive* and showed
  differences — not a copy fault: the working-tree generator carries 328
  uncommitted lines of the "4 explores → 2" consolidation, so that test measured
  generator drift, not copy fidelity. See `okf-emitter/PROVENANCE.md`.)
- **Emits 13 joins + 26 metrics + 3 indexes** from `spec.yaml` — 11 one-to-many
  relationships, 2 many-to-many bridges, one concept per declared measure.
- **Deterministic: re-emission byte-identical.** `generated.at` is an explicit
  input (default: the spec's mtime), never wall-clock, so the bundle can be
  frozen and diffed like any other artifact in this repo.

## Phase 4a — Measurement E: did the LLM author find the hazards unaided?

`reference_agent` + `KCBigQuerySource` (schema + 5 sample rows + the Phase 2
profile and joins), `gemini-3.5-flash` on Vertex, 14 concepts, agent-only pass
scored **before** the emitter supplied any authoritative structure.

> Model availability: `gemini-3.5-flash` is **not served** in
> `royston-dev-8253 / us-central1` (404), nor is `gemini-flash-latest`. It *is*
> served at location `global`. The plan's pre-run check earned its place.

| Hazard (derivable from the profile it was given) | Verdict |
|---|---|
| `accounts` duplicate loads — `load_batch_id` `1:1200, 2:60` over 1260 rows | **HIT** |
| `customer_segment_history` SCD2 — `valid_to` `9999-12-31:500` | **HIT** |
| `account_owners` M:N bridge — 1200 primary + 180 joint = 1380 rows | **HIT** |

All three found, and derived rather than asserted:

- accounts: *"the primary load consists of 1,200 accounts under batch ID `1`,
  while a smaller subset of 60 records represents subsequent additions or updates
  under batch ID `2` … Out of the 1,260 total records, there are 1,201 unique
  accounts"* — and its first suggested query is literally "Deduplicating accounts
  to get the latest state" with `ROW_NUMBER() OVER (PARTITION BY account_id …)`.
- customer_segment_history: names the sentinel — *"An active segment is indicated
  by a `valid_to` date of `9999-12-31`"* — and supplies both a current-only filter
  and a point-in-time `BETWEEN valid_from AND valid_to` join.
- account_owners: *"1,200 primary ownership records and 180 joint ownership
  records across the table's 1,380 rows, every account has exactly one primary
  owner, while some accounts have multiple owners"*.

### Three caveats that matter more than the score

**1. The same prompt missed the same hazard on an earlier run.** A single-concept
probe of `tables/accounts` — same model, same inputs, minutes earlier — produced
no duplication warning at all and asserted `account_id` is a *"Primary key"*,
which the profile it was reading (`distinct_ratio 0.9532`) directly contradicts.
The full run got it right. So "3/3" is one sample of a non-deterministic process,
not a capability measurement. Author variance sits on top of the scan variance in
Measurement B.

**2. The two producers disagree on de-duplication direction.** The reviewed spec
says `order_by: load_batch_id` (ascending — *first* batch wins); the agent wrote
`ORDER BY load_batch_id DESC` (*latest* batch wins). Semantically opposite, both
plausible, now both in one bundle. Exactly what a review step is for, and it would
be invisible without the provenance split.

**3. Generated SQL references columns that do not exist.** `customers` has
`customer_id, name, segment, region, signup_date, referred_by, state, city`. The
generated query patterns select `c.first_name`, `c.last_name` and `c.email` —
6 occurrences across `payments.md` and `wire_transfers.md`. The agent is given
only its *own* table's schema, so any cross-table SQL it writes is unverified
invention. Useful as prose, unsafe as exemplars.

Per the plan these are **recorded, not patched** — patching would corrupt
Measurement F's review signal.

## Phase 5 — RESOLVED: the projection lands. 53 concepts in `okf_cymbal_v6z`

The blocker below was real but its recorded prime suspect was wrong. Kept in
full underneath, because the six ruled-out hypotheses are still worth having and
because the *wrong* guess is itself a result.

### Root cause: entries were being pushed with no name

`DocumentsLayout.init()` indexes on `entry.name` and on nothing else:

```ts
const {entry} = parseMarkdown(content);
if (entry && entry.name) this._index.set(entry.name, localPath);
```

and `parseMarkdown` reconstructs the entry as `metadata.catalogEntry ?? {}`,
never deriving a name from the file path. `toStaging` emitted only
`catalogEntry.resource.name` — a BigQuery **resource URI**, not an entry name.
So all 59 files parsed cleanly, `entry` was non-null, `entry.name` was
`undefined`, the index stayed empty, and push iterated an empty set while
printing *"Successfully pushed catalog entries."*

Probed directly against the built layout:

```
indexed entries: 0
entry is null? false
entry.name = undefined
entry.resource.name = "https://bigquery.googleapis.com/v2/projects/…/tables/accounts"
```

**The path-shape suspect is refuted, not merely unconfirmed.** `init()` contains
no path logic at all, so `catalog/<namespace>/<project>/<location>/` could never
have mattered. That prefix is a `KnowledgeBaseSource.localName` convention for
the *pull* direction; `serviceName` already strips it only when present and
otherwise treats the whole name as the entry id. A bare `tables/accounts` is a
valid entry id and maps to `<entryGroup>/entries/tables/accounts`.

Two changes, both in our own shim — the fork is untouched:

- `push.ts` derives the entry id from the bundle-relative path minus `.md`, the
  same derivation the fork's own `OkfLayout.deriveEntryName` uses.
- `toStaging` stamps it on `catalogEntry.name` and adds the
  `dataplex-types.global.generic` aspect. Dataplex rejects an entry whose type
  is `generic` when the matching aspect is absent (400 *"Missing required
  Aspect(s)"*) — an error that only became visible once entries were being
  created at all.

**Result:** 54 entries in the EntryGroup — 13 `tables/`, 1 `datasets/`, 39
`references/` (13 joins + 26 metrics), plus the auto-created
`okf_cymbal_v6z_entry`. Each concept carries the `okf` signal aspect, the
`generic` aspect, and its markdown body as `overview` (4,395 chars on
`tables/accounts`).

**Not projected: the 6 `index.md` files.** They have no frontmatter, so
`toStaging` passes them through unchanged, they get no `catalogEntry.name`, and
they never index. The documents layout has no synthetic-index support — the
fork's `OkfLayout` does (it invents a `<folder>/index` entry per directory), and
that is the one thing it would buy us here.

### `push --validate-only` is not a dry run in this fork

It created all 14 entries it "validated", then reported success. The earlier
session used `--validate-only` as a safe auth probe and cited its success as
evidence against the auth hypothesis; the conclusion held, but the probe was
writing to the catalog the whole time. Do not reach for it as a safe check.

## Measurement A — clean-OKF round-trip loss

Project → `pull` into a scratch workspace → compare against `okf-bundle/`.
53/53 concepts came back. Field by field, this is what the round trip costs.

### A.1 The body was lost entirely, until an alias bug was worked around

First pull returned **every concept with an empty body** — for OKF, where the
body *is* the concept, a 100% content loss with the frontmatter intact.

The content was never missing from the service; it came back stashed in
`catalogEntry.aspects` under the bare key `overview` and was never promoted to
the markdown body. The cause is an alias asymmetry inside the fork:

- `ResourceAlias._defaultResource` maps `dataplex-types.global.overview` → the
  short alias `overview`, and `toLocalEntry` applies it to **every** aspect key
  on the way in.
- `DocumentsLayout` promotes the body to/from the **unaliased** constant
  `OVERVIEW_ASPECT_KEY = 'dataplex-types.global.overview'`.

So push works (`loadEntry` writes the long key and `lookupAlias` passes it
through untouched) and pull silently does not. **`OkfLayout` has the identical
constant and the identical defect** — the fork's own OKF layout would lose the
body the same way. `standard.ts` is the only layout that handles both forms
(`key === 'overview'`).

Worked around in `fromStaging` by accepting the short alias, the long key and
the project-number-qualified service form. After the fix: **53/53 bodies
byte-identical to the bundle.** This is a fork bug worth reporting upstream, not
a property of OKF.

### A.2 The `index.md` layer does not survive at all

6 of 59 files. See above — no frontmatter, no entry name, no entry. The OKF
bundle's navigation layer has no representation in the projected catalog.

### A.3 Duplicate tags collapse — 1 concept of 53

`references/joins/customers__customers__referrer` carries
`[join, one-to-many, customers, customers]` (a self-join, so the emitter names
the table twice). It comes back as `[join, one-to-many, customers]`.

Mechanism, confirmed against the stored entry: tags are not a list in Dataplex.
`parseMarkdown` writes them into `resource.labels` as `{tag: 'true'}` and the
service stores `{'one-to-many': 'true', 'customers': 'true', 'join': 'true'}`.
A map cannot hold a duplicate key. Tag *order* happened to survive here, but a
map does not promise it either.

Arguably the bundle is at fault for emitting a duplicate tag. It is still a
real, silent, unreported mutation of authored content.

### A.4 Everything else survives

52/53 concepts are semantically identical in frontmatter (`type`, `resource`,
`title`, `description`, `status`, `generated.by`, `generated.at`, `sources[]`
with `id`/`resource`/`title`). The one exception is A.3.

The `okf.ts` warning that x-kcmd-less files "load lossily" does **not** apply on
this path: our shim never uses the `x-kcmd` stash, it carries the signal layer
through the `catalogEntry` passthrough into a custom aspect. That warning is
about the fork's native `OkfLayout`.

## Measurement C — round-trip fidelity: byte-unstable, semantically clean

**0 of 53 files are byte-identical.** Every single one differs. The pass
condition as written in the plan ("empty `git diff` is the pass") **fails**.

Every difference is YAML serializer style. The bundle is written by Python
(`yaml.dump` in `reference_agent` / `gen_okf`), the round trip re-emits it with
JS `yaml.stringify`, and the two disagree about:

| Churn | Bundle (Python) | Pulled (JS) |
|---|---|---|
| block sequence indent | `- core` at column 0 | `  - core` indented |
| line-wrap column | wraps after `managed` | wraps after `credit` |
| timestamp quoting | `at: '2026-08-12T20:50:24+00:00'` | `at: 2026-08-12T20:50:24+00:00` |

Parsed and compared as data rather than as bytes: **frontmatter 52/53
semantically identical** (the exception is A.3, a genuine loss) and **bodies
53/53 identical**.

**What this constrains.** OKF-as-source-of-truth cannot use `git diff` as its
review surface without a canonical formatter — the churn would swamp every real
change, which is exactly the failure mode Measurement F is meant to detect. The
fix is cheap and mechanical (normalise the bundle through the same emitter after
each pull, or pin a shared YAML style), and it is a **tooling** requirement, not
evidence against the model. Recorded here so F is not run against a diff that is
99% noise.

## Measurement D — the extended trust tier survives projection: PASS

Tests our own schema extension. `verified`, `status` and `stale_after` are OKF
v0.2 fields the shipped aspect schema omits; `okf-aspect.json` adds them and
`SIGNAL_KEYS` carries them. Nothing had ever exercised them — the bundle has
`status: stable` on 39 concepts and **zero** `verified` or `stale_after`.

A matrix was injected into a scratch copy of the bundle (the bundle itself was
not mutated — Phase 6's sign-off is a deliberate separate step, and editing it
here would corrupt Measurement F), pushed, pulled, and compared.

| Concept | Tier under test | Result |
|---|---|---|
| `tables/accounts` | human-reviewed: `status: draft` + `verified: [human:…]` + `stale_after` | **PASS** all three |
| `tables/customers` | machine-confirmed: single non-human `verified` actor | **PASS** |
| `tables/payments` | 2-element `verified` array (machine **then** human) + `stale_after` | **PASS**, order preserved |
| `references/joins/accounts__transactions` | `status: deprecated` | **PASS** |
| `tables/calendar` | control — no `verified` key at all | **PASS**, absent both sides |

Everything that matters here holds: all three fields survive; the record array
survives with **cardinality and order intact**; non-default `status` values
(`draft`, `deprecated`) survive, not just the `stable` the bundle already had;
and **absence survives as absence** — the unverified tier does not come back as
an empty array, which is what makes "no key = unverified" a usable distinction
rather than an ambiguity.

So the v0.2 trust tier was blocked by tooling, exactly like the Phase 3 finding
about Track A. Knowledge Catalog stores it fine once the aspect type declares it.

### The okf aspect write is a full replace, not a merge

Found while restoring the catalog afterwards. Re-pushing the clean bundle — in
which those concepts have no `verified` and no `stale_after` — **removed** the
injected values rather than leaving them in place:

```
tables/accounts:  status=None  verified=None  stale_after=None
references/joins/accounts__transactions:  status='stable'  ...   # its own value, restored
```

This is the behaviour OKF-as-source-of-truth needs: the bundle wins, and a field
deleted from the bundle is deleted from the catalog. It also means the projection
cannot be used to *augment* an entry incrementally — anything not in the bundle
at push time is gone. Worth stating plainly in RESULTS.md, since it is the whole
argument for keeping the bundle authoritative.

## Track A — the okf aspect on the ingested `@bigquery` entries: 14/14

The projection that actually matters for the agent story. Track B's EntryGroup
holds abstract concepts in a side catalog; Track A attaches the signal layer to
the BigQuery entries an analyst's tooling already looks at.

`kcmd/demo/okf/push-track-a.ts` maps the 14 asset-backed concepts
(`tables/*.md` + `datasets/*.md` — joins and metrics have no ingested entry to
attach to) onto `BigQueryDatasetSource`'s local names,
`bigquery/<project>/<dataset>/<table>`, and pushes through the same shim.

**Result: the `okf` aspect is present on 14/14 `@bigquery` entries**, carrying
`okf_type`, `generated.by`, `generated.at` and `sources`. Phase 3's smoke test
proved one write by hand; this is the whole set, projected from the bundle.

Two things the mapping had to respect, both different from Track B:

- **The entry type is fixed by ingestion and must be echoed back.** These are
  `bigquery-table` / `bigquery-dataset`, not `generic`. `toStaging` grew an
  `entryType` parameter, and it emits the `generic` *aspect* only for `generic`
  entries — that aspect is required exactly when the type requires it.
- **`ingestedEntries` is true**, so no synthetic index entries may be created.

### Scope decision: the okf aspect only, nothing else

`catalog.yaml`'s `publishing.aspects` lists only `royston-dev-8253.us.okf`. The
concept body is deliberately **not** written into these entries, so whatever
Dataplex generated for them is left exactly as the Phase 2 scan produced it —
an untouched control for Phase 7, which has to tell "the re-scan overwrote
curated content" apart from "the content was never there".

### Finding that changes Phase 7: there is no `overview` aspect here at all

The plan assumes curated content lives in `overview` and that Measurement G
watches a `<!-- curated:v1 -->` sentinel inside it. On these entries **`overview`
does not exist** — it is absent from the aspect map, not merely empty. What the
Phase 2 DATA_DOCUMENTATION scan actually wrote is two different aspects:

```
accounts aspect keys: bigquery-policy, bigquery-table, descriptions,
                      okf, queries, schema, storage
```

- `655216118709.global.descriptions` — the generated table description, stamped
  with the producing scan (`kc-doc-v6z-scaffold-copy-accounts`, run
  2026-08-12T20:24:45Z)
- `655216118709.global.queries` — the generated suggested SQL

Both carry **`userManaged: false`**. That flag, not the sentinel, is the real
mechanism Measurement G is about: it is how Knowledge Catalog marks content a
re-scan is free to overwrite. (It is the same `userManaged` guard the v7
relationships work ran into.)

So Phase 7 needs a decision before it can run: put the sentinel in
`descriptions` and see whether writing it flips `userManaged` to true and
thereby protects it, or accept that the `okf` aspect — a custom aspect type, one
no scan owns — is trivially safe and therefore not an interesting test. **The
second reading makes G nearly vacuous, so the first is the measurement worth
taking.** Recorded here rather than decided, because it changes what G means.

Both aspects survived the Track A push intact, which also confirms the
publishing filter does what it claims.

## Measurement F — is the projection diff reviewable? Yes, but only with a tool that did not exist

F asks whether a human can review what the projection round trip produces. The
answer turns entirely on canonical formatting, which is why Measurement C
flagged it as a prerequisite.

| | files differing | what a reviewer sees |
|---|---|---|
| raw `diff` | **53 / 53** | 100% YAML-serializer churn. Unreviewable. |
| canonical `diff` | **1 / 53** | the one genuine loss, and nothing else |

The single surviving difference is the duplicate-tag collapse already named in
Measurement A.3 — `[join, one-to-many, customers, customers]` returning three
tags. Plus the 6 `index.md` files, which report as *only in bundle* because they
do not project at all (A.2). **Both are real findings, and after
canonicalisation they are the only things in the diff.** That is the pass.

### Building the canonicaliser: `okf-review/canonicalize.py`

Two things had to be settled, and only the first was mechanical.

**1. The canonical style is a choice, not a discovery.** The bundle's two
producers disagree, so there was no existing convention to adopt:

| producer | width | allow_unicode |
|---|---|---|
| `okf-emitter/gen_okf.py::_fm` | 100 | False |
| `reference_agent` `OKFDocument.serialize` | 80 (default) | True |

| candidate | files reformatted | titles left holding `\uXXXX` |
|---|---|---|
| gen_okf (w=100, escaped) | 11 | 13 |
| agent (w=80, unicode) | 20 | 0 |
| **chosen (w=100, unicode)** | **24** | **0** |

The chosen style reformats the most files and is still right, *because F is a
question about human legibility*: 13 join concepts are titled
`customers → customers (referrer)`, and gen_okf's style renders that
`"customers \u2192 customers (referrer)"` for a quarter of the bundle. A wider
wrap also means editing one word of a `description` rewraps fewer lines, so a
later diff shows the edit rather than the reflow. Reformatting is a one-time
cost; legibility is permanent.

**2. Top-level key order was not enough.** Ordering only the frontmatter keys
left **12** differing files. Eleven of them differed on nothing but the key
order *inside* `sources[]` list items: the round trip returns `id, resource,
title` (that is `fromStaging`'s `pick` order) while `reference_agent` emitted
whatever order the model happened to produce. Canonicalising one level down —
`sources` → `(id, resource, title)`, `generated`/`verified` → `(by, at)` — took
12 to 1. Without that step F would have reported a 12-file diff of which 11
were noise, and the noise would have looked like content.

### The bundle is now canonical, and the reformat changed nothing

`--write` over `okf-bundle/`: **27 files reformatted, 51 insertions / 53
deletions, 0 semantic changes** — verified by parsing every touched file at
`HEAD` and in the working tree and comparing frontmatter-as-data plus stripped
body. The tool is idempotent (`--check` clean immediately after `--write`) and
has a `--selftest` that fails if `reference_agent`'s `_PREFERRED_KEY_ORDER`
drifts from the copy embedded here.

### What this constrains

- **"Is OKF-as-source-of-truth reviewable?" — yes, conditionally.** The diff is
  clean and the signal is exactly the real losses. But out of the box it is
  100% noise; the review surface only exists because a canonicaliser was built
  for it. That belongs in the RESULTS.md cost column next to the two fork
  defects, not in the win column.
- **Canonicalisation is a required post-authoring step, not a tidy-up.**
  `reference_agent` writes non-canonical frontmatter every time it authors, so
  Phase 6 sign-off and any future authoring pass must run `--write` afterwards
  or the next diff is noisy again.
- Phase 6's sign-off edits can now be reviewed as a diff, which is what makes
  the half-flagged/half-unflagged control legible.

## The dedup disagreement dissolves, and the profile is off by one

Carried forward across two sessions as an open item for sign-off: the reviewed
spec says `order_by: load_batch_id` (ascending, first batch wins) while the
agent wrote `ORDER BY load_batch_id DESC` (latest wins) — "semantically
opposite, both plausible, now both in one bundle."

Queried the table instead of arbitrating it.

```
distinct_accounts   1200
accounts_with_dupes   60
batch1              1200
batch2                60
overlapping pairs     60, identical on every non-batch column: 60
```

**Batch 2 is a pure re-load of 60 existing rows, not a set of updates.** Every
one of the 60 overlapping pairs is byte-identical on every column except
`load_batch_id`. So the dedup *direction is irrelevant to the result*: first-wins
and latest-wins select rows with identical content. Both producers are correct,
and the conflict recorded twice as a real semantic disagreement is **empty**.

The resolution to record at sign-off is therefore not "which producer won" but
"the question was not load-bearing on this data" — while noting that the
direction *would* matter the moment a batch carried genuine updates, which is
why keeping the guidance is still right.

### The disagreement was hiding a real error: `distinct_ratio` is wrong

Measurement E quoted, approvingly, the agent's *"Out of the 1,260 total records,
there are 1,201 unique accounts"*. The true count is **1,200**.

The agent is not at fault. The captured profile says:

```
kc-capture/profile/accounts.json:  "distinct_ratio": 0.9531746031746032
0.9531746031746032 × 1260 = 1201.0     exactly 1201/1260
actual                                  1200/1260 = 0.9523809523809523
```

**The Knowledge Catalog DATA_PROFILE scan reports 1201 distinct `account_id`
where there are 1200.** The agent derived its figure faithfully from the input it
was given.

This sharpens Measurement B rather than contradicting it. B established the
DATA_PROFILE half of a capture is **perfectly reproducible** — 136/136 statistics
identical across two runs. It did not establish that it is **accurate**, because
it only ever compared the scanner against itself. It is off by one here,
consistent with an approximate distinct-count implementation.

Consequences:

1. **Reproducible is not correct.** Any downstream rule keyed on `distinct_ratio`
   inherits the error. A "distinct_ratio == 1.0 ⇒ primary key" heuristic is
   exactly the kind of thing that breaks on an approximate counter — and note the
   earlier single-concept probe asserted `account_id` is a *"Primary key"* off
   this same column.
2. **Measurement E's hazard verdict still stands.** The agent was asked whether it
   found the duplicate-load hazard, and it did. Only its derived count was wrong,
   and it was wrong because its source was.
3. It took a direct query to notice. Two sessions of review read that sentence
   and neither checked the arithmetic, because 1,201 is plausible. That is the
   argument for Phase 6 verifying claims against the warehouse rather than
   against the prose.

## Phase 6 part 2 — join triage and sign-off

### Join triage — `okf-review/join_triage.yaml`, one entry per generated link

All 12 links in the frozen rich capture, all `inference_source: AGENT`, all
arriving `user_managed: false`. JT1 and JT4 were **measured against the
warehouse** rather than eyeballed — orphan counts both directions, and
max-rows-per-key on each side.

| Criterion | Result |
|---|---|
| **JT1 Real** | **12/12 pass.** Every link's fields correspond. The orphans that exist are legitimate optionality — 88 customers never filed a loan application, 120 accounts have no transactions — not broken references. |
| **JT2 Authoritative** | **1 reject.** |
| **JT3 Grain-compatible** | **No instance in this capture.** |
| **JT4 Cardinality declared** | **0/12.** Universal failure. |

**The JT2 reject: `accounts.customer_id -> customers.customer_id`.** Real —
JT1 passes with 0 source orphans — but not authoritative. That column names
only the *primary* owner, so joining customers to accounts through it silently
drops every joint owner; the `account_owners` bridge holds 1200 primary + 180
joint rows over 1260 accounts. An agent offered both paths will sometimes take
this one and under-report multi-owner accounts **with no error surfaced**. This
is the single most consequential item in the triage.

**JT3 has no instance, and that is the honest finding.** The plan's example was
`balance_snapshots.snapshot_month -> calendar.cal_date` (month vs day). Measurement
B already recorded that *every* date→calendar join is absent from the rich
capture — all 6 dropped between runs. The role-playing case JT2 was also
expected to catch (`wire_transfers.sent_date` vs `received_date`) is invisible
for the same reason: neither date link was generated. Recorded as untestable
here rather than manufactured.

### Cross-cutting: the duplicate load corrupts every inferred cardinality

`accounts` carries 60 re-loaded rows, so max-rows-per-key on `account_id` is 2,
so **every link touching accounts measures as N:M** when it is semantically 1:N
or N:1 — 3 of the 12.

```
account_owners.account_id -> accounts.account_id       measured N:M, semantic N:1
accounts.account_id -> balance_snapshots.account_id    measured N:M, semantic 1:N
accounts.account_id -> transactions.account_id         measured N:M, semantic 1:N
```

**Cardinality inferred from data alone cannot distinguish "this table has
duplicate loads" from "this relationship is many-to-many."** Any automated
modeller reading cardinality off the warehouse gets three wrong answers here,
and each one is the kind that produces silently inflated measures rather than an
error. The bundle's de-duplication guidance is load-bearing for this reason, not
merely tidy.

### Sign-off — 27 flagged, 26 control

`okf-review/signoff.py`, deterministic and re-runnable (`--apply` / `--status` /
`--clear`), writing `verified: [{by: human:kenly@google.com, at: …}]`.

| provenance class | flagged | control |
|---|---|---|
| `generate_models/okf` | 20 | 19 |
| `reference_agent/gemini-3.5-flash` | 7 | 7 |
| **total** | **27** | **26** |

**The split is balanced across provenance classes on purpose.** Flagging one
whole class would confound the flag with the producer, so any Phase 7 difference
could be read as "agent-authored content is treated differently" rather than
"the flag worked". Within each class the concepts are sorted by path and every
other one is flagged, so the population is reproducible and uncorrelated with
content.

Applied cleanly: **27 files, +81 lines, and 0 changes outside the `verified`
key** — verified by parsing every touched file at `HEAD` and in the working tree
and comparing everything else as data. Projected to both tracks and confirmed
live: **Track B 27 flagged / 26 control, 0 mismatches against the bundle**;
Track A 6 flagged / 7 control across the 13 tables.

**What the flag claims, stated plainly.** Our aspect schema defines `human:<id>`
as human-reviewed. The review behind it is a real pass over the canonical diff
and the warehouse, and it found real things — the dedup conflict was empty, the
profile distinct count is off by one, one join fails JT2. It is **not** a deep
per-concept audit of all 53 bodies, and the flag should not be read as more than
"reviewed at Phase 6 depth". Recording that here matters more than the flag
does: an unearned trust signal is worse than none.

## Phase 7 / Measurement G — curated content survives iff `userManaged` is set

Reframed, as Track A required: the plan watched a `<!-- curated:v1 -->` sentinel
inside `overview`, but the `@bigquery` entries have **no `overview` aspect at
all**. The scan writes `descriptions` and `queries`. So G was pointed at
`descriptions`, with **`userManaged`** — Knowledge Catalog's own "a scan may
overwrite this" marker — as the variable under test. Testing the custom `okf`
aspect instead would have been vacuous: no scan owns a custom aspect type.

Design: a 2×2 crossing `userManaged` with the OKF `verified` flag, plus two
untouched tables, so survival can be attributed to one and not the other. All
six DATA_DOCUMENTATION scans were re-run and all six jobs reported SUCCEEDED.

| table | OKF `verified` | `userManaged` | aspect rewritten | sentinel survived |
|---|---|---|---|---|
| `accounts` | **FLAGGED** | false | yes | **NO** |
| `balance_snapshots` | control | false | yes | **NO** |
| `customers` | **FLAGGED** | **true** | no | **YES** |
| `account_owners` | control | **true** | no | **YES** |
| `transactions` | FLAGGED | false | yes | *(not curated)* |
| `wire_transfers` | control | false | yes | *(not curated)* |

### Three findings, in order of how much they matter

**1. `userManaged: true` is honoured, and it is the only thing that is.**
Survival tracks `userManaged` perfectly across all four curated cells and is
**completely uncorrelated with the OKF `verified` flag** — a flagged concept
with `userManaged: false` was destroyed, an unflagged one with `userManaged:
true` was preserved. The OKF trust tier is an *annotation*; it confers no
protection inside Knowledge Catalog. Anyone reading `verified: [{by: human:…}]`
as "this is safe from the pipeline" is wrong.

**2. Writing curated content does NOT set `userManaged`. That is a silent
data-loss trap.** The first probe wrote a curated description without touching
the flag: the write was accepted, the sentinel landed, and `userManaged` stayed
`false`. Nothing warned. The content then survived until the next scan and was
gone — no error, no conflict, no version. A human editing a description through
any path that does not explicitly set `userManaged` has written something with
an invisible expiry date.

**3. A protected aspect keeps its ORIGINAL job stamp, which is how you can tell
it was skipped.** `customers` and `account_owners` still carry
`runTime: 2026-08-12T20:26:50Z` and `20:24:45Z` after a successful
2026-08-13T01:11 scan, while the four unprotected tables all advanced to the new
run time. The scan did not merely decline to overwrite the text — it did not
touch the aspect at all.

> This nearly produced a wrong answer. The first pass of the verifier inferred
> "did a scan run?" from whether `run_time` changed, which reports the two
> *protected* tables as "no rescan — inconclusive". The stale stamp is evidence
> **of** protection, not of a skipped scan. Ground truth has to come from the
> job state, which is why `measure_g.py` now records the re-scanned set
> explicitly.

### What this constrains

- **Measurement B's drift floor did not need to be invoked.** B warned that a
  third of joins vanish between runs, so G must not read a changed link as flag
  failure. G avoided the problem entirely by measuring an aspect the scan
  deterministically owns, on a per-table basis, with an explicit control.
- **For OKF-as-source-of-truth this is a mixed result, and the mixed part is
  fine.** The projection cannot protect what it writes — but it does not need
  to. The bundle is authoritative and re-pushing restores it, and Follow-up 9
  (v7) established that every consumed channel is live. The honest statement is:
  *OKF survives re-scan by being re-projected, not by being protected.* Any
  claim that the trust tier hardens content against the pipeline is false.
- **Track A's projection should set `userManaged: true` if it ever writes
  `descriptions`.** It currently writes only the `okf` aspect, which no scan
  touches, so it is unaffected — but that safety is incidental, not designed.

## Phase 8 — Arm K (OKF bundle via kcmd MCP) vs Arm D (Knowledge Catalog, live)

5 questions × 3 repeats × 2 arms, `gemini-2.5-flash` on Vertex. Every question
targets a hazard the bundle documents and has a distinct **correct** answer and
a distinct **naive-trap** answer, so responses are classified, not judged.
Ground truth computed directly against BigQuery.

Both arms get an identical, deliberately **minimal** system prompt. The
`bq-kc-agent` scaffold ships a prompt carrying ten hand-written modelling rules
— fan traps, de-duplication, zero-fill cohorts, SCD2 — which encode exactly the
knowledge the bundle is meant to supply. Reusing it would have answered the
questions from the prompt and measured nothing.

| q | hazard | Arm K | Arm D | discriminates |
|---|---|---|---|---|
| q1 | duplicate load — count | **2/3** | 1/3 | K > D |
| q2 | duplicate load — SUM | **3/3** | **0/3** | **K > D, decisively** |
| q3 | M:N ownership bridge | 3/3 | 3/3 | no |
| q4 | zero-fill cohort average | **0/3** | **0/3** | no — both fail |
| q5 | SCD2 current rows | 3/3 | 3/3 | no |
| | **total** | **11/15** | **7/15** | |

### The plan expected Arm D to win. It lost.

The plan said "Arm D is expected to win and that is not evidence about OKF."
Arm D had **strictly more capability** — `search_entries`, `lookup_entry`,
`lookup_context` against the live catalog, versus Arm K's `list-entries` and
`lookup-entry` with **no search at all** — and still scored lower.

**q2 is the cleanest result in the whole experiment: 3/3 versus 0/3.** Asked for
the total balance across all accounts, Arm K de-duplicated every time and Arm D
never did. The bundle's `tables/accounts.md` body states the hazard in prose and
supplies the `ROW_NUMBER() OVER (PARTITION BY account_id …)` pattern; the live
catalog's generated `descriptions` aspect does not.

### Why: Arm D had the better tools and kept not using them

**7 of Arm D's 15 runs never touched the catalog at all** — straight to
`execute_sql`, including both q1/q2 failures in two of three reps. Search being
available is not the same as search being used. Arm K's tool surface is so thin
that `list-entries` → `lookup-entry` is the only path to *any* metadata, so the
model walks it.

The mirror-image evidence on Arm K: **of its 15 runs, 14 called `lookup-entry`
and the one that did not was a failure** (q1 rep2 — `list-entries` then straight
to SQL, answering 1260). Correct answers correlate with retrieval, not with the
arm.

So the honest causal claim is not "OKF is better metadata". It is: **a narrow
tool surface that forces retrieval beat a rich one that permits skipping it**,
and the content behind Arm K happened to contain the hazard. Both halves matter,
and the first half is about MCP ergonomics, not about OKF.

### q4 is a real negative for the bundle

Both arms 0/3 on the zero-fill cohort average (16.67 correct, 18.52 trap — the
average over accounts that *have* transactions). Neither channel carries the
hazard: the bundle documents duplicate loads, the M:N bridge and SCD2, but says
nothing about zero-count denominators. The `bq-kc-agent` scaffold's discarded
prompt *did* have a rule for it. **A curated bundle only defends against the
hazards someone curated into it** — that is the ceiling on this whole approach,
and it showed up on the first question that fell outside the curated set.

### Run 1 measured an empty catalog — the Phase 5 defect, on the read path

The first execution scored Arm K 1/5, and the transcripts explain why: *"the
`list_entries` function returned an empty list."* Pointing the kcmd MCP server at
`okf-kb-workspace` (layout `documents`) indexes **zero** of the 59 files, because
clean OKF files carry no `catalogEntry.name` — the identical defect that was the
Phase 5 blocker, resurfacing on read. Fixed by giving Arm K a workspace with
`layout: okf`, whose `OkfLayout` derives names from paths; `list-entries` then
returns 59 and `lookup-entry` returns the 5,190-character concept including the
de-duplication guidance. Run 1's transcripts are kept in
`okf-agent/results_run1_armK_empty_catalog.json`.

**This is the third time one bug has produced a silent, plausible-looking wrong
answer** — success on an empty push, an empty body on pull, and now a scored
agent arm reading nothing. Each looked like a result.

### Limits — do not over-read this

n=3 per cell, one model, 5 questions, one dataset, and 4 of 15 Arm K runs and 8
of 15 Arm D runs varied their tool use between identical repeats. q1 moved
between correct and trap on both arms across reps. This is directional, not a
benchmark, and it is consistent with the author variance Measurement E already
recorded.

## Two Track A defects found on review (both fixed)

Neither changed a published result — Track A still has the `okf` aspect on
14/14 entries and the entry types are still the native
`bigquery-table` / `bigquery-dataset` — but both were latent and both are the
same failure mode as everything else here: silent.

### 1. The entry type was hardcoded, and BigQuery has more than two

`push-track-a.ts` mapped `tables/*.md -> dataplex-types.global.bigquery-table`
by hand. That is right only because this dataset holds 13 `BASE TABLE`s and
nothing else; BigQuery entries can equally be `bigquery-view`, `bigquery-model`
or `bigquery-routine`, and a view would have been stamped `bigquery-table`.

**No new entry types were ever defined** — those constants are the *aliases for
the native Knowledge Catalog types* Dataplex had already assigned at ingest, and
the live entries confirm they are unchanged. The defect is that the shim was
*asserting* a type the catalog could simply be asked for.

Why the type must be there at all: `snapshot.ts:446` uses it as a **publishing
filter** — an entry whose `type` is absent from `catalog.yaml`'s
`publishing.entries` is dropped and `push` still reports success. Precisely the
Phase 5 blocker's mechanism, so a wrong type loses entries quietly.

Fixed by reading the live `entryType` per entry and normalising it. That
normalisation is itself load-bearing: the service returns the built-in types
qualified by project **NUMBER** (`655216118709.global.bigquery-table`) while the
allowlist is written with the project **ID** alias
(`dataplex-types.global.…`) — the same ID/number asymmetry the Phase 3 smoke
test found on aspect keys. Comparing the raw form would have dropped all 14.
The script now also **throws** if a derived type is not in the allowlist,
converting a silent drop into a loud error.

### 2. The kcmd CLI was authenticating as the wrong identity

`ApiContext.default()` mints its bearer token from the **globally active gcloud
config's account** — `kenly@gcp.altostrat.com` on this workstation — not from
the `admin@kenly.altostrat.com` in `GOOGLE_APPLICATION_CREDENTIALS`, which
governs the Python clients only. So every `kcmd push` in this work ran as an
identity nobody chose, and it worked only because that account happens to have
access.

An earlier revision of `HANDOFF.md` §2.2 explicitly dismissed the
`Your active configuration is: [student-01--qwiklabs-…]` line as "noise, not a
routing bug". **That was wrong**, and it is corrected there now. `config.ts`'s
own PORT NOTE had caught this for project and location and missed it for the
token.

The destination was never at risk — that comes from `catalog.yaml`'s `scope:`,
and all writes landed in `royston-dev-8253`. Only the identity was accidental,
and on a workstation where the active config points at an unrelated project it
would have failed confusingly rather than safely. `push-track-a.ts` now refuses
to run unless `KCMD_ACCESS_TOKEN` is set explicitly.

## Track A/B de-duplication — and the confound it exposed in Phase 8

Raised from a Knowledge Catalog search screenshot: every table appeared **twice**
— `Customers` with our description next to native `customers` with none.

### The duplication was real and was Track B's fault

A catalog search for the dataset returned **28 hits**: the 14 native `@bigquery`
entries and 14 standalone concepts in `okf_cymbal_v6z`. (The "BIGQUERY TABLE"
type shown against the duplicates is the UI's *type alias* column, rendering the
`type` field of our `generic` aspect. The entries' real type is `generic`.)

Only 39 of the bundle's 53 concepts — the joins and metrics — have no native
home. **The other 14 describe assets Dataplex already has entries for, and
publishing them as separate entries created a second catalog object per table.**

Fixed by splitting the two tracks on a property the bundle already carries: a
concept with a top-level `resource:` names an ingested asset, so Track B skips
it and Track A owns it. Joins and metrics have no `resource:` and stay in Track
B.

- `push.ts` now skips asset-backed concepts (`staged 45 … skipped 14`)
- `bq-okf-workspace/catalog.yaml` adds `dataplex-types.global.overview` to
  `publishing.aspects`, so the concept body lands on the native entry — a slot
  Measurement G found **empty**, so nothing is displaced
- the 14 duplicates were deleted

**Result: 28 search hits → 14.** `okf_cymbal_v6z` holds 40 entries (39
references + its own), and all 14 native entries carry both the `okf` aspect and
the 4,395-character body, with `descriptions` still scan-owned
(`userManaged: false`).

### Measurement G extended: `overview` survives a re-scan

Re-ran the `accounts` DATA_DOCUMENTATION scan with the body in place.
**SUCCEEDED, and the overview was untouched (4,395 → 4,395 chars)** despite
`userManaged` being false. G showed the scan destroys unprotected content in
`descriptions`; this shows the scan only touches the aspects it **owns**.
`overview` is not one of them, so the projection is safe there for free — and
`userManaged` only matters for aspects the scan writes.

### The Phase 8 re-run, and why my earlier explanation was wrong

Projecting the bodies onto the native entries should have helped Arm D. It did
not: **6/15, against 7/15 before — unchanged within noise**, and q2 still 0/3
while Arm K scores 3/3 off the identical text.

The reason is not that Arm D ignored the content. **Its tool does not return
it.** The prebuilt dataplex toolbox's `lookup_entry` takes a `view` whose
documented default is `2 (FULL)`, and FULL means *"all required aspects and the
**keys** of non-required aspects"*:

```
view=2 (FULL, the default)   3,619 chars   OKF body present: NO
view=4 (ALL)                18,171 chars   OKF body present: YES
```

`overview` is a non-required aspect, so at the default view its content is
withheld and only its key is returned. Arm D was structurally unable to read the
enrichment sitting on the entry it was querying, and nothing in its tool
descriptions would prompt it to ask for `view=4`.

**This supersedes the explanation recorded in the Phase 8 section.** That section
attributed Arm K's win to a thin tool surface forcing retrieval, which is still
true and still half the story. The other half is sharper: **Arm K's
`lookup-entry` returns the whole concept, and Arm D's returns a summary with the
prose stripped out.** The two arms were never reading comparable content, even
after both were pointed at the same text.

The generalisable finding is not about OKF at all: *publishing knowledge to a
catalog is not enough if the default read path omits it.* A "FULL" view that
withholds the field a human would consider the whole point is a trap, and it is
invisible — the call succeeds and returns a plausible-looking entry.

## Forcing `view=ALL` — Arm Dall, and the two failures it separates

Follow-up to the finding that the dataplex toolbox's `lookup_entry` withholds
the concept body at its default view. **Can it be forced?** Yes, deterministically.

### How

An ADK `before_tool_callback` that rewrites the argument before the call:

```python
ENTRY_VIEW_ALL = 4   # Dataplex EntryView.ALL

def _force_full_view(tool, args, tool_context):
    if tool.name == "lookup_entry" and args.get("view") != ENTRY_VIEW_ALL:
        args["view"] = ENTRY_VIEW_ALL
    return None        # None = no override, proceed with the mutated args
```

This works because ADK hands the callback **the same dict** it later passes to
the tool (`flows/llm_flows/functions.py:577` → `:589`), so an in-place mutation
is what actually reaches the server. Verified by spying on the callback: the
model called `lookup_entry` with **no `view` at all**, and the callback set it.

Instructing the model to pass `view=4` in the prompt would not be equivalent —
it is a request, not a guarantee, and the whole point is that the default is
wrong. For a non-ADK consumer the equivalent is to stop using
`--prebuilt dataplex` and supply a `--configs` tool file binding `view: 4`
(untested here).

### What it bought

| arm | q1 | q2 | q3 | q4 | q5 | total |
|---|---|---|---|---|---|---|
| Arm K — bundle via kcmd | 2/3 | **3/3** | 3/3 | 0/3 | 3/3 | **11/15** |
| Arm D — pre-enrichment | 1/3 | 0/3 | 3/3 | 0/3 | 3/3 | 7/15 |
| Arm D — enriched catalog, default view | 0/3 | **0/3** | 3/3 | 0/3 | 3/3 | 6/15 |
| **Arm Dall — enriched, `view=ALL` forced** | 0/3 | **2/3** | 3/3 | 0/3 | 3/3 | **8/15** |

**q2 went 0/3 → 2/3, and the within-arm correlation is exact:**

```
rep0  lookup_entry called, view forced  -> correct
rep1  lookup_entry NOT called           -> trap
rep2  lookup_entry called, view forced  -> correct
```

Every run that actually reached the entry with `view=ALL` got it right. The one
that trapped never called the tool. So the view was genuinely the blocker on
that question, and forcing it is a real fix — not a prompt nudge that happened
to help.

### The two failures are now cleanly separated

**1. Legibility — fixed.** The body was on the entry and the default read path
withheld it. One forced argument recovers it, and q2 is the proof.

**2. Retrieval — untouched, and now the dominant failure.** q1 is **0/3 across
all three D variants**, and the tool trace is identical every time:
`tools=['execute_sql']`. The model never consults the catalog for "how many
accounts are there?", so no amount of fixing what `lookup_entry` returns can
help — it is not called. Arm K's advantage on q1 survives for the same reason it
always did: its tool surface offers no way to answer without listing entries
first.

**The generalisable claim.** Getting knowledge to an agent through a catalog has
three independent failure points, and they need three different fixes:
*published* (Track A), *returned by the default read path* (the view), and
*actually requested* (tool-surface design or prompting). Fixing any one leaves
the others intact — 6/15 → 8/15 is what fixing exactly one looks like.

## Where `userManaged` is set: nowhere in this pipeline, deliberately

Asked directly, and worth pinning down because Measurement G made the flag look
load-bearing when it is actually out of scope for what we write.

### It is not an OKF field, and should not become one

OKF's signal layer is `okf_type`, `generated`, `sources`, `verified`, `status`,
`stale_after`. There is no `userManaged`, and adding one would be a category
error: it is a **Dataplex-native field on Dataplex's own aspects**, describing
who owns an aspect's content, not a property of the knowledge. Measurement G
established that `verified` and `userManaged` are **orthogonal** — a
`verified` concept with `userManaged: false` was destroyed by a re-scan.
Collapsing them would encode a protection guarantee OKF does not have.

### In Knowledge Catalog, Dataplex sets it — to `false` — and we never touch it

Live across all 14 Track A entries:

```
descriptions.userManaged = False   (14/14)
queries.userManaged      = False   (14/14)
okf aspect present       = True    (14/14)
overview body present    = True    (14/14)
```

Nothing in the projection writes the flag. The only code that ever set it is
`okf-review/measure_g.py`, the Measurement G harness, which set it `true` on two
tables and reverted them afterwards.

### Why the projection does not need it

`userManaged` governs only the aspects the DATA_DOCUMENTATION scan **owns** —
`descriptions` and `queries`. Track A writes `okf` (a custom aspect type no scan
owns) and `overview` (which that scan does not write). Verified directly: the
4,395-character overview survived a successful re-scan at `userManaged: false`,
unchanged. So the flag is irrelevant to everything the projection currently
touches, and the correct number of places to set it is zero.

### When it WOULD become mandatory

The moment the projection writes `descriptions` or `queries`. Then
`userManaged: true` is not optional — Measurement G showed unprotected content
in those aspects is destroyed by the next scan with no error. It would also need
somewhere to live: the natural home is the **projector's** publishing config
(a per-aspect "we own this" declaration in `catalog.yaml`), not the OKF bundle,
because it describes the projection's relationship to the catalog rather than
the knowledge itself.

> **A caveat that matters more than the flag.** If the goal is consumption by
> the **BigQuery Conversational Analytics API** rather than by an MCP agent,
> neither target helps. The parent repo's v7 investigation found the CA API
> consumes BigQuery's own **table and column descriptions**, and does **not**
> consume the Dataplex `overview`, `descriptions` or `queries` aspects at all.
> That is a different channel entirely — the BQ schema, where `userManaged` has
> no meaning. Not re-verified here; see `v7_iceberg_catalog_agent/RESULTS.md`.
> Our Phase 8 result is about an MCP/ADK agent reading Dataplex, and does not
> transfer to the CA path.

## kcmd now owns `descriptions` and `queries` — what that bought, and what it did not

Requested: the projector should manage the scan-owned aspects too, not just
`okf` and `overview`.

### Built

`assetAspects()` maps each concept body onto the two aspects:

| target | source in the concept | result |
|---|---|---|
| `descriptions.description` | frontmatter `description` | 13/13 tables |
| `descriptions.fields[]` | the `# Schema` markdown table | **66 column descriptions** |
| `queries.queries[]` | `# Common query patterns` — `### N. Title` + fenced SQL | **37 query patterns** |

Both written with **`userManaged: true`**, which Measurement G made mandatory:
without it the next scan destroys them silently. **Verified after the change —
a successful re-scan of `accounts` left description, all 7 fields and all 3
queries byte-identical.**

Two things the bundle's own inconsistency forced:

- **The schema tables have two layouts.** The LLM author emitted
  `| Field | Type | Description |` with backticked names for some tables and
  `| Field Name | Type | Mode | Description |` with bold names for others. A
  parser assuming column 3 produced **zero** fields for 4 of 13 tables while
  looking like it worked. It now takes first cell / last cell and strips either
  emphasis marker.
- **Field names were checked against `INFORMATION_SCHEMA`.** 66 claimed, **0
  invented**, 2 real columns left undocumented (`customers.name`,
  `investors.name`). Measurement E's invented columns were in SQL bodies, not
  schema tables — so this content is safe to project, but the check should stay
  before anyone trusts a future bundle.

kcmd also refuses a publishing aspect that is not also in `snapshot.aspects`
("Publishing aspect type ... is not listed in snapshot aspects") — a loud
failure, which is a welcome change from this fork's usual silence.

### Correction: `descriptions` is NOT returned at the default view either

An earlier note in this file claimed `descriptions` comes back at the default
`view=FULL` while `overview` needs `ALL`. **That was wrong.** Measured against
the live entry after the projection:

```
view=2 (FULL, default)   3,619 chars   our description: NO   our queries: NO   overview: NO
view=4 (ALL)            13,302 chars   our description: YES  our queries: YES  overview: YES
```

All three are **non-required** aspects, and FULL returns non-required aspects as
keys only. The earlier reading was fooled by `load_batch_id` appearing in the
FULL response — that is the column **name** from the required `schema` aspect,
not our description of it.

So owning `descriptions`/`queries` buys **UI correctness and ownership**, not
agent reach. Reach still needs `view=ALL`.

### And it did not move the agent at all — because retrieval dominates

| run | score | `lookup_entry` called |
|---|---|---|
| Arm K — bundle via kcmd | **11/15** | **14/15** |
| Arm Dall — +overview, view=ALL | 8/15 | 4/15 |
| Arm D — pre-enrichment | 7/15 | 5/15 |
| Arm D — +overview | 6/15 | 2/15 |
| Arm D — +descriptions/queries | 6/15 | 4/15 |
| Arm Dall — +descriptions/queries | 6/15 | 1/15 |

**Score tracks the retrieval rate, not the content.** Every content improvement
— overview, then descriptions, then queries, then forcing `view=ALL` — left the
D family between 6 and 8 out of 15, while the one arm that actually looks
something up on almost every question scores 11.

Pooled over all 75 D-family runs:

```
called lookup_entry:       10 correct / 16   (62%)
did NOT call lookup_entry: 23 correct / 59   (38%)

on q1+q2 — the two questions only the catalog can settle:
called:      2 correct /  6   (33%)
not called:  1 correct / 24   ( 4%)
```

The last pair is the finding. On questions where the answer *is* in the
metadata, an agent that consults the catalog is right a third of the time and
one that does not is right 4% of the time — and the D family does not consult it
in 24 of 30 attempts.

**Conclusion for the projector.** Owning `descriptions` and `queries` is right on
its own terms: the bundle is now the source of truth for what a human sees in
the UI, it survives re-scan, and ownership is explicit. But it is the third
consecutive intervention on the *content* axis that produced no measurable agent
improvement. The remaining bottleneck is not what the catalog holds, nor what
its read path returns — it is that the agent does not ask. That is tool-surface
and prompt design, and no amount of projection fixes it.

## `userManaged` granularity: whole-aspect only, and what that costs

Asked whether ownership can be partial. **It cannot.** From the aspect type
definitions (`projects/dataplex-types/locations/global/aspectTypes/…`):

```
Descriptions: record          Queries: record
  description: string           queries: array
  fields: array                   query: record
    field: record                   description: string
      name: string                  sql: string
      description: string           source: enum
      fields: array                 sqlDialect: enum
  userManaged: bool             userManaged: bool
  job: record                   job: record
```

`userManaged` is a **single bool at the root of each aspect**. It does not exist
on `fields[].field` or on `queries[].query`. So you cannot own one column's
description and let the scan manage the rest, and you cannot pin one curated
query while the scan keeps refreshing the others. Taking ownership means taking
all of it, and inheriting the maintenance.

### What it cost here, measured

**1. Two columns are now permanently blank.** 68 columns across the 13 tables,
66 documented by the bundle. `customers.name` and `investors.name` were never
written up by the LLM author, and because `descriptions` is now `userManaged`
the scan will never fill them. Before ownership they would have been generated.

**2. Query counts: no loss on some tables, real loss on others.** Handed
`payments` back to the scan (set `userManaged: false`, re-ran its
DATA_DOCUMENTATION scan) to measure what we displaced:

```
payments   ours: 6 fields, 3 queries    scan: 6 fields, 3 queries   -> no coverage loss
accounts   ours: 7 fields, 3 queries    scan: 7 fields, 10 queries  -> 7 fewer queries
```

The scan's output per table is uneven (18–30 candidate queries in the frozen
capture, of which the aspect surfaced 3 for `payments` and 10 for `accounts`).
Whether losing 7 generated queries for 3 curated ones is a loss is a judgement
call — but it is a silent one, and it only happens on tables where the scan was
more generous than the author.

**3. The `job` provenance stamp is dropped.** Our write replaces the whole
aspect, so `job.name` / `job.runTime` — the record of which scan run produced
the content — becomes null. Nothing then distinguishes "curated" from
"generated but stale" at the aspect level; that signal now lives only in the
`okf` aspect's `generated` / `verified` fields.

`payments` and `accounts` were both restored to bundle ownership afterwards and
verified.

### The three ways to live with it

1. **Document the gaps in the bundle** — the purist option and the cheapest
   here: two column descriptions. Keeps the bundle genuinely authoritative,
   which is the whole thesis.
2. **Merge-on-write** — read the live aspect, overlay bundle fields on top of
   the scan's, write back `userManaged: true`. No coverage loss, but it freezes
   scan-generated content *inside* an aspect the bundle claims to own, and
   destroys the ability to tell curated from generated. **Rejected for this
   project**: provenance is the point.
3. **Leave `userManaged: false` and re-push after every scan.** Keeps the scan
   refreshing what the bundle does not cover, at the cost of a window where the
   catalog disagrees with the bundle. Consistent with the RESULTS.md framing
   that OKF survives by being re-projected rather than protected.

Recorded as an open item; option 1 is the recommendation and is two lines of
prose.

## `verified` is NOT mapped to `userManaged`, and the Track A pull is lossy

Two questions, both answered by measurement rather than intent.

### 1. No — `userManaged: true` is unconditional, not derived from `verified`

`assetAspects()` hardcodes `userManaged: true` on both aspects for every
asset-backed concept. Nothing reads `verified`. Cross-tabulated live:

```
accounts, calendar, customers, loan_applications,
payments, transactions            verified=True   userManaged=True
account_owners, balance_snapshots, customer_segment_history,
investors, loan_investors, support_tickets,
wire_transfers                    verified=False  userManaged=True   <-- 7 tables
```

Seven tables are unflagged in the bundle and owned in the catalog anyway.

**Mapping them would be a real design decision, not a tidy-up.** Measurement G
established the two are orthogonal, and coupling them would mean: *the bundle is
authoritative only for concepts a human has signed off, and the scan keeps
managing the rest.* That is defensible — it is arguably what a trust tier is
for — but it contradicts the full-replace, bundle-wins semantics that
Measurement D established and that RESULTS.md leans on. It would also make the
projection's behaviour change as review state changes, so a re-push after
sign-off would silently start overwriting content the scan previously owned.
Left unmapped and flagged here rather than decided.

### 2. What happens next: scan, pull, push

**Scan — nothing.** Measured twice: the DATA_DOCUMENTATION job runs, reports
SUCCEEDED, and leaves the owned aspects byte-identical (description, all 7
fields, all 3 queries on `accounts`). It no longer refreshes anything on those
entries — including the columns the bundle does not document, which is the cost
recorded in the granularity section above.

**Pull — lossy for Track A, in a way Track B is not.** A real pull of the 14
asset concepts returns all 14, and the body round-trips intact, but:

| field | bundle | after pull |
|---|---|---|
| `title` | `Accounts` | `accounts` — the **native** displayName |
| `description` | `Core table containing checking…` | **absent** |
| `resource` | `https://bigquery.googleapis.com/v2/projects/…` | `projects/…` — different form |
| `descriptions` / `queries` aspect content | 7 fields, 3 queries | **discarded** by `fromStaging` |

The cause is structural: these entries' `entry_source` is system-owned, so our
`title`/`description` never land there — the description lives *only* inside the
`descriptions` aspect, and `fromStaging` maps only `okf` and `overview` back to
clean OKF. Track B did not have this problem because it owns its entries'
`entry_source` outright (Measurement C: 52/53 semantically identical).

**Push — safe from the bundle, degrading from a pull.** Pushing from
`okf-bundle/` is unaffected. Pushing from a *pulled* tree was evaluated offline
(pure function, no writes):

```
FROM BUNDLE        description="Core table containing checking, savings, and …"  fields=7  queries=3
FROM PULLED TREE   description=""                                                fields=7  queries=3
```

The 7 fields and 3 queries survive because they are re-derived from the body,
which does round-trip. The **table-level description would be blanked**. So a
pull→push cycle is currently a slow leak of exactly one field per table.

**Fix, not yet applied:** teach `fromStaging` to reconstruct `description` from
the `descriptions` aspect the same way it already recovers the body from
`overview`. That is the symmetric fix to Measurement A.1 and it restores Track A
round-tripping. Recorded as an open item.

## Phase 5 — the original blocker report (superseded by the section above)

The bundle is authored, committed and staged correctly, and the EntryGroup +
extended aspect type exist. **The projection does not land.** `kcmd push` reports
*"Successfully pushed catalog entries"* and creates nothing — after two real
pushes the EntryGroup contains only its own auto-created `okf_cymbal_v6z_entry`.

Time-boxed per the plan ("the port is the biggest unknown … if it resists, fall
back"). What is established, so the next person does not repeat it:

**Not the cause (each ruled out by measurement):**

| Hypothesis | Evidence against |
|---|---|
| Wrong identity / no auth | `push --validate-only` succeeds; the same creds write aspects directly (smoke test 1) |
| Missing catalog location | Fixed — `ApiContext.default()` reads `gcloud config get-value compute/region`, unset on this profile. `CLOUDSDK_COMPUTE_REGION=us` resolves it per-invocation |
| Missing Dataplex entry type | Fixed — this fork assigns `entry.type = metadata.type` verbatim where upstream falls back to generic; `toStaging` now emits `type: dataplex-types.global.generic`. Push still creates nothing |
| Frontmatter-less `index.md` files aborting the scan | Removing all 6 leaves `listEntries()` at 0 |
| The glob not matching | `glob('**/*.md', {cwd:'catalog'})` returns **59** in isolation |
| `init()` never running | `CatalogSnapshot.fromPath` awaits `_layout.init()` (`snapshot.ts:97`) and does not throw |

**Isolated to:** `DocumentsLayout.init()` globs 59 files and populates an index of
**0**. Every file is being rejected between the glob and the index. The next step
is to instrument `src/libts/layouts/documents.ts` around lines 54-90 (the
per-file parse/index loop) and print why each path is dropped.

**Suspected root cause.** Royston's README documents the Markdown layout as
`catalog/<namespace>/<project>/<location>/<page>.md`, and `sources/kb.ts:63`
builds local paths as `${namespace}/${project}/${location}/${entryId}`. Upstream's
OKF demo writes bare paths (`catalog/tables/accounts.md`). If this fork's indexer
requires the three-segment prefix, every OKF-shaped path fails to index — which
matches the symptom exactly. Testing that means re-staging under
`catalog/okf_cymbal_v6z/royston-dev-8253/us/…`.

**Consequence for the plan.** Measurements A (clean-OKF round-trip loss), C
(round-trip fidelity), D (extended trust tier survives projection), F (diff
review), G (flag survives re-scan) and Phase 8 (agent read paths) all sit
downstream of a working projection and are **not yet taken**.

**What this already tells us.** The plan's headline risk was whether *clean OKF*
survives kcmd's lossy path. The actual blocker is cruder and arrives earlier: the
two forks disagree about where concept files live on disk, so upstream's OKF demo
cannot be pointed at this fork without a path-shape adapter. The projection layer
is not portable between them — the divergence table in the plan understated how
deep it goes.
