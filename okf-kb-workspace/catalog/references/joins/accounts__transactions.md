---
type: Join
title: accounts → transactions
description: One account has_txn many transactions rows, joined on account_id.
tags:
- join
- one-to-many
- accounts
- transactions
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T00:00:00+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

`accounts` **one-to-many** `transactions`.

| | |
|---|---|
| Parent | [accounts](../../tables/accounts.md) (`account_id`) |
| Child | [transactions](../../tables/transactions.md) (`account_id`) |
| Cardinality | **1:N** — one parent row, many child rows |

```sql
accounts.account_id = transactions.account_id
```

**Fan-out.** Because this is 1:N, joining transactions to accounts repeats each account row once per matching transactions row. Any measure on `accounts` aggregated *after* this join is multiplied by the child count. Aggregate each side separately and join the pre-aggregated results on `account_id`.

> **accounts must be de-duplicated first.** It carries duplicate loads; take one row per `account_id` ordered by `load_batch_id` before aggregating, or every measure over it is overstated.
