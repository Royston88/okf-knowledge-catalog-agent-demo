---
type: Metric
title: allocated_account_balance (account_owners)
description: Account balance split EQUALLY among the account's owners, attributable by ownership_role
  (primary vs joint).
tags:
- metric
- allocated_sum
- account_owners
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T00:00:00+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

****Allocated** across a many-to-many bridge — apportion, do not SUM.**

| | |
|---|---|
| Table | [account_owners](/tables/account_owners.md) |
| Type | `allocated_sum` |
| `amount_table` | `accounts` |
| `amount_column` | `balance` |
| `weight` | `owner_count` |

Account balance split EQUALLY among the account's owners, attributable by ownership_role (primary vs joint).
