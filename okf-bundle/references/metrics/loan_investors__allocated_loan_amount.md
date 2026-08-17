---
type: Metric
title: allocated_loan_amount (loan_investors)
description: allocated sum measure on loan_investors.
tags:
- metric
- allocated_sum
- loan_investors
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
| Table | [loan_investors](/tables/loan_investors.md) |
| Type | `allocated_sum` |
| `amount_table` | `loan_applications` |
| `amount_column` | `amount` |
| `weight` | `owner_count` |
