---
type: Join
title: loan_applications ↔ investors (via loan_investors)
description: loan_applications and investors are many-to-many; loan_investors is the bridge that resolves
  them.
tags:
- join
- many-to-many
- bridge
- loan_applications
- investors
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

`loan_applications` **many-to-many** `investors`, resolved through the bridge [loan_investors](/tables/loan_investors.md).

| | |
|---|---|
| Side A | [loan_applications](/tables/loan_applications.md) (`application_id`) |
| Side B | [investors](/tables/investors.md) (`investor_id`) |
| Bridge | [loan_investors](/tables/loan_investors.md) |
| Cardinality | **M:N** |
| Allocation | `count_once` — how a measure on `loan_applications` is apportioned across the bridge |

```sql
loan_applications.application_id = loan_investors.application_id
  AND loan_investors.investor_id = investors.investor_id
```

**Double counting.** Traversing the bridge repeats each `loan_applications` row once per related `investors` row (and vice versa). A plain `SUM` over `loan_applications` across this join double counts. The declared treatment is `count_once`: count each loan_application once rather than once per partner.
