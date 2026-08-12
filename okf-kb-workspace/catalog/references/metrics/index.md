# Metric

* [allocated_account_balance (account_owners)](account_owners__allocated_account_balance.md) - Account balance split EQUALLY among the account's owners, attributable by ownership_role (primary vs joint).
* [allocated_loan_amount (loan_investors)](loan_investors__allocated_loan_amount.md) - allocated sum measure on loan_investors.
* [avg_accounts_per_customer (customers)](customers__avg_accounts_per_customer.md) - ratio measure on customers.
* [avg_days_to_approve (loan_applications)](loan_applications__avg_days_to_approve.md) - milestone lag measure on loan_applications.
* [avg_days_to_fund (loan_applications)](loan_applications__avg_days_to_fund.md) - milestone lag measure on loan_applications.
* [avg_monthly_balance (balance_snapshots)](balance_snapshots__avg_monthly_balance.md) - Average monthly TOTAL account balance across the snapshot history: sum balance per snapshot month, then average those monthly totals.
* [avg_payments_per_customer_in_year (customers)](customers__avg_payments_per_customer_in_year.md) - filtered ratio measure on customers.
* [avg_tickets_per_customer (customers)](customers__avg_tickets_per_customer.md) - ratio measure on customers.
* [avg_txns_per_account (accounts)](accounts__avg_txns_per_account.md) - Average number of transactions per account across ALL accounts, including accounts with zero transactions.
* [avg_txns_per_account_in_year (accounts)](accounts__avg_txns_per_account_in_year.md) - Average transactions per account for a selected year, counted across ALL accounts (accounts with zero transactions in that year count as zero, not dropped).
* [balance_period_end (balance_snapshots)](balance_snapshots__balance_period_end.md) - Total account balance AS OF the single most recent monthly snapshot (period-end stock; summed across accounts, never summed across months).
* [cumulative_payments (payments)](payments__cumulative_payments.md) - Running (cumulative) total of payment amount by month.
* [high_priority_ticket_count (support_tickets)](support_tickets__high_priority_ticket_count.md) - aggregate measure on support_tickets.
* [max_wire_amount (wire_transfers)](wire_transfers__max_wire_amount.md) - aggregate measure on wire_transfers.
* [payment_amount_pct_by_channel (payments)](payments__payment_amount_pct_by_channel.md) - percent of total measure on payments.
* [payments_yoy (payments)](payments__payments_yoy.md) - period over period measure on payments.
* [total_balance (accounts)](accounts__total_balance.md) - Sum of the CURRENT account balance across accounts.
* [total_loan_amount (loan_applications)](loan_applications__total_loan_amount.md) - additive measure on loan_applications.
* [total_payments (payments)](payments__total_payments.md) - additive measure on payments.
* [total_snapshot_balance (balance_snapshots)](balance_snapshots__total_snapshot_balance.md) - Total snapshot balance summed across accounts WITHIN a snapshot month.
* [total_txn_amount (transactions)](transactions__total_txn_amount.md) - additive measure on transactions.
* [total_wire_amount (wire_transfers)](wire_transfers__total_wire_amount.md) - additive measure on wire_transfers.
* [txn_amount_3mo_moving_avg (transactions)](transactions__txn_amount_3mo_moving_avg.md) - moving avg measure on transactions.
* [weighted_avg_interest_rate (accounts)](accounts__weighted_avg_interest_rate.md) - rate measure on accounts.
* [wire_amount_received_on_holiday (wire_transfers)](wire_transfers__wire_amount_received_on_holiday.md) - Total wire amount for wires whose RECEIVED date fell on a bank holiday (filters total_wire_amount by the received_cal role-played calendar's is_holiday).
* [wire_amount_sent_on_holiday (wire_transfers)](wire_transfers__wire_amount_sent_on_holiday.md) - Total wire amount for wires whose SENT date fell on a bank holiday (filters total_wire_amount by the sent_cal role-played calendar's is_holiday).
