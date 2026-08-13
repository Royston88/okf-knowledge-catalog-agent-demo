---
type: BigQuery Table
resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/calendar
title: Calendar
description: A standard reference dimension table containing calendar and fiscal date attributes from
  May 1, 2023, through April 30, 2026.
tags:
- reference
- dimension
- time
- fiscal
generated:
  by: reference_agent/gemini-3.5-flash
  at: '2026-08-12T20:51:49+00:00'
verified:
- by: human:kenly@google.com
  at: '2026-08-13T00:00:00+00:00'
sources:
- id: bq-metadata
  resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/calendar
  title: BigQuery Table Metadata and Schema
---

The `calendar` table is a reference dimension table representing daily date attributes for Cymbal Bank's financial, operational, and analytical reporting. It covers a range from May 1, 2023, through April 30, 2026 [^bq-metadata]. Every row in this table represents a single day (one row per day grain) [^bq-metadata], mapping its calendar date to relevant temporal attributes such as day of week, fiscal quarter, and calendar quarter, and indicating whether the date is a holiday.

This dimension table is commonly joined with transaction-oriented or snapshot tables—such as [transactions](transactions.md) or [balance_snapshots](balance_snapshots.md)—to perform time-series analysis, cohort reporting, or to group activity by fiscal quarters rather than calendar months. The parent dataset is [cymbal_bank_v6z_scaffold_demo_copy](../datasets/cymbal_bank_v6z_scaffold_demo_copy.md).

### Fiscal Calendar Alignment
Cymbal Bank's fiscal year runs on a shifted schedule, beginning on February 1st and ending on January 31st of the following calendar year [^bq-metadata]. Under this schedule, the fiscal year is labeled based on the calendar year in which it ends (for example, May 5, 2023, falls in `FY2024-Q2` [^bq-metadata]).

# Schema

| Field | Type | Description |
|---|---|---|
| `cal_date` | DATE | The calendar date. This is the unique primary key of the table (one row per date) [^bq-metadata]. |
| `cal_year` | INTEGER | The calendar year (e.g., 2023, 2024, 2025, 2026) [^bq-metadata]. |
| `cal_quarter` | STRING | The calendar quarter (e.g., `Q1`, `Q2`, `Q3`, `Q4`) [^bq-metadata]. |
| `fiscal_quarter` | STRING | The fiscal quarter formatted as `FYYYYY-QX` (e.g., `FY2024-Q2`) [^bq-metadata]. |
| `is_holiday` | BOOLEAN | A flag indicating whether the date is a recognized holiday [^bq-metadata]. |
| `day_of_week` | STRING | Three-letter abbreviation of the weekday (e.g., `Mon`, `Tue`) [^bq-metadata]. |

# Common query patterns

### Pattern 1: Find all holidays in Q4 of calendar year 2024

This query retrieves all holiday dates and their days of week for a specific calendar quarter, which is useful for operational planning.

```sql
SELECT 
  cal_date, 
  day_of_week, 
  fiscal_quarter
FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.calendar`
WHERE cal_year = 2024 
  AND cal_quarter = 'Q4'
  AND is_holiday = TRUE
ORDER BY cal_date;
```

### Pattern 2: Aggregate transaction volumes by fiscal quarter

This pattern joins the `calendar` dimension with the [transactions](transactions.md) table to analyze total transaction volume and account activity grouped by fiscal quarters.

```sql
SELECT 
  c.fiscal_quarter,
  SUM(t.amount) AS total_amount,
  COUNT(DISTINCT t.account_id) AS active_accounts,
  COUNT(t.transaction_id) AS transaction_count
FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.transactions` AS t
JOIN `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.calendar` AS c
  ON t.txn_date = c.cal_date
GROUP BY c.fiscal_quarter
ORDER BY c.fiscal_quarter;
```

### Pattern 3: Compare transaction behavior on holidays vs. business days

This query compares the average transaction amount and transaction count on bank holidays versus normal business days.

```sql
SELECT 
  c.is_holiday,
  COUNT(t.transaction_id) AS total_transactions,
  AVG(t.amount) AS average_transaction_amount
FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.transactions` AS t
JOIN `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.calendar` AS c
  ON t.txn_date = c.cal_date
GROUP BY c.is_holiday;
```

[^bq-metadata]: BigQuery Table Metadata and Schema for `calendar` (royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.calendar).
