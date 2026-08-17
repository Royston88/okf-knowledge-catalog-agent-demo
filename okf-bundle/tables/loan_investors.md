---
type: BigQuery Table
resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/loan_investors
title: Loan Investors
description: A junction table that records the financial allocation and participation tier of institutional
  investors in loan applications.
tags:
- loans
- investors
- allocations
- participation
status: stable
generated:
  by: reference_agent/gemini-3.5-flash
  at: '2026-08-12T20:55:35+00:00'
verified:
- by: human:kenly@google.com
  at: '2026-08-13T00:00:00+00:00'
stale_after: '2026-11-13'
sources:
- id: royston-dev-8253-cymbal-bank-loan-investors
  resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/loan_investors
  title: BigQuery Table royston-dev-8253:cymbal_bank_v6z_scaffold_demo_copy.loan_investors
---

The `loan_investors` table functions as a junction table establishing the relationships between loan applications and the institutional investors who fund them. Each row in this table represents a single investor's financial commitment and specific role in a syndicated or co-invested loan transaction[^royston-dev-8253-cymbal-bank-loan-investors].

### Key Characteristics

- **Grain**: One row per investor per loan application (uniquely defined by the combination of `application_id` and `investor_id`). 
- **Syndication Model**: Loans are frequently syndicated among multiple institutions. This means a single loan application in [loan_applications](/tables/loan_applications.md) can map to multiple records in this table, representing multiple investors who split the financial backing.
- **Participation Distribution**: The syndicate structure is represented by three tiers: `lead` (the coordinating institution, appearing in 800 records), `co-lead` (secondary lead institutions, appearing in 626 records), and `participant` (passive backers, appearing in 593 records)[[^royston-dev-8253-cymbal-bank-loan-investors]].
- **Allocation and Funding**: The `allocation_pct` field specifies the proportion of the total loan funded by the investor (e.g., `1.0` representing a 100% solo allocation, or fractional values like `0.3732` representing 37.32%). The most frequent single allocation value is `1.0`, occurring in 174 instances, signifying cases where a single investor fully funds the loan.

This table is critical for analyzing investor portfolio exposure, assessing syndicate health, and auditing funding allocations within the [cymbal_bank_v6z_scaffold_demo_copy](/datasets/cymbal_bank_v6z_scaffold_demo_copy.md) dataset. It links directly to the [investors](/tables/investors.md) details table.

# Related concepts

_Generated from the concepts that reference this table — see `okf-review/postauthor.py`._

## Joins
* [loan_applications ↔ investors (via loan_investors)](/references/joins/loan_applications__investors__via_loan_investors.md) - loan_applications and investors are many-to-many; loan_investors is the bridge that resolves them.

## Metrics
* [allocated_loan_amount (loan_investors)](/references/metrics/loan_investors__allocated_loan_amount.md) - allocated sum measure on loan_investors.

# Schema

| Field Name | Type | Mode | Description |
| :--- | :---: | :---: | :--- |
| **application_id** | INTEGER | NULLABLE | The unique identifier of the syndicated loan application, linking to [loan_applications](/tables/loan_applications.md). |
| **investor_id** | INTEGER | NULLABLE | The unique identifier of the institutional investor, linking to [investors](/tables/investors.md). |
| **allocation_pct** | FLOAT | NULLABLE | The percentage of the loan funded by the investor (e.g., `1.0` for 100% or `0.3732` for 37.32%). |
| **participation_tier** | STRING | NULLABLE | The role of the investor in the loan syndicate. Standard values are `lead`, `co-lead`, and `participant`. |

# Data characteristics

_Computed from BigQuery on 2026-08-15 by `okf-review/mirror.py`. The warehouse is authoritative for this section — it is a cache, not an assertion, and a refresh overwrites it._

**2,019 rows.**

| Column | Nulls | Distinct | Range / top values |
| :--- | ---: | ---: | :--- |
| `application_id` | 0 | 800 | 1 – 800 |
| `investor_id` | 0 | 40 | 1 – 40 |
| `allocation_pct` | 0 | 1,608 | 0.04 – 1.00 |
| `participation_tier` | 0 | 3 | `lead` 39.6%, `co-lead` 31.0%, `participant` 29.4% |

> **2,019 rows, 800 distinct `application_id`.** The row count is not the entity count; de-duplicate before aggregating.

# Common query patterns

### 1. View syndicate composition for a specific loan
Retrieve all participating investors, their allocation shares, and syndicate roles for a particular loan application:

```sql
SELECT 
  li.application_id,
  i.name AS investor_name,
  li.participation_tier,
  li.allocation_pct
FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_investors` li
JOIN `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.investors` i
  ON li.investor_id = i.investor_id
WHERE li.application_id = 4
ORDER BY li.allocation_pct DESC;
```

### 2. Investor exposure and role distribution
Analyze each investor's overall loan portfolio involvement, average allocation percentage, and syndicate tier distribution:

```sql
SELECT 
  investor_id,
  COUNT(DISTINCT application_id) AS total_loans_participated,
  ROUND(AVG(allocation_pct) * 100, 2) AS avg_allocation_percentage,
  COUNTIF(participation_tier = 'lead') AS lead_roles,
  COUNTIF(participation_tier = 'co-lead') AS co_lead_roles,
  COUNTIF(participation_tier = 'participant') AS participant_roles
FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_investors`
GROUP BY investor_id
ORDER BY total_loans_participated DESC;
```

### 3. Verify total allocation integrity
Check for any syndicated loans where the sum of allocations does not equal exactly 100% (allowing for minor floating-point precision differences):

```sql
SELECT 
  application_id,
  COUNT(investor_id) AS total_investors,
  ROUND(SUM(allocation_pct), 4) AS total_allocation
FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_investors`
GROUP BY application_id
HAVING total_allocation NOT BETWEEN 0.9999 AND 1.0001
ORDER BY total_allocation DESC;
```

[^royston-dev-8253-cymbal-bank-loan-investors]: BigQuery table metadata and schema from `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_investors`.
