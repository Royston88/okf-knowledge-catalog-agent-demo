---
type: Metric
title: total_balance (accounts)
description: Sum of the CURRENT account balance across accounts.
tags:
- metric
- additive
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

**Additive — safe to SUM across every dimension.**

| | |
|---|---|
| Table | [accounts](../../tables/accounts.md) |
| Type | `additive` |
| `column` | `balance` |

Sum of the CURRENT account balance across accounts. For balance at a monthly snapshot use balance_period_end / avg_monthly_balance.

> **Precondition — de-duplicate `accounts` first.** One row per `account_id` ordered by `load_batch_id`. Computed over the raw table this measure is overstated.
