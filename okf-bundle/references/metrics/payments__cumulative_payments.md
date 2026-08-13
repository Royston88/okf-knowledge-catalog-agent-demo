---
type: Metric
title: cumulative_payments (payments)
description: Running (cumulative) total of payment amount by month.
tags:
- metric
- cumulative
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

**Running total ordered by the declared column.**

| | |
|---|---|
| Table | [payments](../../tables/payments.md) |
| Type | `cumulative` |
| `column` | `amount` |
| `order_by` | `payment_month` |

Running (cumulative) total of payment amount by month. Lives in its OWN explore cumulative_payments_window; select the month dimension plus this measure there to get the full per-month running total series.
