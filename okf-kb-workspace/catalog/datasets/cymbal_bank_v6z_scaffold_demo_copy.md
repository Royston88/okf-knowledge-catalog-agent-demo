---
type: BigQuery Dataset
resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy
title: Cymbal Bank Scaffold Demo (Copy)
description: A simulated retail banking dataset modeling customers, accounts, transactions, and loans
  for testing the OKF projector mechanism.
tags:
- financial-data
- demo-dataset
- cymbal-bank
generated:
  by: reference_agent/gemini-3.5-flash
  at: '2026-08-12T20:49:17+00:00'
sources:
- resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy
  id: bq-dataset-metadata
  title: BigQuery Dataset Metadata for cymbal_bank_v6z_scaffold_demo_copy
---

The `cymbal_bank_v6z_scaffold_demo_copy` dataset is a simulated retail banking database representing the operations of Cymbal Bank, used as a mechanism proof for the OKF projector[^bq-dataset-metadata]. It models a comprehensive banking ecosystem containing tables for customer profiles, checking/savings/credit accounts, transactional logs, loan applications, and support tickets.

The dataset serves as a relational testing ground, containing typical banking domain structures such as many-to-many relationship mapping between customers and accounts, temporal tracking of account balances, and loan investor participation logs.

# Schema

This dataset contains 14 tables modeling a retail and commercial banking system. The tables can be categorized into customer-centric tables, account-centric tables, and loan/investment-centric tables.

### Tables

- **[customers](../tables/customers.md)**: Contains customer profiles, demographics, geographic regions, segments, and referral info.
- **[accounts](../tables/accounts.md)**: Contains deposit and credit account types, current balances, interest rates, and open dates.
- **[account_owners](../tables/account_owners.md)**: Junction table linking customers to their respective bank accounts (supports many-to-many relationships).
- **[transactions](../tables/transactions.md)**: Detailed ledger of account transactions including transaction amount and merchant categories.
- **[balance_snapshots](../tables/balance_snapshots.md)**: Historical record of account balances over time.
- **[customer_segment_history](../tables/customer_segment_history.md)**: Tracking history of customer marketing/service segments.
- **[loan_applications](../tables/loan_applications.md)**: Submissions for loans by customers, including status and requested amounts.
- **[loan_investors](../tables/loan_investors.md)**: Maps investors to loan applications.
- **[investors](../tables/investors.md)**: Details of individual or institutional investors funding loans.
- **[payments](../tables/payments.md)**: Record of payments made by customers.
- **[support_tickets](../tables/support_tickets.md)**: Customer service and support ticket history.
- **[wire_transfers](../tables/wire_transfers.md)**: Log of domestic/international wire transfers.
- **[calendar](../tables/calendar.md)**: A lookup dimension table for date-based reporting.

### Key Relationships

The following entity-relationship joins have been identified across the dataset[^bq-dataset-metadata]:

| Source Table | Source Field | Target Table | Target Field | Relationship Type / Description |
| :--- | :--- | :--- | :--- | :--- |
| `account_owners` | `account_id` | `accounts` | `account_id` | Link owner to account |
| `account_owners` | `customer_id` | `customers` | `customer_id` | Link owner to customer profile |
| `accounts` | `account_id` | `balance_snapshots` | `account_id` | Balance history tracking |
| `accounts` | `customer_id` | `customers` | `customer_id` | Primary customer ownership |
| `accounts` | `account_id` | `transactions` | `account_id` | Account transaction history |
| `customers` | `customer_id` | `customer_segment_history` | `customer_id` | Segment history |
| `customers` | `customer_id` | `loan_applications` | `customer_id` | Customer loan applications |
| `customers` | `customer_id` | `payments` | `customer_id` | Customer payments |
| `customers` | `customer_id` | `support_tickets` | `customer_id` | Customer support requests |
| `customers` | `customer_id` | `wire_transfers` | `customer_id` | Customer wire transfers |
| `investors` | `investor_id` | `loan_investors` | `investor_id` | Investor assignments to loans |
| `loan_applications` | `application_id` | `loan_investors` | `application_id` | Loan funding allocation |

# Common query patterns

### 1. Customer Account and Transaction Overview
This query aggregates customer account types and their current balances along with total transaction counts and volumes.

```sql
SELECT
  c.customer_id,
  c.name,
  a.account_type,
  a.balance,
  COUNT(t.transaction_id) AS transaction_count,
  SUM(t.amount) AS total_transaction_volume
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customers` c
JOIN
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.accounts` a
  ON c.customer_id = a.customer_id
LEFT JOIN
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.transactions` t
  ON a.account_id = t.account_id
GROUP BY
  c.customer_id,
  c.name,
  a.account_type,
  a.balance
ORDER BY
  a.balance DESC
LIMIT 100;
```

### 2. Segment-based Balance and Transaction Summary
Analyze banking activity by customer service segments (e.g., retail, premier, private).

```sql
SELECT
  c.segment,
  COUNT(DISTINCT c.customer_id) AS customer_count,
  ROUND(AVG(a.balance), 2) AS average_account_balance,
  ROUND(SUM(t.amount), 2) AS total_transacted_amount
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customers` c
JOIN
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.accounts` a
  ON c.customer_id = a.customer_id
LEFT JOIN
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.transactions` t
  ON a.account_id = t.account_id
GROUP BY
  c.segment
ORDER BY
  total_transacted_amount DESC;
```

### 3. Loan Portfolio Allocation by Investor
Evaluate the aggregate loan value funded across active investors in the system.

```sql
SELECT
  i.investor_id,
  COUNT(la.application_id) AS funded_loans_count,
  SUM(la.amount) AS total_loan_portfolio_value
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.investors` i
JOIN
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_investors` li
  ON i.investor_id = li.investor_id
JOIN
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_applications` la
  ON li.application_id = la.application_id
GROUP BY
  i.investor_id
ORDER BY
  total_loan_portfolio_value DESC;
```

[^bq-dataset-metadata]: BigQuery Dataset Metadata for cymbal_bank_v6z_scaffold_demo_copy
