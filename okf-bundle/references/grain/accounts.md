---
type: Grain Rule
title: accounts grain
description: 'Grain rules for accounts: it carries duplicate loads and MUST be de-duplicated on `account_id`.'
tags:
- grain
- accounts
- dedup
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T20:55:30+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

**Duplicate loads — de-duplicate before any aggregate.**

| | |
|---|---|
| Table | [accounts](../../tables/accounts.md) |
| `partition_by` | `account_id` |
| `order_by` | `load_batch_id` |

Every measure over this table is overstated if computed on the raw rows, and every join to it fans out. Take one row per `account_id` first:

```sql
SELECT * FROM `@{bq_dataset}.accounts`
QUALIFY ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY load_batch_id) = 1
```
