---
type: BigQuery Table
resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/loan_applications
title: Loan Applications
description: Encompasses the application pipeline and lifecycle dates for bank loan products.
tags:
- loans
- applications
- credit
- analytics
status: stable
generated:
  by: reference_agent/gemini-3.5-flash
  at: '2026-08-12T20:54:54+00:00'
verified:
- by: human:kenly@google.com
  at: '2026-08-13T00:00:00+00:00'
sources:
- id: bq-schema
  resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/loan_applications
  title: BigQuery Table Metadata for cymbal_bank_v6z_scaffold_demo_copy.loan_applications
---

The `loan_applications` table records every loan application filed by clients of the bank, detailing the application's lifecycle, product category, and financial amounts [^bq-schema]. Each record represents a single unique loan application [^bq-schema], making the grain of the table one row per `application_id`. This table resides within the [cymbal_bank_v6z_scaffold_demo_copy](/datasets/cymbal_bank_v6z_scaffold_demo_copy.md) dataset and links directly to [customers](/tables/customers.md) via `customer_id` and to [loan_investors](/tables/loan_investors.md) via `application_id`.

The dataset captures the natural chronological progression of a loan through several milestones represented by dates: application, approval, funding, and closure [^bq-schema]. A substantial portion of loans remain active or are in progress, with approximately 21.3% of applications lacking an approval date, 33.1% lacking a funding date, and 76.4% lacking a closed date [^bq-schema]. The offered financial products span five distinct categories: mortgage, auto, personal, business, and student loans, with mortgages being the most frequently represented product type [^bq-schema].

# Related concepts

_Generated from the concepts that reference this table — see `okf-review/postauthor.py`._

## Grain rules
* [loan_applications grain](/references/grain/loan_applications.md) - Grain rules for loan_applications: it is an accumulating snapshot whose milestone columns fill in over time.

## Joins
* [customers → loan_applications](/references/joins/customers__loan_applications.md) - One customer applied_for many loan_applications rows, joined on customer_id.
* [loan_applications ↔ investors (via loan_investors)](/references/joins/loan_applications__investors__via_loan_investors.md) - loan_applications and investors are many-to-many; loan_investors is the bridge that resolves them.

## Metrics
* [avg_days_to_approve (loan_applications)](/references/metrics/loan_applications__avg_days_to_approve.md) - milestone lag measure on loan_applications.
* [avg_days_to_fund (loan_applications)](/references/metrics/loan_applications__avg_days_to_fund.md) - milestone lag measure on loan_applications.
* [total_loan_amount (loan_applications)](/references/metrics/loan_applications__total_loan_amount.md) - additive measure on loan_applications.

## Derived tables
* [loan_milestone_dates](/references/derived/loan_milestone_dates.md) - Long-form view of loan_applications: one row per source row per applied_date/approved_date/funded_date/closed_date column, as (milestone, milestone_date).

# Schema

| Field Name | Type | Mode | Description |
| :--- | :--- | :--- | :--- |
| `application_id` | INTEGER | NULLABLE | Unique identifier for each loan application (Primary Key). |
| `customer_id` | INTEGER | NULLABLE | Foreign key linking to the applicant in the [customers](/tables/customers.md) table. |
| `product_type` | STRING | NULLABLE | Category of loan product applied for (e.g., 'mortgage', 'auto', 'personal', 'business', 'student'). |
| `amount` | FLOAT | NULLABLE | The principal amount requested or granted for the loan. |
| `applied_date` | DATE | NULLABLE | The date when the application was formally submitted. |
| `approved_date` | DATE | NULLABLE | The date when the application was approved by the bank (Null if rejected or pending). |
| `funded_date` | DATE | NULLABLE | The date when the loan funds were disbursed to the applicant (Null if not yet funded). |
| `closed_date` | DATE | NULLABLE | The date when the loan was fully paid off, discharged, or written off (Null if still active). |

# Common query patterns

### 1. Loan application funnel conversion rates
This query calculates the progression of applications through each phase of the loan lifecycle (applied, approved, funded, closed) by product type.

```sql
SELECT
  product_type,
  COUNT(1) AS total_applied,
  COUNT(approved_date) AS total_approved,
  COUNT(funded_date) AS total_funded,
  COUNT(closed_date) AS total_closed,
  ROUND(COUNT(approved_date) / COUNT(1) * 100, 2) AS approval_rate_pct,
  ROUND(COUNT(funded_date) / COUNT(approved_date) * 100, 2) AS funding_rate_pct
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_applications`
GROUP BY
  product_type
ORDER BY
  total_applied DESC;
```

### 2. Average loan amount and duration to fund by product type
This query identifies the average size of funded loans and measures the average processing time (in days) between the application date and the funding date.

```sql
SELECT
  product_type,
  COUNT(1) AS funded_loans_count,
  ROUND(AVG(amount), 2) AS avg_funded_amount,
  ROUND(AVG(DATE_DIFF(funded_date, applied_date, DAY)), 1) AS avg_days_to_fund
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_applications`
WHERE
  funded_date IS NOT NULL
GROUP BY
  product_type
ORDER BY
  avg_funded_amount DESC;
```

[^bq-schema]: Derived from BigQuery table metadata and Dataplex data profile scan of `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_applications`.
