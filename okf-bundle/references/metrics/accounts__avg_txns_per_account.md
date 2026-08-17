---
type: Metric
title: avg_txns_per_account (accounts)
description: Average number of transactions per account across ALL accounts, including accounts with zero
  transactions.
tags:
- metric
- ratio
- accounts
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

**Ratio — compute numerator and denominator separately, then divide. Never average a ratio.**

| | |
|---|---|
| Table | [accounts](/tables/accounts.md) |
| Type | `ratio` |
| `numerator` | `transactions.count` |
| `denominator` | `accounts.count` |

Average number of transactions per account across ALL accounts, including accounts with zero transactions.

> **Precondition — de-duplicate `accounts` first.** One row per `account_id` ordered by `load_batch_id`. Computed over the raw table this measure is overstated.
