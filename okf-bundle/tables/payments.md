---
type: BigQuery Table
resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/payments
title: Payments
description: A ledger of customer payment transactions across multiple channels (ACH, card, Zelle, wire,
  and check).
tags:
- payments
- transaction-ledger
- billing
generated:
  by: reference_agent/gemini-3.5-flash
  at: '2026-08-12T20:56:18+00:00'
verified:
- by: human:kenly@google.com
  at: '2026-08-13T00:00:00+00:00'
sources:
- id: bq-metadata
  resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/payments
  title: BigQuery Table Metadata and Data Profile
---

The `payments` table is a ledger of outgoing or incoming payment transactions initiated by customers within the [cymbal_bank_v6z_scaffold_demo_copy](../datasets/cymbal_bank_v6z_scaffold_demo_copy.md) dataset[^bq-metadata]. The grain of this table is one row per individual payment transaction, uniquely identified by a near-unique `payment_id`[^bq-metadata]. The dataset captures a historical range of 8,000 payments spanning from early 2024 through mid-2026[^bq-metadata].

Each payment record maps to a specific customer using the `customer_id` field, allowing direct joins with the [customers](customers.md) table[^bq-metadata]. Transactions are routed through five primary payment channels: ACH, credit cards, Zelle, wire transfers, and checks[^bq-metadata]. The table also pre-truncates transaction dates into the `payment_month` field, which simplifies monthly partition-based reporting and aggregated volume analysis[^bq-metadata].

# Schema

| Field | Type | Mode | Description |
| :--- | :--- | :--- | :--- |
| `payment_id` | INTEGER | NULLABLE | Primary identifier for the payment. This field is near-unique, with a 99.96% distinctness ratio across the 8,000 total rows[^bq-metadata]. |
| `customer_id` | INTEGER | NULLABLE | Foreign key referencing the `customer_id` in the [customers](customers.md) table[^bq-metadata]. |
| `amount` | FLOAT | NULLABLE | The dollar value of the processed payment[^bq-metadata]. |
| `payment_date` | DATE | NULLABLE | The specific calendar date on which the payment transaction occurred[^bq-metadata]. |
| `payment_month` | DATE | NULLABLE | The calendar date representing the first day of the transaction's month, useful for monthly aggregation[^bq-metadata]. |
| `channel` | STRING | NULLABLE | The channel or method through which the payment was completed. Supported values include: `ach` (33.7%), `card` (30.3%), `zelle` (13.7%), `wire` (12.3%), and `check` (10.1%)[^bq-metadata]. |

# Common query patterns

### 1. Monthly payment volume and counts by channel
This query aggregates total payment volumes and transaction counts by payment month and channel to track seasonal trends and channel popularity.

```sql
SELECT
  payment_month,
  channel,
  COUNT(*) AS total_transactions,
  ROUND(SUM(amount), 2) AS total_amount
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.payments`
GROUP BY
  1, 2
ORDER BY
  payment_month DESC,
  total_amount DESC;
```

### 2. High-value customer payment details
This query joins payments with the [customers](customers.md) table to identify top-spending customers and their total payments.

```sql
SELECT
  p.customer_id,
  c.name,
  ROUND(SUM(p.amount), 2) AS total_paid,
  COUNT(p.payment_id) AS payment_count
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.payments` AS p
LEFT JOIN
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customers` AS c
  ON p.customer_id = c.customer_id
GROUP BY
  1, 2
ORDER BY
  total_paid DESC
LIMIT 10;
```

### 3. Payment size distribution by channel
This query computes the overall share and average amount for each payment channel, providing insight into which channels handle larger transactions.

```sql
SELECT
  channel,
  COUNT(*) AS payment_count,
  ROUND(SUM(amount), 2) AS total_amount,
  ROUND(AVG(amount), 2) AS average_amount,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) AS percentage_of_total_count
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.payments`
GROUP BY
  channel
ORDER BY
  payment_count DESC;
```

[^bq-metadata]: BigQuery Table Metadata and Data Profile for `cymbal_bank_v6z_scaffold_demo_copy.payments`.
