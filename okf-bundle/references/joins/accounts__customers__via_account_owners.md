---
type: Join
title: accounts ↔ customers (via account_owners)
description: accounts and customers are many-to-many; account_owners is the bridge that resolves them.
tags:
- join
- many-to-many
- bridge
- accounts
- customers
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T00:00:00+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

`accounts` **many-to-many** `customers`, resolved through the bridge [account_owners](../../tables/account_owners.md).

| | |
|---|---|
| Side A | [accounts](../../tables/accounts.md) (`account_id`) |
| Side B | [customers](../../tables/customers.md) (`customer_id`) |
| Bridge | [account_owners](../../tables/account_owners.md) |
| Cardinality | **M:N** |
| Allocation | `count_once` — how a measure on `accounts` is apportioned across the bridge |

```sql
accounts.account_id = account_owners.account_id
  AND account_owners.customer_id = customers.customer_id
```

**Double counting.** Traversing the bridge repeats each `accounts` row once per related `customers` row (and vice versa). A plain `SUM` over `accounts` across this join double counts. The declared treatment is `count_once`: count each account once rather than once per partner.


> **accounts must be de-duplicated first.** It carries duplicate loads; take one row per `account_id` ordered by `load_batch_id` before aggregating, or every measure over it is overstated.
