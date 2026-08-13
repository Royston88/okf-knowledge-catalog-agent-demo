---
type: BigQuery Table
resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/support_tickets
title: Support Tickets
description: A table containing support ticket records created by customers across various communication
  channels, tracking creation dates and priorities.
tags:
- support
- operations
- ticketing
- customer-service
generated:
  by: reference_agent/gemini-3.5-flash
  at: '2026-08-12T20:56:54+00:00'
verified:
- by: human:kenly@google.com
  at: '2026-08-13T00:00:00+00:00'
sources:
- id: support-tickets-meta
  resource: https://bigquery.googleapis.com/v2/projects/royston-dev-8253/datasets/cymbal_bank_v6z_scaffold_demo_copy/tables/support_tickets
  title: BigQuery Metadata for support_tickets
---

The `support_tickets` table stores operational records of support requests and customer service queries submitted by clients. This table is a part of the [cymbal_bank_v6z_scaffold_demo_copy](../datasets/cymbal_bank_v6z_scaffold_demo_copy.md) dataset[^support-tickets-meta]. The grain of the table is one row per unique support ticket, with a total volume of 1,500 tickets recorded[^support-tickets-meta].

Each support ticket is uniquely identified by `ticket_id` and is associated with a specific customer listed in the [customers](customers.md) table via the `customer_id` foreign key[^support-tickets-meta]. Inbound customer requests are tracked across four support channels: phone (representing 40.0% of tickets), chat (30.3%), email (19.8%), and in-person branch visits (9.9%)[^support-tickets-meta]. 

Each ticket is assigned a numerical `priority` ranging from 1 to 5[^support-tickets-meta]. These values help support teams manage service level agreements (SLAs) and organize queues, with priority 3 and 4 tickets representing the vast majority (over 72%) of the logged volume[^support-tickets-meta].

# Schema

| Field | Type | Mode | Description |
| :--- | :--- | :--- | :--- |
| `ticket_id` | INTEGER | NULLABLE | Unique identifier for each ticket. |
| `customer_id` | INTEGER | NULLABLE | Foreign key linking to the [customers](customers.md) table. |
| `created_date` | DATE | NULLABLE | Date the support ticket was opened. |
| `channel` | STRING | NULLABLE | The channel through which the ticket was received (e.g., `phone`, `chat`, `email`, `branch`). |
| `priority` | INTEGER | NULLABLE | The ticket priority level (values from 1 to 5). |

# Common query patterns

### 1. Support volume and average priority by channel
This query aggregates the total number of tickets and the average priority rating across the different support channels.

```sql
SELECT
  channel,
  COUNT(ticket_id) AS total_tickets,
  ROUND(AVG(priority), 2) AS avg_priority
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.support_tickets`
GROUP BY
  channel
ORDER BY
  total_tickets DESC;
```

### 2. Daily support ticket volume trend
This query measures daily inbound ticket counts to help identify periods of high support activity.

```sql
SELECT
  created_date,
  COUNT(ticket_id) AS daily_ticket_count
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.support_tickets`
GROUP BY
  created_date
ORDER BY
  created_date DESC;
```

### 3. Customers with the most high-priority tickets
This query joins support tickets with the [customers](customers.md) table to find customers who have submitted the highest number of urgent (priority 4 or 5) support tickets.

```sql
SELECT
  t.customer_id,
  c.name AS customer_name,
  COUNT(t.ticket_id) AS high_priority_tickets
FROM
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.support_tickets` AS t
JOIN
  `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customers` AS c
  ON t.customer_id = c.customer_id
WHERE
  t.priority >= 4
GROUP BY
  t.customer_id,
  c.name
ORDER BY
  high_priority_tickets DESC
LIMIT 10;
```

[^support-tickets-meta]: BigQuery metadata for `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.support_tickets`.
