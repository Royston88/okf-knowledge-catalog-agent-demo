---
type: Join
title: calendar → wire_transfers (sent_cal)
description: One calendar_day wire_sent_on many wire_transfers rows, joined on sent_date.
tags:
- join
- one-to-many
- calendar
- wire_transfers
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

`calendar` **one-to-many** `wire_transfers`.

| | |
|---|---|
| Parent | [calendar](../../tables/calendar.md) (`cal_date`) |
| Child | [wire_transfers](../../tables/wire_transfers.md) (`sent_date`) |
| Cardinality | **1:N** — one parent row, many child rows |
| Role | `sent_cal` — this table joins calendar more than once; pick the role deliberately |

```sql
calendar.cal_date = wire_transfers.sent_date
```

**Fan-out.** Because this is 1:N, joining wire_transfers to calendar repeats each calendar_day row once per matching wire_transfers row. Any measure on `calendar` aggregated *after* this join is multiplied by the child count. Aggregate each side separately and join the pre-aggregated results on `sent_date`.
