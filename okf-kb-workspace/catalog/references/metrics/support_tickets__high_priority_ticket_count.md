---
type: Metric
title: high_priority_ticket_count (support_tickets)
description: aggregate measure on support_tickets.
tags:
- metric
- aggregate
- support_tickets
status: stable
generated:
  by: generate_models/okf
  at: '2026-08-12T00:00:00+00:00'
sources:
- id: spec
  resource: bq-modeling-spec://royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy
  title: Reviewed BI modeling spec (layer1_structure + layer2_semantics)
---

**Plain aggregate.**

| | |
|---|---|
| Table | [support_tickets](../../tables/support_tickets.md) |
| Type | `aggregate` |
| `column` | `ticket_id` |
| `agg` | `count_distinct` |
| `filter_field` | `priority` |
| `filter_value` | `5` |
