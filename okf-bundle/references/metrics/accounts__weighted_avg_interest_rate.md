---
type: Metric
title: weighted_avg_interest_rate (accounts)
description: rate measure on accounts.
tags:
- metric
- rate
- accounts
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T00:00:00+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

**Weighted rate — weight by the declared column, never a plain AVG.**

| | |
|---|---|
| Table | [accounts](/tables/accounts.md) |
| Type | `rate` |
| `column` | `interest_rate` |
| `weight_by` | `balance` |

> **Precondition — de-duplicate `accounts` first.** One row per `account_id` ordered by `load_batch_id`. Computed over the raw table this measure is overstated.
