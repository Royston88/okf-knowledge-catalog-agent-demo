---
type: Metric
title: balance_period_end (balance_snapshots)
description: Total account balance AS OF the single most recent monthly snapshot (period-end stock; summed
  across accounts, never summed across months).
tags:
- metric
- semi_additive
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

****Semi-additive** — additive across every dimension EXCEPT the period. Pick a single period; summing across periods double counts.**

| | |
|---|---|
| Table | [balance_snapshots](/tables/balance_snapshots.md) |
| Type | `semi_additive` |
| `column` | `balance` |
| `period` | `snapshot_month` |

Total account balance AS OF the single most recent monthly snapshot (period-end stock; summed across accounts, never summed across months). For a specific or per-month total, group total_snapshot_balance by snapshot_month instead.

> **Precondition — single period.** `balance_snapshots` is a snapshot keyed on `account_id` per `snapshot_month`. Constrain to one `snapshot_month`; summing across periods counts the same balance_snapshot repeatedly.
