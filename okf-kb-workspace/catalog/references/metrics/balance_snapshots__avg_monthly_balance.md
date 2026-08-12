---
type: Metric
title: avg_monthly_balance (balance_snapshots)
description: 'Average monthly TOTAL account balance across the snapshot history: sum balance per snapshot
  month, then average those monthly totals.'
tags:
- metric
- semi_additive_avg
- balance_snapshots
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T00:00:00+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

****Semi-additive average** — average the per-period totals; do not average the raw rows.**

| | |
|---|---|
| Table | [balance_snapshots](../../tables/balance_snapshots.md) |
| Type | `semi_additive_avg` |
| `column` | `balance` |
| `period` | `snapshot_month` |

Average monthly TOTAL account balance across the snapshot history: sum balance per snapshot month, then average those monthly totals.

> **Precondition — single period.** `balance_snapshots` is a snapshot keyed on `account_id` per `snapshot_month`. Constrain to one `snapshot_month`; summing across periods counts the same balance_snapshot repeatedly.
