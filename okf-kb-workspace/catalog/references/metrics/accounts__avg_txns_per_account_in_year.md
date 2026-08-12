---
type: Metric
title: avg_txns_per_account_in_year (accounts)
description: Average transactions per account for a selected year, counted across ALL accounts (accounts
  with zero transactions in that year count as zero, not dropped).
tags:
- metric
- filtered_ratio
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

**Ratio over a filtered subset; the denominator must include rows with zero matches or the average is overstated.**

| | |
|---|---|
| Table | [accounts](../../tables/accounts.md) |
| Type | `filtered_ratio` |

Average transactions per account for a selected year, counted across ALL accounts (accounts with zero transactions in that year count as zero, not dropped). Set the selected_year parameter; do NOT put txn_date in a WHERE clause (that would drop zero-transaction accounts).

> **Precondition — de-duplicate `accounts` first.** One row per `account_id` ordered by `load_batch_id`. Computed over the raw table this measure is overstated.
