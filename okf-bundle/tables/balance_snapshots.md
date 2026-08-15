---
type: BigQuery Table
resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/balance_snapshots
title: Balance Snapshots
description: Monthly historical snapshots of account balances for Cymbal Bank customers.
tags:
- finance
- account-balances
- snapshots
status: stable
generated:
  by: reference_agent/gemini-3.5-flash
  at: '2026-08-12T20:50:59+00:00'
verified:
- by: human:kenly@google.com
  at: '2026-08-13T00:00:00+00:00'
sources:
- id: bq-meta
  resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/balance_snapshots
  title: BigQuery Table Metadata
---

The `balance_snapshots` table contains monthly end-of-month financial balance records for accounts in the Cymbal Bank system, located in the [cymbal_bank_v6z_scaffold_demo_copy](/datasets/cymbal_bank_v6z_scaffold_demo_copy.md) dataset[^bq-meta]. Each record stores the total balance of a specific bank account at the end of a given calendar month, enabling historical trend analysis and monthly financial reporting. While detailed transactional activity is tracked in the [transactions](/tables/transactions.md) table, this snapshot table provides pre-computed records that allow analysts to perform historical queries without reconstructing balances from individual transaction ledgers.

The grain of this table is one row per `account_id` per `snapshot_month`[^bq-meta]. The dataset contains exactly 7,200 rows, tracking 1,200 unique accounts across 6 consecutive calendar months from November 2025 (`2025-11-01`) to April 2026 (`2026-04-01`)[^bq-meta]. This data can be joined with the [accounts](/tables/accounts.md) table to analyze historical balances by account properties, such as account type or status.

# Related concepts

_Generated from the concepts that reference this table — see `okf-review/postauthor.py`._

## Grain rules
* [balance_snapshots grain](/references/grain/balance_snapshots.md) - Grain rules for balance_snapshots: it is a periodic snapshot at one row per `account_id` per `snapshot_month`.

## Joins
* [accounts → balance_snapshots](/references/joins/accounts__balance_snapshots.md) - One account snapshotted many balance_snapshots rows, joined on account_id.

## Metrics
* [avg_monthly_balance (balance_snapshots)](/references/metrics/balance_snapshots__avg_monthly_balance.md) - Average monthly TOTAL account balance across the snapshot history: sum balance per snapshot month, then average those monthly totals.
* [balance_period_end (balance_snapshots)](/references/metrics/balance_snapshots__balance_period_end.md) - Total account balance AS OF the single most recent monthly snapshot (period-end stock; summed across accounts, never summed across months).
* [total_snapshot_balance (balance_snapshots)](/references/metrics/balance_snapshots__total_snapshot_balance.md) - Total snapshot balance summed across accounts WITHIN a snapshot month.

# Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| **account_id** | `INTEGER` | Unique identifier of the account. Joins to the accounts table. |
| **snapshot_month** | `DATE` | The first day of the calendar month for which the snapshot is recorded (e.g., `2025-11-01`). |
| **balance** | `FLOAT` | The total balance of the account at the end of the snapshot month. |

# Common query patterns

### 1. Total and average balances per month
The following query calculates the total balance and average balance across all accounts for each snapshot month:

```sql
SELECT
  snapshot_month,
  COUNT(DISTINCT account_id) AS total_accounts,
  SUM(balance) AS total_balance,
  ROUND(AVG(balance), 2) AS average_balance
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.balance_snapshots`
GROUP BY
  snapshot_month
ORDER BY
  snapshot_month ASC;
```

### 2. Month-over-month balance change for an account
This query tracks monthly balance changes and month-over-month deltas for a specific account:

```sql
SELECT
  account_id,
  snapshot_month,
  balance,
  LAG(balance) OVER (PARTITION BY account_id ORDER BY snapshot_month) AS previous_month_balance,
  ROUND(balance - LAG(balance) OVER (PARTITION BY account_id ORDER BY snapshot_month), 2) AS balance_change
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.balance_snapshots`
WHERE
  account_id = 1
ORDER BY
  snapshot_month;
```

### 3. Average balance by account type
To see how different account types perform over time, you can join `balance_snapshots` with the [accounts](/tables/accounts.md) table:

```sql
SELECT
  a.account_type,
  s.snapshot_month,
  COUNT(DISTINCT s.account_id) AS account_count,
  ROUND(AVG(s.balance), 2) AS average_balance
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.balance_snapshots` s
JOIN
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.accounts` a
ON
  s.account_id = a.account_id
GROUP BY
  a.account_type,
  s.snapshot_month
ORDER BY
  a.account_type,
  s.snapshot_month;
```

[^bq-meta]: BigQuery table metadata and data profiles for `balance_snapshots`.
