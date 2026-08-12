---
type: Metric
title: total_txn_amount (transactions)
description: additive measure on transactions.
tags:
- metric
- additive
- transactions
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
| Table | [transactions](../../tables/transactions.md) |
| Type | `additive` |
| `column` | `amount` |
