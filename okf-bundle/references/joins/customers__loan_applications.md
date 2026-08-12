---
type: Join
title: "customers \u2192 loan_applications"
description: One customer applied_for many loan_applications rows, joined on customer_id.
tags:
- join
- one-to-many
- customers
- loan_applications
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T00:00:00+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

`customers` **one-to-many** `loan_applications`.

| | |
|---|---|
| Parent | [customers](../../tables/customers.md) (`customer_id`) |
| Child | [loan_applications](../../tables/loan_applications.md) (`customer_id`) |
| Cardinality | **1:N** — one parent row, many child rows |

```sql
customers.customer_id = loan_applications.customer_id
```

**Fan-out.** Because this is 1:N, joining loan_applications to customers repeats each customer row once per matching loan_applications row. Any measure on `customers` aggregated *after* this join is multiplied by the child count. Aggregate each side separately and join the pre-aggregated results on `customer_id`.
