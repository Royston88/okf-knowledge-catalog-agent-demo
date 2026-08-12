---
type: BigQuery Table
resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/customers
title: Customers
description: Contains demographic, geographic, and account segment profiles for Cymbal
  Bank customers, including referral connections.
tags:
- customers
- demographics
- core-entities
generated:
  by: reference_agent/gemini-3.5-flash
  at: '2026-08-12T20:53:12+00:00'
sources:
- id: bq-metadata
  resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/customers
  title: BigQuery Table Metadata for customers
---

The `customers` table is a core dimension table in the [cymbal_bank_v6z_scaffold_demo_copy](../datasets/cymbal_bank_v6z_scaffold_demo_copy.md) dataset, containing profile and demographic details for Cymbal Bank customers[^bq-metadata]. The grain of this table is **one row per customer** (uniquely identified by `customer_id`)[^bq-metadata]. 

The table tracks customer tier classifications (ranging from mass-market retail to high-net-worth private tiers), registration signup dates, geographic regions, and customer-to-customer referral links[^bq-metadata]. 

This table is frequently joined with other analytical tables such as [accounts](accounts.md) and [account_owners](account_owners.md) to map ownership, [customer_segment_history](customer_segment_history.md) to track tier transitions, or [loan_applications](loan_applications.md) and [payments](payments.md) to attribute financial transactions to demographic segments.

# Schema

The table contains 500 rows with the following schema[^bq-metadata]:

| Field Name | Type | Mode | Description |
| :--- | :--- | :--- | :--- |
| `customer_id` | INTEGER | NULLABLE | Unique identifier for each customer. Serves as the primary key. |
| `name` | STRING | NULLABLE | Full name of the customer. |
| `segment` | STRING | NULLABLE | Customer tier segment. Standard values are `retail` (~71.0%), `premier` (~25.2%), and `private` (~3.8%)[^bq-metadata]. |
| `region` | STRING | NULLABLE | Geographic region of the customer (e.g., Northwest, Midwest, Northeast, Southwest, West, Southeast). |
| `signup_date` | DATE | NULLABLE | The date the customer registered with Cymbal Bank. |
| `referred_by` | INTEGER | NULLABLE | The `customer_id` of the referring customer. Approximately 37% of customers have no referrer (`NULL`)[^bq-metadata]. |
| `state` | STRING | NULLABLE | State of residence for the customer. |
| `city` | STRING | NULLABLE | City of residence for the customer. |

# Common query patterns

### 1. Customer breakdown by tier segment and region
This query aggregates customer distribution across segments and geographic regions to identify geographic concentrations of high-tier customers.

```sql
SELECT
  segment,
  region,
  COUNT(*) AS customer_count
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customers`
GROUP BY
  1, 2
ORDER BY
  segment ASC,
  customer_count DESC;
```

### 2. Analysis of the customer referral network
This query identifies the top customers who have referred other customers, tracking the success of the peer referral program.

```sql
SELECT
  referrer.customer_id AS referrer_id,
  referrer.name AS referrer_name,
  COUNT(referee.customer_id) AS referral_count
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customers` AS referee
JOIN
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customers` AS referrer
ON
  referee.referred_by = referrer.customer_id
GROUP BY
  1, 2
ORDER BY
  referral_count DESC
LIMIT 10;
```

### 3. Customer signup trends over time
This query details customer signup volume and tier distribution by calendar year.

```sql
SELECT
  EXTRACT(YEAR FROM signup_date) AS signup_year,
  segment,
  COUNT(*) AS signup_count
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customers`
GROUP BY
  1, 2
ORDER BY
  signup_year DESC,
  segment ASC;
```

[^bq-metadata]: BigQuery Table Metadata for customers: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/customers
