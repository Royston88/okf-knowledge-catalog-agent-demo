---
type: Metric
title: max_wire_amount (wire_transfers)
description: aggregate measure on wire_transfers.
tags:
- metric
- aggregate
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

**Plain aggregate.**

| | |
|---|---|
| Table | [wire_transfers](../../tables/wire_transfers.md) |
| Type | `aggregate` |
| `column` | `amount` |
| `agg` | `max` |
