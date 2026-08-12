---
type: Metric
title: avg_tickets_per_customer (customers)
description: ratio measure on customers.
tags:
- metric
- ratio
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

**Ratio — compute numerator and denominator separately, then divide. Never average a ratio.**

| | |
|---|---|
| Table | [customers](../../tables/customers.md) |
| Type | `ratio` |
| `numerator` | `support_tickets.count` |
| `denominator` | `customers.count` |
