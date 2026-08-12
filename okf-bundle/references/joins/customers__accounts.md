---
type: Join
title: "customers \u2192 accounts"
description: One customer owns many accounts rows, joined on customer_id.
tags:
- join
- one-to-many
- customers
- accounts
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T00:00:00+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

`customers` **one-to-many** `accounts`.

| | |
|---|---|
| Parent | [customers](../../tables/customers.md) (`customer_id`) |
| Child | [accounts](../../tables/accounts.md) (`customer_id`) |
| Cardinality | **1:N** — one parent row, many child rows |

```sql
customers.customer_id = accounts.customer_id
```

**Fan-out.** Because this is 1:N, joining accounts to customers repeats each customer row once per matching accounts row. Any measure on `customers` aggregated *after* this join is multiplied by the child count. Aggregate each side separately and join the pre-aggregated results on `customer_id`.


> **accounts must be de-duplicated first.** It carries duplicate loads; take one row per `account_id` ordered by `load_batch_id` before aggregating, or every measure over it is overstated.
