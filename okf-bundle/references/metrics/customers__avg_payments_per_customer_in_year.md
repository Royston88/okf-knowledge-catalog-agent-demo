---
type: Metric
title: avg_payments_per_customer_in_year (customers)
description: filtered ratio measure on customers.
tags:
- metric
- filtered_ratio
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

**Ratio over a filtered subset; the denominator must include rows with zero matches or the average is overstated.**

| | |
|---|---|
| Table | [customers](../../tables/customers.md) |
| Type | `filtered_ratio` |
