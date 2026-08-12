---
type: Metric
title: txn_amount_3mo_moving_avg (transactions)
description: moving avg measure on transactions.
tags:
- metric
- moving_avg
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

**Moving average over the declared window.**

| | |
|---|---|
| Table | [transactions](../../tables/transactions.md) |
| Type | `moving_avg` |
| `column` | `amount` |
| `order_by` | `txn_date` |
| `window` | `3` |
