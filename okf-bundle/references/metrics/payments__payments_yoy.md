---
type: Metric
title: payments_yoy (payments)
description: period over period measure on payments.
tags:
- metric
- period_over_period
- payments
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

**Period-over-period comparison against the same measure shifted one period.**

| | |
|---|---|
| Table | [payments](/tables/payments.md) |
| Type | `period_over_period` |
| `column` | `amount` |
| `period` | `year` |
| `base` | `total_payments` |
