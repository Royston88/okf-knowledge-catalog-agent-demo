---
type: BigQuery Table
resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/customer_segment_history
title: Customer Segment History
description: Historical log of customer tier assignments (retail, premier, private) over time using a
  Slowly Changing Dimension (SCD) Type 2 structure.
tags:
- customer-segmentation
- scd-type-2
- history
- retail-banking
status: stable
generated:
  by: reference_agent/gemini-3.5-flash
  at: '2026-08-12T20:52:28+00:00'
verified:
- by: human:kenly@google.com
  at: '2026-08-13T00:00:00+00:00'
stale_after: '2026-11-13'
sources:
- id: bq-metadata
  resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/customer_segment_history
  title: BigQuery Table Metadata and Schema
---

The `customer_segment_history` table resides within the [cymbal_bank_v6z_scaffold_demo_copy](/datasets/cymbal_bank_v6z_scaffold_demo_copy.md) dataset and stores the historical progression of customer loyalty and service tier assignments over time. Structured as a Slowly Changing Dimension (SCD) Type 2 table[^bq-metadata], it enables historical auditing and point-in-time reporting of customer tier statuses (such as retail, premier, or private). The table contains 827 rows of historical segment shifts[^bq-metadata], facilitating trend analysis on tier progression and retention.

The grain of this table is one row per customer segment assignment period. Every assignment contains a starting validity date (`valid_from`) and an ending validity date (`valid_to`). An active segment is indicated by a `valid_to` date of `9999-12-31`. To analyze historical activity or attribute financial transactions (such as those in [transactions](/tables/transactions.md) or [payments](/tables/payments.md)) to a customer's specific tier at the moment of the event, query joins should match the event date to the window between `valid_from` and `valid_to`.

The table links directly to the [customers](/tables/customers.md) table via the `customer_id` field. Across the historical log, the table tracks three segment classifications: `retail` (accounting for ~55.6% of records), `premier` (~29.1%), and `private` (~15.2%)[^bq-metadata]. The earliest recorded segment assignments start on `2018-01-01`[^bq-metadata].

# Related concepts

_Generated from the concepts that reference this table — see `okf-review/postauthor.py`._

## Joins
* [customer_segment_history → wire_transfers (segment_asof)](/references/joins/customer_segment_history__wire_transfers__segment_asof.md) - One segment_version segment_at_wire many wire_transfers rows, joined on customer_id.

# Schema

| Field | Type | Description |
| :--- | :---: | :--- |
| `customer_id` | INTEGER | Unique identifier for the customer. Joins with the `customer_id` column in the [customers](/tables/customers.md) table. |
| `segment` | STRING | The tier or category assigned to the customer. Common values include `retail`, `premier`, and `private`. |
| `valid_from` | DATE | The start date (inclusive) from which this segment assignment was valid for the customer. |
| `valid_to` | DATE | The end date (inclusive) until which this segment assignment was valid. A value of `9999-12-31` represents the currently active tier. |

# Data characteristics

_Computed from BigQuery on 2026-08-15 by `okf-review/mirror.py`. The warehouse is authoritative for this section — it is a cache, not an assertion, and a refresh overwrites it._

**827 rows.**

| Column | Nulls | Distinct | Range / top values |
| :--- | ---: | ---: | :--- |
| `customer_id` | 0 | 500 | 1 – 500 |
| `segment` | 0 | 3 | `retail` 55.6%, `premier` 29.1%, `private` 15.2% |
| `valid_from` | 0 | 263 | 2018-01-01 – 2025-12-30 |
| `valid_to` | 0 | 263 | 2024-01-01 – 9999-12-31 |

> **827 rows, 500 distinct `customer_id`.** The row count is not the entity count; de-duplicate before aggregating.

# Common query patterns

### 1. Retrieve currently active customer segments
This query retrieves the active segment classification for all currently enrolled customers.

```sql
SELECT
  customer_id,
  segment,
  valid_from
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customer_segment_history`
WHERE
  valid_to = '9999-12-31';
```

### 2. Resolve customer segments for a historical point-in-time
This query determines the tier or segment each customer belonged to on a specific historical date (for example, March 15, 2025).

```sql
SELECT
  customer_id,
  segment,
  valid_from,
  valid_to
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customer_segment_history`
WHERE
  DATE('2025-03-15') BETWEEN valid_from AND valid_to;
```

### 3. Track customer tier migration patterns
This query tracks transitions from one tier to another to understand how customers move between retail, premier, and private banking statuses.

```sql
WITH segment_transitions AS (
  SELECT
    customer_id,
    segment AS prev_segment,
    LEAD(segment) OVER (PARTITION BY customer_id ORDER BY valid_from) AS next_segment,
    valid_to AS change_date
  FROM
    `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customer_segment_history`
)
SELECT
  prev_segment,
  next_segment,
  COUNT(DISTINCT customer_id) AS customer_count
FROM
  segment_transitions
WHERE
  next_segment IS NOT NULL AND prev_segment <> next_segment
GROUP BY
  prev_segment,
  next_segment
ORDER BY
  customer_count DESC;
```

[^bq-metadata]: BigQuery Table Metadata and Schema for `tables/customer_segment_history` in `royston-dev-8253` project.
