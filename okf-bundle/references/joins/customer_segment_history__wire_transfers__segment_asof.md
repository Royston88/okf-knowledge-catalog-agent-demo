---
type: Join
title: customer_segment_history → wire_transfers (segment_asof)
description: One segment_version segment_at_wire many wire_transfers rows, joined on customer_id.
tags:
- join
- one-to-many
- customer_segment_history
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

`customer_segment_history` **one-to-many** `wire_transfers`.

| | |
|---|---|
| Parent | [customer_segment_history](../../tables/customer_segment_history.md) (`customer_id`) |
| Child | [wire_transfers](../../tables/wire_transfers.md) (`customer_id`) |
| Cardinality | **1:N** — one parent row, many child rows |
| Role | `segment_asof` — this table joins customer_segment_history more than once; pick the role deliberately |
| Effective-dated | `{'fact_date': 'sent_date', 'entity_key': 'customer_id', 'valid_from': 'valid_from', 'valid_to': 'valid_to'}` — pick the version valid at the reporting instant, not all versions |

```sql
customer_segment_history.customer_id = wire_transfers.customer_id
```

**Fan-out.** Because this is 1:N, joining wire_transfers to customer_segment_history repeats each segment_version row once per matching wire_transfers row. Any measure on `customer_segment_history` aggregated *after* this join is multiplied by the child count. Aggregate each side separately and join the pre-aggregated results on `customer_id`.
