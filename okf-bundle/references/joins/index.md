# Join

* [accounts → balance_snapshots](accounts__balance_snapshots.md) - One account snapshotted many balance_snapshots rows, joined on account_id.
* [accounts → transactions](accounts__transactions.md) - One account has_txn many transactions rows, joined on account_id.
* [accounts ↔ customers (via account_owners)](accounts__customers__via_account_owners.md) - accounts and customers are many-to-many; account_owners is the bridge that resolves them.
* [calendar → wire_transfers (received_cal)](calendar__wire_transfers__received_cal.md) - One calendar_day wire_received_on many wire_transfers rows, joined on received_date.
* [calendar → wire_transfers (sent_cal)](calendar__wire_transfers__sent_cal.md) - One calendar_day wire_sent_on many wire_transfers rows, joined on sent_date.
* [customer_segment_history → wire_transfers (segment_asof)](customer_segment_history__wire_transfers__segment_asof.md) - One segment_version segment_at_wire many wire_transfers rows, joined on customer_id.
* [customers → accounts](customers__accounts.md) - One customer owns many accounts rows, joined on customer_id.
* [customers → customers (referrer)](customers__customers__referrer.md) - One customer referred_by many customers rows, joined on referred_by.
* [customers → loan_applications](customers__loan_applications.md) - One customer applied_for many loan_applications rows, joined on customer_id.
* [customers → payments](customers__payments.md) - One customer made many payments rows, joined on customer_id.
* [customers → support_tickets](customers__support_tickets.md) - One customer opened many support_tickets rows, joined on customer_id.
* [customers → wire_transfers](customers__wire_transfers.md) - One customer sent many wire_transfers rows, joined on customer_id.
* [loan_applications ↔ investors (via loan_investors)](loan_applications__investors__via_loan_investors.md) - loan_applications and investors are many-to-many; loan_investors is the bridge that resolves them.
