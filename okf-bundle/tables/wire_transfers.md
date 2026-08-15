---
type: BigQuery Table
resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/wire_transfers
title: Wire Transfers
description: Logs outbound international wire transfers initiated by customers, specifying transfer amounts,
  dates, and country corridors.
tags:
- transactions
- payments
- international-wires
- customer-activity
status: stable
generated:
  by: reference_agent/gemini-3.5-flash
  at: '2026-08-12T20:58:01+00:00'
verified:
- by: human:kenly@google.com
  at: '2026-08-13T00:00:00+00:00'
stale_after: '2026-11-13'
sources:
- id: bq-table-metadata
  resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/wire_transfers
  title: BigQuery Table Metadata for wire_transfers
---

The `wire_transfers` table logs outbound international wire transfers initiated by customers of Cymbal Bank[^bq-table-metadata]. Every record in this table represents a unique wire transfer transaction, uniquely identified by `transfer_id`. This table belongs to the [cymbal_bank_v6z_scaffold_demo_copy dataset](/datasets/cymbal_bank_v6z_scaffold_demo_copy.md) and provides crucial visibility into international payment flows, customer remittance behavior, and transactional speed.

The table contains 3,000 records spanning multiple years[^bq-table-metadata]. Each transfer is associated with a specific customer through the `customer_id` foreign key, which links back to the [customers](/tables/customers.md) table. While day-to-day domestic payments or account transactions are captured in the [payments](/tables/payments.md) and [transactions](/tables/transactions.md) tables respectively, international transfers are routed through this specialized log. Every transfer in this dataset originates from the United States (`US`) and targets one of six country destinations: Germany (`DE`), Singapore (`SG`), Canada (`CA`), United Kingdom (`UK`), India (`IN`), or Japan (`JP`)[^bq-table-metadata]. Transaction values are recorded under `amount`, and processing timelines can be evaluated by comparing the `sent_date` and `received_date`.

# Related concepts

_Generated from the concepts that reference this table — see `okf-review/postauthor.py`._

## Joins
* [calendar → wire_transfers (received_cal)](/references/joins/calendar__wire_transfers__received_cal.md) - One calendar_day wire_received_on many wire_transfers rows, joined on received_date.
* [calendar → wire_transfers (sent_cal)](/references/joins/calendar__wire_transfers__sent_cal.md) - One calendar_day wire_sent_on many wire_transfers rows, joined on sent_date.
* [customer_segment_history → wire_transfers (segment_asof)](/references/joins/customer_segment_history__wire_transfers__segment_asof.md) - One segment_version segment_at_wire many wire_transfers rows, joined on customer_id.
* [customers → wire_transfers](/references/joins/customers__wire_transfers.md) - One customer sent many wire_transfers rows, joined on customer_id.

## Metrics
* [max_wire_amount (wire_transfers)](/references/metrics/wire_transfers__max_wire_amount.md) - aggregate measure on wire_transfers.
* [total_wire_amount (wire_transfers)](/references/metrics/wire_transfers__total_wire_amount.md) - additive measure on wire_transfers.
* [wire_amount_received_on_holiday (wire_transfers)](/references/metrics/wire_transfers__wire_amount_received_on_holiday.md) - Total wire amount for wires whose RECEIVED date fell on a bank holiday (filters total_wire_amount by the received_cal role-played calendar's is_holiday).
* [wire_amount_sent_on_holiday (wire_transfers)](/references/metrics/wire_transfers__wire_amount_sent_on_holiday.md) - Total wire amount for wires whose SENT date fell on a bank holiday (filters total_wire_amount by the sent_cal role-played calendar's is_holiday).

# Schema

| Field Name | Type | Mode | Description |
| :--- | :---: | :---: | :--- |
| **transfer_id** | INTEGER | NULLABLE | Unique identifier for each wire transfer. Serves as the primary key of this table[^bq-table-metadata]. |
| **customer_id** | INTEGER | NULLABLE | Identifier of the customer who sent the wire transfer. Foreign key referencing [customers.customer_id](/tables/customers.md)[^bq-table-metadata]. |
| **amount** | FLOAT | NULLABLE | The monetary amount of the wire transfer transaction[^bq-table-metadata]. |
| **sent_date** | DATE | NULLABLE | The date when the customer initiated the outbound wire transfer[^bq-table-metadata]. |
| **received_date** | DATE | NULLABLE | The date when the wire transfer was successfully received at the destination bank[^bq-table-metadata]. |
| **corridor** | STRING | NULLABLE | The direction and routing pair of the international wire transfer (e.g., `US->CA`, `US->DE`)[^bq-table-metadata]. |

# Data characteristics

_Computed from BigQuery on 2026-08-15 by `okf-review/mirror.py`. The warehouse is authoritative for this section — it is a cache, not an assertion, and a refresh overwrites it._

**3,000 rows.**

| Column | Nulls | Distinct | Range / top values |
| :--- | ---: | ---: | :--- |
| `transfer_id` | 0 | 3,000 | 1 – 3,000 |
| `customer_id` | 0 | 500 | 1 – 500 |
| `amount` | 0 | 2,996 | 173.26 – 170,638.98 |
| `sent_date` | 0 | 1,032 | 2023-05-01 – 2026-04-27 |
| `received_date` | 0 | 1,022 | 2023-05-03 – 2026-04-29 |
| `corridor` | 0 | 6 | `US->DE` 18.8%, `US->SG` 16.7%, `US->CA` 16.5%, `US->UK` 16.4%, `US->IN` 16.1%, `US->JP` 15.6% |

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
  c.name,
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
  c.name
ORDER BY
  total_wire_amount DESC
LIMIT 10;
```

[^bq-table-metadata]: BigQuery Table Metadata for wire_transfers
