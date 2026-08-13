---
title: Investors
description: Details of individuals and institutional entities investing in loan portfolios.
tags:
  - investment
  - party-dimension
  - loan-funding
type: dataplex-types.global.bigquery-table
catalogEntry:
  name: bigquery/royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy/investors
  resource:
    name: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/investors
  aspects:
    royston-dev-8253.us.okf:
      okf_type: BigQuery Table
      generated:
        by: reference_agent/gemini-3.5-flash
        at: 2026-08-12T20:53:36+00:00
      sources:
        - resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/investors
          id: bq-metadata
          title: BigQuery Table Metadata and Data Profile
---

The `investors` table provides dimensional data for 40 individuals and institutional entities that fund loan portfolios managed by Cymbal Bank[^bq-metadata]. The grain of this dimension is one row per investor, uniquely identified by `investor_id`[^bq-metadata].

The table classifies investors into four categories: individual `retail` investors (15 rows, 37.5%), and institutional investors comprising `insurer` (12 rows, 30.0%), `fund` (9 rows, 22.5%), and `bank` (4 rows, 10.0%) entities[^bq-metadata]. This categorization enables the analysis of funding diversification and risk concentration across different types of market participants.

This table serves as a reference dimension and is designed to be joined with the [loan_investors](loan_investors.md) table to map specific loan funding obligations to their respective funding entities[^bq-metadata]. The parent dataset containing this table is [cymbal_bank_v6z_scaffold_demo_copy](../datasets/cymbal_bank_v6z_scaffold_demo_copy.md).

# Schema

| Field Name | Type | Mode | Description |
| :--- | :--- | :--- | :--- |
| **investor_id** | INTEGER | NULLABLE | Unique identifier for each investor (primary key)[^bq-metadata]. |
| **name** | STRING | NULLABLE | The full legal or corporate name of the investor[^bq-metadata]. |
| **investor_type** | STRING | NULLABLE | The category of investor (`retail`, `insurer`, `fund`, or `bank`)[^bq-metadata]. |

# Common query patterns

### 1. Count of investors by investor type
This query aggregates the investor counts by their types to understand the distribution of retail versus institutional investors.

```sql
SELECT
  investor_type,
  COUNT(*) AS investor_count
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.investors`
GROUP BY
  investor_type
ORDER BY
  investor_count DESC;
```

### 2. Identify investment participation by investor
This query joins the `investors` table with the [loan_investors](loan_investors.md) table to list each investor, the count of loan commitments they hold, and their average allocation percentage.

```sql
SELECT
  i.investor_id,
  i.name,
  i.investor_type,
  COUNT(li.application_id) AS funded_applications_count,
  ROUND(AVG(li.allocation_pct) * 100, 2) AS avg_allocation_percentage
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.investors` AS i
LEFT JOIN
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_investors` AS li
ON
  i.investor_id = li.investor_id
GROUP BY
  i.investor_id,
  i.name,
  i.investor_type
ORDER BY
  funded_applications_count DESC;
```

[^bq-metadata]: BigQuery Table Metadata and Data Profile for `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.investors`.
