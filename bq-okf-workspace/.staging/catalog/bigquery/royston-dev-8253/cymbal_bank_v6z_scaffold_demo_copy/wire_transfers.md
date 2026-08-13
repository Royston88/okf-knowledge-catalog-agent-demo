---
title: Wire Transfers
description: Logs outbound international wire transfers initiated by customers,
  specifying transfer amounts, dates, and country corridors.
tags:
  - transactions
  - payments
  - international-wires
  - customer-activity
type: dataplex-types.global.bigquery-table
catalogEntry:
  name: bigquery/royston-dev-8253/cymbal_bank_v6z_scaffold_demo_copy/wire_transfers
  resource:
    name: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/wire_transfers
  aspects:
    royston-dev-8253.us.okf:
      okf_type: BigQuery Table
      generated:
        by: reference_agent/gemini-3.5-flash
        at: 2026-08-12T20:58:01+00:00
      sources:
        - id: bq-table-metadata
          resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/wire_transfers
          title: BigQuery Table Metadata for wire_transfers
---

The `wire_transfers` table logs outbound international wire transfers initiated by customers of Cymbal Bank[^bq-table-metadata]. Every record in this table represents a unique wire transfer transaction, uniquely identified by `transfer_id`. This table belongs to the [cymbal_bank_v6z_scaffold_demo_copy dataset](../datasets/cymbal_bank_v6z_scaffold_demo_copy.md) and provides crucial visibility into international payment flows, customer remittance behavior, and transactional speed.

The table contains 3,000 records spanning multiple years[^bq-table-metadata]. Each transfer is associated with a specific customer through the `customer_id` foreign key, which links back to the [customers](customers.md) table. While day-to-day domestic payments or account transactions are captured in the [payments](payments.md) and [transactions](transactions.md) tables respectively, international transfers are routed through this specialized log. Every transfer in this dataset originates from the United States (`US`) and targets one of six country destinations: Germany (`DE`), Singapore (`SG`), Canada (`CA`), United Kingdom (`UK`), India (`IN`), or Japan (`JP`)[^bq-table-metadata]. Transaction values are recorded under `amount`, and processing timelines can be evaluated by comparing the `sent_date` and `received_date`.

# Schema

| Field Name | Type | Mode | Description |
| :--- | :--- | :--- | :--- |
| **transfer_id** | INTEGER | NULLABLE | Unique identifier for each wire transfer. Serves as the primary key of this table[^bq-table-metadata]. |
| **customer_id** | INTEGER | NULLABLE | Identifier of the customer who sent the wire transfer. Foreign key referencing [customers.customer_id](customers.md)[^bq-table-metadata]. |
| **amount** | FLOAT | NULLABLE | The monetary amount of the wire transfer transaction[^bq-table-metadata]. |
| **sent_date** | DATE | NULLABLE | The date when the customer initiated the outbound wire transfer[^bq-table-metadata]. |
| **received_date** | DATE | NULLABLE | The date when the wire transfer was successfully received at the destination bank[^bq-table-metadata]. |
| **corridor** | STRING | NULLABLE | The direction and routing pair of the international wire transfer (e.g., `US->CA`, `US->DE`)[^bq-table-metadata]. |

# Common query patterns

### 1. Summary of Transfers by Corridor
Analyze the total volume, transaction count, and average value of transfers made through each international corridor.

```sql
SELECT
  corridor,
  COUNT(transfer_id) AS total_transfers,
  ROUND(SUM(amount), 2) AS total_amount,
  ROUND(AVG(amount), 2) AS avg_amount
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.wire_transfers`
GROUP BY
  corridor
ORDER BY
  total_amount DESC;
```

### 2. Processing Speed and Volume by Month
Track the month-over-month volume of wire transfers along with the average processing time in days (difference between receipt and initiation dates).

```sql
SELECT
  DATE_TRUNC(sent_date, MONTH) AS transfer_month,
  COUNT(transfer_id) AS total_transfers,
  ROUND(AVG(DATE_DIFF(received_date, sent_date, DAY)), 2) AS avg_processing_days,
  ROUND(SUM(amount), 2) AS total_volume
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.wire_transfers`
GROUP BY
  transfer_month
ORDER BY
  transfer_month DESC;
```

### 3. Top Remitting Customers
Identify the top 10 customers by total dollar amount sent via wire transfer, cross-referencing their basic details from the customers table.

```sql
SELECT
  w.customer_id,
  c.first_name,
  c.last_name,
  COUNT(w.transfer_id) AS total_wires,
  ROUND(SUM(w.amount), 2) AS total_wire_amount
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.wire_transfers` w
JOIN
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customers` c
ON
  w.customer_id = c.customer_id
GROUP BY
  w.customer_id,
  c.first_name,
  c.last_name
ORDER BY
  total_wire_amount DESC
LIMIT 10;
```

[^bq-table-metadata]: BigQuery Table Metadata for wire_transfers
