---
type: Derived Table
title: loan_milestone_dates
description: 'Long-form view of loan_applications: one row per source row per applied_date/approved_date/funded_date/closed_date
  column, as (milestone, milestone_date).'
tags:
- derived
- unpivot
- loan_applications
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T20:55:30+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

**Unpivot — one row per source row per milestone column.**
| | |
|---|---|
| Source | [loan_applications](../../tables/loan_applications.md) |
| `milestone` | `applied_date` -> Applied, `approved_date` -> Approved, `funded_date` -> Funded, `closed_date` -> Closed |
| `milestone_date` | the value of that column |
| Carried through | `product_type` |
This view MULTIPLIES the source: 4 rows out per row in. Counting it counts milestones, not loan_applications rows — filter `milestone` before aggregating, or join it to a de-duplicated source.
```sql
  SELECT product_type, 'Applied' AS milestone, applied_date AS milestone_date FROM `@{bq_dataset}.loan_applications`
  UNION ALL
  SELECT product_type, 'Approved' AS milestone, approved_date AS milestone_date FROM `@{bq_dataset}.loan_applications`
  UNION ALL
  SELECT product_type, 'Funded' AS milestone, funded_date AS milestone_date FROM `@{bq_dataset}.loan_applications`
  UNION ALL
  SELECT product_type, 'Closed' AS milestone, closed_date AS milestone_date FROM `@{bq_dataset}.loan_applications`
```
