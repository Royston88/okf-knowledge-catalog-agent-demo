---
type: Hierarchy
title: geography hierarchy
description: 'Drill path on customers: region > state > city. Roll up along these levels in order; skipping
  one double-counts or mixes grains.'
tags:
- hierarchy
- customers
- region
- state
- city
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T20:55:30+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

**Drill path — roll up in order.**

| | |
|---|---|
| Table | [customers](/tables/customers.md) |
| Levels | `region` > `state` > `city` |

Each level is contained by the one before it. Aggregating at a level means grouping by that level *and every level above it*, or rows from different parents collapse together.

```sql
SELECT region, state, city, COUNT(*) AS n
FROM `@{bq_dataset}.customers`
GROUP BY region, state, city
```
