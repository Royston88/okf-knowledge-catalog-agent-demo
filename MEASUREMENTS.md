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
