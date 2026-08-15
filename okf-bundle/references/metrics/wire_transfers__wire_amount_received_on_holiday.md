---
type: Metric
title: wire_amount_received_on_holiday (wire_transfers)
description: Total wire amount for wires whose RECEIVED date fell on a bank holiday (filters total_wire_amount
  by the received_cal role-played calendar's is_holiday).
tags:
- metric
- filtered_sum
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

**Additive over a filtered subset.**

| | |
|---|---|
| Table | [wire_transfers](/tables/wire_transfers.md) |
| Type | `filtered_sum` |
| `column` | `amount` |
| `filter_field` | `received_cal.is_holiday` |
| `filter_value` | `Yes` |

Total wire amount for wires whose RECEIVED date fell on a bank holiday (filters total_wire_amount by the received_cal role-played calendar's is_holiday).
