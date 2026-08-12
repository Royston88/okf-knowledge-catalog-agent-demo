# BigQuery Table

* [Account Owners](account_owners.md) - A junction table establishing the ownership mapping and roles between customers and bank accounts.
* [Accounts](accounts.md) - Core table containing checking, savings, and credit accounts managed by Cymbal Bank.
* [Balance Snapshots](balance_snapshots.md) - Monthly historical snapshots of account balances for Cymbal Bank customers.
* [Calendar](calendar.md) - A standard reference dimension table containing calendar and fiscal date attributes from May 1, 2023, through April 30, 2026.
* [Customer Segment History](customer_segment_history.md) - Historical log of customer tier assignments (retail, premier, private) over time using a Slowly Changing Dimension (SCD) Type 2 structure.
* [Customers](customers.md) - Contains demographic, geographic, and account segment profiles for Cymbal Bank customers, including referral connections.
* [Investors](investors.md) - Details of individuals and institutional entities investing in loan portfolios.
* [Loan Applications](loan_applications.md) - Encompasses the application pipeline and lifecycle dates for bank loan products.
* [Loan Investors](loan_investors.md) - A junction table that records the financial allocation and participation tier of institutional investors in loan applications.
* [Payments](payments.md) - A ledger of customer payment transactions across multiple channels (ACH, card, Zelle, wire, and check).
* [Support Tickets](support_tickets.md) - A table containing support ticket records created by customers across various communication channels, tracking creation dates and priorities.
* [Transactions](transactions.md) - Transaction-level ledger records of financial activities for bank accounts.
* [Wire Transfers](wire_transfers.md) - Logs outbound international wire transfers initiated by customers, specifying transfer amounts, dates, and country corridors.
