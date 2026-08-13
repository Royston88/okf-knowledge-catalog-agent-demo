---
type: Join
title: accounts → balance_snapshots
description: One account snapshotted many balance_snapshots rows, joined on account_id.
tags:
- join
- one-to-many
- accounts
- balance_snapshots
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T00:00:00+00:00'
verified:
- by: human:kenly@google.com
  at: '2026-08-13T00:00:00+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

`accounts` **one-to-many** `balance_snapshots`.

| | |
|---|---|
| Parent | [accounts](../../tables/accounts.md) (`account_id`) |
| Child | [balance_snapshots](../../tables/balance_snapshots.md) (`account_id`) |
| Cardinality | **1:N** — one parent row, many child rows |

```sql
accounts.account_id = balance_snapshots.account_id
```

**Fan-out.** Because this is 1:N, joining balance_snapshots to accounts repeats each account row once per matching balance_snapshots row. Any measure on `accounts` aggregated *after* this join is multiplied by the child count. Aggregate each side separately and join the pre-aggregated results on `account_id`.

> **accounts must be de-duplicated first.** It carries duplicate loads; take one row per `account_id` ordered by `load_batch_id` before aggregating, or every measure over it is overstated.
