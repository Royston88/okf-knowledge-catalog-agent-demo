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
status: stable
generated:
  by: reference_agent/gemini-3.5-flash
  at: '2026-08-12T20:56:18+00:00'
verified:
- by: human:kenly@google.com
  at: '2026-08-13T00:00:00+00:00'
stale_after: '2026-11-13'
sources:
- id: bq-metadata
  resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/payments
  title: BigQuery Table Metadata and Data Profile
---

The `payments` table is a ledger of outgoing or incoming payment transactions initiated by customers within the [cymbal_bank_v6z_scaffold_demo_copy](/datasets/cymbal_bank_v6z_scaffold_demo_copy.md) dataset[^bq-metadata]. The grain of this table is one row per individual payment transaction, uniquely identified by a near-unique `payment_id`[^bq-metadata]. The dataset captures a historical range of 8,000 payments spanning from early 2024 through mid-2026[^bq-metadata].

Each payment record maps to a specific customer using the `customer_id` field, allowing direct joins with the [customers](/tables/customers.md) table[^bq-metadata]. Transactions are routed through five primary payment channels: ACH, credit cards, Zelle, wire transfers, and checks[^bq-metadata]. The table also pre-truncates transaction dates into the `payment_month` field, which simplifies monthly partition-based reporting and aggregated volume analysis[^bq-metadata].

# Related concepts

_Generated from the concepts that reference this table — see `okf-review/postauthor.py`._

## Joins
* [customers → payments](/references/joins/customers__payments.md) - One customer made many payments rows, joined on customer_id.

## Metrics
* [cumulative_payments (payments)](/references/metrics/payments__cumulative_payments.md) - Running (cumulative) total of payment amount by month.
* [payment_amount_pct_by_channel (payments)](/references/metrics/payments__payment_amount_pct_by_channel.md) - percent of total measure on payments.
* [payments_yoy (payments)](/references/metrics/payments__payments_yoy.md) - period over period measure on payments.
* [total_payments (payments)](/references/metrics/payments__total_payments.md) - additive measure on payments.

# Schema

| Field | Type | Mode | Description |
| :--- | :---: | :---: | :--- |
| `payment_id` | INTEGER | NULLABLE | Primary identifier for the payment. This field is near-unique, with a 99.96% distinctness ratio across the 8,000 total rows[^bq-metadata]. |
| `customer_id` | INTEGER | NULLABLE | Foreign key referencing the `customer_id` in the [customers](/tables/customers.md) table[^bq-metadata]. |
| `amount` | FLOAT | NULLABLE | The dollar value of the processed payment[^bq-metadata]. |
| `payment_date` | DATE | NULLABLE | The specific calendar date on which the payment transaction occurred[^bq-metadata]. |
| `payment_month` | DATE | NULLABLE | The calendar date representing the first day of the transaction's month, useful for monthly aggregation[^bq-metadata]. |
| `channel` | STRING | NULLABLE | The channel or method through which the payment was completed. Supported values include: `ach` (33.7%), `card` (30.3%), `zelle` (13.7%), `wire` (12.3%), and `check` (10.1%)[^bq-metadata]. |

# Data characteristics

_Computed from BigQuery on 2026-08-15 by `okf-review/mirror.py`. The warehouse is authoritative for this section — it is a cache, not an assertion, and a refresh overwrites it._

**8,000 rows.**

| Column | Nulls | Distinct | Range / top values |
| :--- | ---: | ---: | :--- |
| `payment_id` | 0 | 8,000 | 1 – 8,000 |
| `customer_id` | 0 | 500 | 1 – 500 |
| `amount` | 0 | 6,469 | 2.89 – 1,330.00 |
| `payment_date` | 0 | 851 | 2024-01-01 – 2026-04-30 |
| `payment_month` | 0 | 28 | 2024-01-01 – 2026-04-01 |
| `channel` | 0 | 5 | `ach` 33.7%, `card` 30.3%, `zelle` 13.7%, `wire` 12.2%, `check` 10.1% |

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
This query joins payments with the [customers](/tables/customers.md) table to identify top-spending customers and their total payments.

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
