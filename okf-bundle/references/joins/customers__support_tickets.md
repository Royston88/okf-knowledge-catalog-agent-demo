---
type: Join
title: customers → support_tickets
description: One customer opened many support_tickets rows, joined on customer_id.
tags:
- join
- one-to-many
- customers
- support_tickets
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

`customers` **one-to-many** `support_tickets`.

| | |
|---|---|
| Parent | [customers](../../tables/customers.md) (`customer_id`) |
| Child | [support_tickets](../../tables/support_tickets.md) (`customer_id`) |
| Cardinality | **1:N** — one parent row, many child rows |

```sql
customers.customer_id = support_tickets.customer_id
```

**Fan-out.** Because this is 1:N, joining support_tickets to customers repeats each customer row once per matching support_tickets row. Any measure on `customers` aggregated *after* this join is multiplied by the child count. Aggregate each side separately and join the pre-aggregated results on `customer_id`.
