---
type: BigQuery Table
resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/transactions
title: Transactions
description: Transaction-level ledger records of financial activities for bank accounts.
tags:
- transactions
- ledger
- financial
- cymbal-bank
status: stable
generated:
  by: reference_agent/gemini-3.5-flash
  at: '2026-08-12T20:59:24+00:00'
verified:
- by: human:kenly@google.com
  at: '2026-08-13T00:00:00+00:00'
stale_after: '2026-11-13'
sources:
- id: bq-metadata
  resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/transactions
  title: BigQuery Table Metadata and Data Profile
---

The `transactions` table contains transaction-level ledger records tracking financial transactions made by account holders within the [Cymbal Bank dataset](/datasets/cymbal_bank_v6z_scaffold_demo_copy.md).[^bq-metadata] The grain of this table is one row per individual transaction. The table contains approximately 20,000 records spanning a temporal range from 2023 through 2026, capturing a comprehensive history of customer purchasing activities and utility payments.

This table is frequently analyzed alongside other financial tables such as [accounts](/tables/accounts.md) to understand customer spending profiles, and [balance_snapshots](/tables/balance_snapshots.md) to reconcile historical account balances. It also serves as a baseline for detecting anomalies, categorizing merchant expenses, and computing aggregated financial statistics over time.

# Related concepts

_Generated from the concepts that reference this table — see `okf-review/postauthor.py`._

## Joins
* [accounts → transactions](/references/joins/accounts__transactions.md) - One account has_txn many transactions rows, joined on account_id.

## Metrics
* [total_txn_amount (transactions)](/references/metrics/transactions__total_txn_amount.md) - additive measure on transactions.
* [txn_amount_3mo_moving_avg (transactions)](/references/metrics/transactions__txn_amount_3mo_moving_avg.md) - moving avg measure on transactions.

# Schema

| Field Name | Type | Mode | Description |
| :--- | :---: | :---: | :--- |
| `transaction_id` | INTEGER | NULLABLE | A unique identifier for each transaction. |
| `account_id` | INTEGER | NULLABLE | The identifier of the account associated with the transaction, referencing `account_id` in the [accounts](/tables/accounts.md) table. |
| `txn_date` | DATE | NULLABLE | The date when the transaction occurred. |
| `amount` | FLOAT | NULLABLE | The monetary amount of the transaction. |
| `merchant_category` | STRING | NULLABLE | The category of the merchant where the transaction was made (e.g., `retail`, `utilities`, `fuel`, `restaurants`, `travel`, `education`, `other`). |

# Data characteristics

_Computed from BigQuery on 2026-08-15 by `okf-review/mirror.py`. The warehouse is authoritative for this section — it is a cache, not an assertion, and a refresh overwrites it._

**20,000 rows.**

| Column | Nulls | Distinct | Range / top values |
| :--- | ---: | ---: | :--- |
| `transaction_id` | 0 | 20,000 | 1 – 20,000 |
| `account_id` | 0 | 1,080 | 1 – 1,080 |
| `txn_date` | 0 | 1,096 | 2023-05-01 – 2026-04-30 |
| `amount` | 0 | 9,914 | -568.65 – 4,950.46 |
| `merchant_category` | 0 | 10 | `other` 10.4%, `retail` 10.3%, `utilities` 10.3%, `fuel` 10.1%, `restaurants` 10.1%, `travel` 9.9%, `entertainment` 9.9%, `healthcare` 9.8%, `groceries` 9.7%, `education` 9.5% |

# Common query patterns

### 1. Total monthly spending by merchant category
The following query calculates the total spending amount and transaction count for each merchant category, grouped by year and month.

```sql
SELECT
  EXTRACT(YEAR FROM txn_date) AS txn_year,
  EXTRACT(MONTH FROM txn_date) AS txn_month,
  merchant_category,
  ROUND(SUM(amount), 2) AS total_spending,
  COUNT(transaction_id) AS transaction_count
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.transactions`
GROUP BY
  txn_year,
  txn_month,
  merchant_category
ORDER BY
  txn_year DESC,
  txn_month DESC,
  total_spending DESC;
```

### 2. High-value transactions with account details
To find transactions exceeding $500 and retrieve details of the associated accounts, we can join this table with the [accounts](/tables/accounts.md) table.

```sql
SELECT
  t.transaction_id,
  t.txn_date,
  t.amount,
  t.merchant_category,
  a.account_id,
  a.account_type
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.transactions` AS t
INNER JOIN (
  -- accounts carries duplicate loads; de-duplicate before joining or every
  -- matched transaction is repeated once per surviving account row.
  SELECT * FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.accounts`
  QUALIFY ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY load_batch_id) = 1
) AS a
ON
  t.account_id = a.account_id
WHERE
  t.amount > 500.0
ORDER BY
  t.amount DESC;
```

### 3. Account-level transaction summary
The following query summarizes key financial metrics for each account, including total spending, average transaction size, and total transaction count.

```sql
SELECT
  account_id,
  COUNT(transaction_id) AS total_transactions,
  ROUND(SUM(amount), 2) AS aggregate_amount,
  ROUND(AVG(amount), 2) AS average_transaction_amount,
  MIN(txn_date) AS first_transaction_date,
  MAX(txn_date) AS last_transaction_date
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.transactions`
GROUP BY
  account_id
ORDER BY
  aggregate_amount DESC;
```

[^bq-metadata]: BigQuery Table Metadata and Dataplex Data Profile for `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.transactions`.
