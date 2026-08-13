---
type: BigQuery Table
resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/account_owners
title: Account Owners
description: A junction table establishing the ownership mapping and roles between customers and bank
  accounts.
tags:
- account-ownership
- junction-table
- customers
- accounts
generated:
  by: reference_agent/gemini-3.5-flash
  at: '2026-08-12T20:49:48+00:00'
sources:
- id: bq-metadata
  resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/account_owners
  title: BigQuery Table Metadata for account_owners
---

The `account_owners` table functions as a junction (many-to-many resolved mapping) table within the [cymbal_bank_v6z_scaffold_demo_copy](../datasets/cymbal_bank_v6z_scaffold_demo_copy.md) dataset[^bq-metadata]. It maps the relationship between [customers](customers.md) and their bank [accounts](accounts.md)[^bq-metadata]. Each row represents a unique association between a specific customer and an account, defined by their respective IDs and the nature of their ownership.

The grain of this table is one row per customer-account ownership mapping[^bq-metadata]. The table supports two primary types of ownership roles specified in `ownership_role`: `primary` (the principal account owner, representing approximately 87% of associations) and `joint` (additional owners sharing access to the account, representing approximately 13% of associations)[^bq-metadata]. Since there are exactly 1,200 primary ownership records and 180 joint ownership records across the table's 1,380 rows, every account has exactly one primary owner, while some accounts have multiple owners under joint custody[^bq-metadata]. Individual customers may own or share multiple accounts, and accounts can have multiple owners.

# Schema

| Field | Type | Mode | Description |
| :--- | :--- | :--- | :--- |
| `account_id` | INTEGER | NULLABLE | Unique identifier of the bank account, referencing `accounts.account_id`. |
| `customer_id` | INTEGER | NULLABLE | Unique identifier of the customer, referencing `customers.customer_id`. |
| `ownership_role` | STRING | NULLABLE | Role of the customer in relation to the account (`primary` or `joint`). |

# Common query patterns

### 1. Retrieve all accounts and their primary and joint owners
This query compiles all bank accounts, resolving their primary customer owner alongside any joint owners associated with the account.

```sql
SELECT
  ao.account_id,
  a.account_type,
  -- Primary owner customer ID
  MAX(CASE WHEN ao.ownership_role = 'primary' THEN ao.customer_id END) AS primary_customer_id,
  -- Comma-separated list of all joint owners
  STRING_AGG(
    CASE WHEN ao.ownership_role = 'joint' THEN CAST(ao.customer_id AS STRING) END, 
    ', '
  ) AS joint_customer_ids,
  -- Total number of owners linked to the account
  COUNT(ao.customer_id) AS total_owners
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.account_owners` ao
LEFT JOIN
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.accounts` a
  ON ao.account_id = a.account_id
GROUP BY
  ao.account_id,
  a.account_type;
```

### 2. Find all accounts owned by a specific customer
This query retrieves all accounts associated with a target customer and details whether they are the primary owner or a joint owner.

```sql
SELECT
  customer_id,
  account_id,
  ownership_role
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.account_owners`
WHERE
  customer_id = 469;
```

### 3. Summary of account ownership roles
This query generates high-level statistics of primary and joint ownership allocations across the bank's active accounts.

```sql
SELECT
  ownership_role,
  COUNT(DISTINCT account_id) AS unique_accounts,
  COUNT(DISTINCT customer_id) AS unique_customers,
  COUNT(*) AS total_records
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.account_owners`
GROUP BY
  ownership_role;
```

[^bq-metadata]: BigQuery Table Metadata for `account_owners`
