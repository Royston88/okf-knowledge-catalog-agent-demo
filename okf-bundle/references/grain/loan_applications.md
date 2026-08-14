---
type: Grain Rule
title: loan_applications grain
description: 'Grain rules for loan_applications: it is an accumulating snapshot whose milestone columns
  fill in over time.'
tags:
- grain
- loan_applications
- accumulating
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T20:55:30+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

**Accumulating snapshot — milestone columns fill in over time.**

| | |
|---|---|
| Table | [loan_applications](../../tables/loan_applications.md) |
| `milestones` | `applied_date`, `approved_date`, `funded_date`, `closed_date` |

A row is rewritten as it progresses, so a NULL milestone means *not reached yet*, not *missing data*. Durations are differences between milestone columns on the same row; filter on the milestone you mean rather than on row creation.
