---
type: Metric
title: payment_amount_pct_by_channel (payments)
description: percent of total measure on payments.
tags:
- metric
- percent_of_total
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

**Share of a partition total.**

| | |
|---|---|
| Table | [payments](../../tables/payments.md) |
| Type | `percent_of_total` |
| `column` | `amount` |
| `partition_by` | `channel` |
