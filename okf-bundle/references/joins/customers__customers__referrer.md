---
type: Join
title: customers → customers (referrer)
description: One customer referred_by many customers rows, joined on referred_by.
tags:
- join
- one-to-many
- customers
- customers
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T00:00:00+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

`customers` **one-to-many** `customers`.

| | |
|---|---|
| Parent | [customers](/tables/customers.md) (`customer_id`) |
| Child | [customers](/tables/customers.md) (`referred_by`) |
| Cardinality | **1:N** — one parent row, many child rows |
| Role | `referrer` — this table joins customers more than once; pick the role deliberately |

```sql
customers.customer_id = customers.referred_by
```

**Fan-out.** Because this is 1:N, joining customers to customers repeats each customer row once per matching customers row. Any measure on `customers` aggregated *after* this join is multiplied by the child count. Aggregate each side separately and join the pre-aggregated results on `referred_by`.
