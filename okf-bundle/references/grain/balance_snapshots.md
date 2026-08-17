---
type: Grain Rule
title: balance_snapshots grain
description: 'Grain rules for balance_snapshots: it is a periodic snapshot at one row per `account_id`
  per `snapshot_month`.'
tags:
- grain
- balance_snapshots
- snapshot
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T20:55:30+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

**Periodic snapshot — semi-additive over time.**

| | |
|---|---|
| Table | [balance_snapshots](/tables/balance_snapshots.md) |
| `entity_key` | `account_id` |
| `period` | `snapshot_month` |

The grain is one row per `account_id` per `snapshot_month`. Balances SUM across entities within a period and MUST NOT be summed across periods — total per `snapshot_month` first, then average those totals.
