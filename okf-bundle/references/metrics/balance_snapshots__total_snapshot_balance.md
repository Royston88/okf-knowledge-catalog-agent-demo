---
type: Metric
title: total_snapshot_balance (balance_snapshots)
description: Total snapshot balance summed across accounts WITHIN a snapshot month.
tags:
- metric
- additive
- balance_snapshots
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

**Additive — safe to SUM across every dimension.**

| | |
|---|---|
| Table | [balance_snapshots](../../tables/balance_snapshots.md) |
| Type | `additive` |
| `column` | `balance` |

Total snapshot balance summed across accounts WITHIN a snapshot month. Group by snapshot_month to get the month-end total for each month (e.g. the two most recent month-ends).

> **Precondition — single period.** `balance_snapshots` is a snapshot keyed on `account_id` per `snapshot_month`. Constrain to one `snapshot_month`; summing across periods counts the same balance_snapshot repeatedly.
