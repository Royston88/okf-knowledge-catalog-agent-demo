---
type: BigQuery Table
resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/accounts
title: Accounts
description: Core table containing checking, savings, and credit accounts managed by Cymbal Bank.
tags:
- core
- accounts
- finance
generated:
  by: reference_agent/gemini-3.5-flash
  at: '2026-08-12T20:50:24+00:00'
sources:
- id: bq-metadata
  resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/accounts
  title: BigQuery Table Metadata for accounts
---

The `accounts` table stores records of all financial accounts registered at Cymbal Bank[^bq-metadata]. It acts as a central hub within the [cymbal_bank_v6z_scaffold_demo_copy dataset](../datasets/cymbal_bank_v6z_scaffold_demo_copy.md), covering checking, savings, and credit accounts. The table provides key metrics such as account balances, interest rates, and activation dates.

### Grain and Batch Updates
Each row in this table represents the state of a financial account for a specific ingestion batch[^bq-metadata]. The presence of `load_batch_id` indicates that the table handles incremental loads; for example, the primary load consists of 1,200 accounts under batch ID `1`, while a smaller subset of 60 records represents subsequent additions or updates under batch ID `2`[^bq-metadata]. Out of the 1,260 total records, there are 1,201 unique accounts[^bq-metadata]. To retrieve the most up-to-date profile for any account, queries should filter for the highest `load_batch_id` per `account_id`.

### Key Relationships
The table is highly connected to other entities across the schema:
- **Primary Owner**: The `customer_id` column maps to [customers](customers.md) to identify the primary individual owning the account (supporting 457 unique customers)[^bq-metadata].
- **Joint Ownership**: The `account_id` maps to [account_owners](account_owners.md) to define many-to-many relationships for shared accounts.
- **Transactions & Snapshots**: Financial events and ledger movements are recorded under the corresponding `account_id` in the [transactions](transactions.md) and [balance_snapshots](balance_snapshots.md) tables.

# Schema

| Field | Type | Description |
| :--- | :--- | :--- |
| `account_id` | INTEGER | Unique identifier of the financial account. |
| `customer_id` | INTEGER | Foreign key linking to the primary owner in [customers](customers.md). |
| `account_type` | STRING | The type of account. The majority of accounts are `checking` (55.6%), followed by `savings` (34.3%) and `credit` (10.2%)[^bq-metadata]. |
| `balance` | FLOAT | Current monetary balance of the account. |
| `interest_rate` | FLOAT | Annual interest rate (e.g., `0.0854` for 8.54%). |
| `open_date` | DATE | The date when the account was opened. |
| `load_batch_id` | INTEGER | The ingestion batch ID representing when this record was loaded[^bq-metadata]. |

# Common query patterns

### 1. Deduplicating accounts to get the latest state
Since accounts can be updated across batches, this query selects only the most recent state for each account.

```sql
SELECT
  account_id,
  customer_id,
  account_type,
  balance,
  interest_rate,
  open_date
FROM (
  SELECT
    *,
    ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY load_batch_id DESC) as rn
  FROM
    `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.accounts`
)
WHERE
  rn = 1;
```

### 2. Aggregating balances and counts by account type
This query summaries total holdings and average interest rates across checking, savings, and credit accounts.

```sql
WITH latest_accounts AS (
  SELECT
    account_type,
    balance,
    interest_rate,
    ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY load_batch_id DESC) as rn
  FROM
    `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.accounts`
)
SELECT
  account_type,
  COUNT(*) AS total_accounts,
  SUM(balance) AS total_balance,
  ROUND(AVG(interest_rate) * 100, 2) AS avg_interest_rate_pct
FROM
  latest_accounts
WHERE
  rn = 1
GROUP BY
  account_type
ORDER BY
  total_balance DESC;
```

### 3. Finding accounts opened in 2024 with customer details
This query joins the deduplicated accounts table with the customers table to inspect recent signups.

```sql
WITH latest_accounts AS (
  SELECT
    account_id,
    customer_id,
    account_type,
    balance,
    open_date,
    ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY load_batch_id DESC) as rn
  FROM
    `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.accounts`
)
SELECT
  a.account_id,
  a.account_type,
  a.balance,
  a.open_date,
  c.customer_id
FROM
  latest_accounts a
JOIN
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customers` c
  ON a.customer_id = c.customer_id
WHERE
  a.rn = 1
  AND EXTRACT(YEAR FROM a.open_date) = 2024
ORDER BY
  a.open_date DESC;
```

[^bq-metadata]: BigQuery metadata retrieved from `cymbal_bank_v6z_scaffold_demo_copy.accounts` table schema and profiling metrics.
