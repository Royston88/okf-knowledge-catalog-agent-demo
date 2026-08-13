---
type: Metric
title: total_loan_amount (loan_applications)
description: additive measure on loan_applications.
tags:
- metric
- additive
- loan_applications
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T00:00:00+00:00'
verified:
- by: human:kenly@google.com
  at: '2026-08-13T00:00:00+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

**Additive — safe to SUM across every dimension.**

| | |
|---|---|
| Table | [loan_applications](../../tables/loan_applications.md) |
| Type | `additive` |
| `column` | `amount` |
