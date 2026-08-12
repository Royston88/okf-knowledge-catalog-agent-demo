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
