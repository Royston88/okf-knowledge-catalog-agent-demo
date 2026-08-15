---
type: Join
title: customers → payments
description: One customer made many payments rows, joined on customer_id.
tags:
- join
- one-to-many
- customers
- payments
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T00:00:00+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

`customers` **one-to-many** `payments`.

| | |
|---|---|
| Parent | [customers](/tables/customers.md) (`customer_id`) |
| Child | [payments](/tables/payments.md) (`customer_id`) |
| Cardinality | **1:N** — one parent row, many child rows |

```sql
customers.customer_id = payments.customer_id
```

**Fan-out.** Because this is 1:N, joining payments to customers repeats each customer row once per matching payments row. Any measure on `customers` aggregated *after* this join is multiplied by the child count. Aggregate each side separately and join the pre-aggregated results on `customer_id`.
