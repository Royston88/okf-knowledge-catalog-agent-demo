---
type: Join
title: customers → wire_transfers
description: One customer sent many wire_transfers rows, joined on customer_id.
tags:
- join
- one-to-many
- customers
- wire_transfers
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T00:00:00+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

`customers` **one-to-many** `wire_transfers`.

| | |
|---|---|
| Parent | [customers](../../tables/customers.md) (`customer_id`) |
| Child | [wire_transfers](../../tables/wire_transfers.md) (`customer_id`) |
| Cardinality | **1:N** — one parent row, many child rows |

```sql
customers.customer_id = wire_transfers.customer_id
```

**Fan-out.** Because this is 1:N, joining wire_transfers to customers repeats each customer row once per matching wire_transfers row. Any measure on `customers` aggregated *after* this join is multiplied by the child count. Aggregate each side separately and join the pre-aggregated results on `customer_id`.
