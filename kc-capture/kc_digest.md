# Knowledge-Catalog digest — arm `rich`

Mechanically rendered from Dataplex Knowledge Catalog artifacts by `bi_modeling_playbook/scaffold/kc_digest.py` (raw stats only; NO modeling judgment applied — PK/FK/bridge/snapshot/role/measure decisions are the reader's). Raw JSON is archived beside this file.

**This arm sees:** data profiling + schema-join relationships + table data-documentation (overviews, column descriptions, suggested queries).

## Tables — data profile (Dataplex DATA_PROFILE, 100% sample)

For each column: LookML-ish type is your call; the numbers are raw KC stats. `distinct_ratio` = distinct/rows (1.0 = unique); `null_ratio` = fraction null (absent shown as 0). `top` = most frequent value:count.


### `account_owners`  (row_count=1380, 3 columns)

| column | bq_type | distinct_ratio | null_ratio | top values (value:count) | numeric/len stats |
|---|---|---|---|---|---|
| account_id | INTEGER | 0.8703 | 0 | '1195':2, '1163':2, '1159':2, '1143':2, '1131':2, '1126':2 | avg=595 quartiles=[296,599,890] |
| customer_id | INTEGER | 0.3406 | 0 | '469':8, '161':8, '108':8, '431':7, '382':7, '172':7 | avg=254.3 quartiles=[131,249,380] |
| ownership_role | STRING | 0.001449 | 0 | 'primary':1200, 'joint':180 | str_len min=5 max=7 avg=6.739 |

### `accounts`  (row_count=1260, 7 columns)

| column | bq_type | distinct_ratio | null_ratio | top values (value:count) | numeric/len stats |
|---|---|---|---|---|---|
| account_id | INTEGER | 0.9532 | 0 | '1190':2, '1187':2, '1166':2, '1148':2, '1136':2, '1106':2 | avg=598.5 quartiles=[296,596,899] |
| customer_id | INTEGER | 0.3627 | 0 | '145':8, '108':8, '469':7, '412':7, '161':7, '89':7 | avg=251.1 quartiles=[125,241,377] |
| account_type | STRING | 0.002381 | 0 | 'checking':700, 'savings':432, 'credit':128 | str_len min=6 max=8 avg=7.454 |
| balance | FLOAT | 0.9532 | 0 | '41212.01':2, '19691.14':2, '18967.14':2, '15853.11':2, '14845.96':2, '14026.81':2 | avg=5093 quartiles=[1527,3026,6028] |
| interest_rate | FLOAT | 0.477 | 0 | '0.035':10, '0.0772':8, '0.0814':7, '0.076':7, '0.0758':7, '0.0646':7 | avg=0.05486 quartiles=[0.037,0.0551,0.0734] |
| open_date | DATE | 0.781 | 0 | '2024-09-08':5, '2024-03-08':4, '2024-03-04':4, '2024-01-06':4, '2022-11-20':4, '2021-08-22':4 |  |
| load_batch_id | INTEGER | 0.001587 | 0 | '1':1200, '2':60 | avg=1.048 quartiles=[1,1,1] |

### `balance_snapshots`  (row_count=7200, 3 columns)

| column | bq_type | distinct_ratio | null_ratio | top values (value:count) | numeric/len stats |
|---|---|---|---|---|---|
| account_id | INTEGER | 0.1668 | 0 | '1200':6, '1199':6, '1198':6, '1197':6, '1196':6, '1195':6 | avg=600.5 quartiles=[300,600,900] |
| snapshot_month | DATE | 0.0008333 | 0 | '2026-04-01':1200, '2026-03-01':1200, '2026-02-01':1200, '2026-01-01':1200, '2025-12-01':1200, '2025-11-01':1200 |  |
| balance | FLOAT | 0.9951 | 0 | '8247.55':2, '4636.57':2, '3117.43':2, '2991.31':2, '2940.31':2, '2936.47':2 | avg=4935 quartiles=[1473,2940,5802] |

### `calendar`  (row_count=1096, 6 columns)

| column | bq_type | distinct_ratio | null_ratio | top values (value:count) | numeric/len stats |
|---|---|---|---|---|---|
| cal_date | DATE | 1 | 0 | '2026-04-30':1, '2026-04-29':1, '2026-04-28':1, '2026-04-27':1, '2026-04-26':1, '2026-04-25':1 |  |
| cal_year | INTEGER | 0.00365 | 0 | '2024':366, '2025':365, '2023':245, '2026':120 | avg=2024 quartiles=[2024,2024,2025] |
| cal_quarter | STRING | 0.00365 | 0 | 'Q4':276, 'Q3':276, 'Q2':273, 'Q1':271 | str_len min=2 max=2 avg=2 |
| fiscal_quarter | STRING | 0.01095 | 0 | 'FY2026-Q4':92, 'FY2026-Q3':92, 'FY2026-Q2':92, 'FY2025-Q4':92, 'FY2025-Q3':92, 'FY2025-Q2':92 | str_len min=9 max=9 avg=9 |
| is_holiday | BOOLEAN | 0.001825 | 0 | 'false':1063, 'true':33 |  |
| day_of_week | STRING | 0.006387 | 0 | 'Wed':157, 'Tue':157, 'Thu':157, 'Mon':157, 'Sun':156, 'Sat':156 | str_len min=3 max=3 avg=3 |

### `customer_segment_history`  (row_count=827, 4 columns)

| column | bq_type | distinct_ratio | null_ratio | top values (value:count) | numeric/len stats |
|---|---|---|---|---|---|
| customer_id | INTEGER | 0.6046 | 0 | '490':3, '487':3, '485':3, '480':3, '476':3, '467':3 | avg=251.4 quartiles=[128,251,375] |
| segment | STRING | 0.003628 | 0 | 'retail':460, 'premier':241, 'private':126 | str_len min=6 max=7 avg=6.444 |
| valid_from | DATE | 0.318 | 0 | '2018-01-01':500, '2025-12-01':3, '2025-06-29':3, '2024-12-24':3, '2024-12-09':3, '2024-06-07':3 |  |
| valid_to | DATE | 0.318 | 0 | '9999-12-31':500, '2025-12-01':3, '2025-06-29':3, '2024-12-24':3, '2024-12-09':3, '2024-06-07':3 |  |

### `customers`  (row_count=500, 8 columns)

| column | bq_type | distinct_ratio | null_ratio | top values (value:count) | numeric/len stats |
|---|---|---|---|---|---|
| customer_id | INTEGER | 1 | 0 | '500':1, '499':1, '498':1, '497':1, '496':1, '495':1 | avg=250.5 quartiles=[125,250,375] |
| name | STRING | 1 | 0 | 'Zachary Pittman':1, 'Zachary Allen':1, 'Yvonne Vargas':1, 'Yvette Lewis':1, 'Willie Miller':1, 'William Wright':1 | str_len min=9 max=22 avg=13.27 |
| segment | STRING | 0.006 | 0 | 'retail':355, 'premier':126, 'private':19 | str_len min=6 max=7 avg=6.29 |
| region | STRING | 0.012 | 0 | 'Northwest':94, 'Midwest':88, 'Northeast':81, 'Southwest':80, 'West':79, 'Southeast':78 | str_len min=4 max=9 avg=7.858 |
| signup_date | DATE | 0.928 | 0 | '2022-12-05':3, '2026-01-11':2, '2025-07-02':2, '2025-02-20':2, '2024-08-31':2, '2024-04-23':2 |  |
| referred_by | INTEGER | 0.198 | 0.37 | '1':49, '2':34, '4':12, '6':11, '9':9, '12':8 | avg=44.06 quartiles=[2,12,51] |
| state | STRING | 0.036 | 0 | 'Massachusetts':39, 'Idaho':36, 'North Carolina':35, 'Michigan':33, 'Montana':32, 'Oregon':29 | str_len min=4 max=14 avg=8.294 |
| city | STRING | 0.072 | 0 | 'Massachusetts Metro':22, 'Idaho City':20, 'Michigan City':19, 'North Carolina Metro':18, 'North Carolina City':17, 'Montana City':17 | str_len min=9 max=20 avg=13.77 |

### `investors`  (row_count=40, 3 columns)

| column | bq_type | distinct_ratio | null_ratio | top values (value:count) | numeric/len stats |
|---|---|---|---|---|---|
| investor_id | INTEGER | 1 | 0 | '40':1, '39':1, '38':1, '37':1, '36':1, '35':1 | avg=20.5 quartiles=[10,20,30] |
| name | STRING | 1 | 0 | 'Wolf PLC':1, 'Walker-Smith':1, 'Tucker, Klein and Jackson':1, 'Stevens, Heath and Greene':1, 'Smith-Hull':1, 'Silva, Chen and Mcgee':1 | str_len min=8 max=27 avg=14.82 |
| investor_type | STRING | 0.1 | 0 | 'retail':15, 'insurer':12, 'fund':9, 'bank':4 | str_len min=4 max=7 avg=5.65 |

### `loan_applications`  (row_count=800, 8 columns)

| column | bq_type | distinct_ratio | null_ratio | top values (value:count) | numeric/len stats |
|---|---|---|---|---|---|
| application_id | INTEGER | 1 | 0 | '800':1, '799':1, '798':1, '797':1, '796':1, '795':1 | avg=400.5 quartiles=[200,400,600] |
| customer_id | INTEGER | 0.515 | 0 | '371':6, '439':5, '346':5, '322':5, '272':5, '125':5 | avg=243.7 quartiles=[115,241,370] |
| product_type | STRING | 0.00625 | 0 | 'mortgage':248, 'auto':221, 'personal':156, 'business':102, 'student':73 | str_len min=4 max=8 avg=6.804 |
| amount | FLOAT | 1 | 0 | '811968.38':1, '532119.71':1, '531584.54':1, '433833.63':1, '409618.94':1, '385906.77':1 | avg=8.192e+04 quartiles=[3.493e+04,5.987e+04,1.018e+05] |
| applied_date | DATE | 0.7037 | 0 | '2024-04-09':5, '2023-10-02':5, '2025-12-31':4, '2024-04-15':4, '2023-05-20':4, '2026-03-19':3 |  |
| approved_date | DATE | 0.6062 | 0.2125 | '2025-03-22':5, '2024-08-15':4, '2024-05-11':4, '2023-07-17':4, '2026-03-31':3, '2026-03-04':3 |  |
| funded_date | DATE | 0.5062 | 0.3312 | '2026-02-18':4, '2025-07-15':4, '2026-04-13':3, '2026-03-07':3, '2026-02-26':3, '2025-07-27':3 |  |
| closed_date | DATE | 0.21 | 0.7638 | '2025-12-24':3, '2025-11-09':3, '2025-09-28':3, '2026-04-14':2, '2026-01-09':2, '2025-12-31':2 |  |

### `loan_investors`  (row_count=2019, 4 columns)

| column | bq_type | distinct_ratio | null_ratio | top values (value:count) | numeric/len stats |
|---|---|---|---|---|---|
| application_id | INTEGER | 0.3962 | 0 | '787':4, '786':4, '784':4, '783':4, '782':4, '780':4 | avg=397.4 quartiles=[199,395,594] |
| investor_id | INTEGER | 0.01981 | 0 | '8':70, '18':64, '40':61, '14':61, '3':61, '20':60 | avg=20.53 quartiles=[10,20,31] |
| allocation_pct | FLOAT | 0.7964 | 0 | '1.0':174, '0.3326':4, '0.3205':4, '0.6891':3, '0.4595':3, '0.4187':3 | avg=0.3962 quartiles=[0.2171,0.3372,0.4914] |
| participation_tier | STRING | 0.001486 | 0 | 'lead':800, 'co-lead':626, 'participant':593 | str_len min=4 max=11 avg=6.986 |

### `payments`  (row_count=8000, 6 columns)

| column | bq_type | distinct_ratio | null_ratio | top values (value:count) | numeric/len stats |
|---|---|---|---|---|---|
| payment_id | INTEGER | 0.9996 | 0 | '8000':1, '7999':1, '7998':1, '7997':1, '7996':1, '7995':1 | avg=4000 quartiles=[1999,3999,6000] |
| customer_id | INTEGER | 0.0625 | 0 | '16':29, '479':28, '417':27, '367':27, '114':27, '360':26 | avg=247.2 quartiles=[121,245,373] |
| amount | FLOAT | 0.8087 | 0 | '49.76':6, '58.27':5, '45.96':5, '31.4':5, '18.57':5, '87.57':4 | avg=98.14 quartiles=[35.82,65.54,121.8] |
| payment_date | DATE | 0.1064 | 0 | '2025-04-01':21, '2025-02-10':20, '2024-09-15':19, '2024-10-03':18, '2024-04-27':18, '2026-04-14':17 |  |
| payment_month | DATE | 0.0035 | 0 | '2025-01-01':320, '2024-01-01':308, '2025-03-01':305, '2024-06-01':301, '2026-04-01':300, '2026-03-01':300 |  |
| channel | STRING | 0.000625 | 0 | 'ach':2692, 'card':2423, 'zelle':1095, 'wire':980, 'check':810 | str_len min=3 max=5 avg=3.902 |

### `support_tickets`  (row_count=1500, 5 columns)

| column | bq_type | distinct_ratio | null_ratio | top values (value:count) | numeric/len stats |
|---|---|---|---|---|---|
| ticket_id | INTEGER | 1 | 0 | '1500':1, '1499':1, '1498':1, '1497':1, '1496':1, '1495':1 | avg=750.5 quartiles=[375,750,1125] |
| customer_id | INTEGER | 0.314 | 0 | '430':9, '364':9, '346':9, '200':9, '441':8, '263':8 | avg=247.6 quartiles=[123,248,373] |
| created_date | DATE | 0.536 | 0 | '2026-04-12':6, '2025-04-26':5, '2025-01-20':5, '2025-01-05':5, '2025-01-04':5, '2024-11-12':5 |  |
| channel | STRING | 0.002667 | 0 | 'phone':600, 'chat':455, 'email':297, 'branch':148 | str_len min=4 max=6 avg=4.795 |
| priority | INTEGER | 0.003333 | 0 | '3':708, '4':382, '2':189, '5':148, '1':73 | avg=3.229 quartiles=[3,3,4] |

### `transactions`  (row_count=20000, 5 columns)

| column | bq_type | distinct_ratio | null_ratio | top values (value:count) | numeric/len stats |
|---|---|---|---|---|---|
| transaction_id | INTEGER | 1 | 0 | '20000':1, '19999':1, '19998':1, '19997':1, '19996':1, '19995':1 | avg=1e+04 quartiles=[4998,9998,1.5e+04] |
| account_id | INTEGER | 0.05405 | 0 | '123':47, '63':44, '78':42, '28':42, '107':41, '98':41 | avg=491.7 quartiles=[181,478,779] |
| txn_date | DATE | 0.05485 | 0 | '2025-06-29':32, '2025-05-22':32, '2026-04-07':31, '2024-01-03':31, '2025-09-01':30, '2023-07-05':30 |  |
| amount | FLOAT | 0.4955 | 0 | '25.57':11, '10.47':11, '25.92':10, '18.05':10, '16.17':10, '16.0':10 | avg=52.94 quartiles=[16.03,32.28,63.66] |
| merchant_category | STRING | 0.0005 | 0 | 'other':2086, 'retail':2065, 'utilities':2052, 'fuel':2025, 'restaurants':2015, 'travel':1988 | str_len min=4 max=13 avg=8.162 |

### `wire_transfers`  (row_count=3000, 6 columns)

| column | bq_type | distinct_ratio | null_ratio | top values (value:count) | numeric/len stats |
|---|---|---|---|---|---|
| transfer_id | INTEGER | 1 | 0 | '3000':1, '2999':1, '2998':1, '2997':1, '2996':1, '2995':1 | avg=1500 quartiles=[750,1500,2250] |
| customer_id | INTEGER | 0.1667 | 0 | '215':16, '59':15, '484':13, '120':13, '43':13, '16':13 | avg=245.7 quartiles=[120,241,372] |
| amount | FLOAT | 0.9983 | 0 | '2989.18':2, '2302.5':2, '1937.01':2, '695.91':2, '170638.98':1, '163124.3':1 | avg=8405 quartiles=[2502,4914,9838] |
| sent_date | DATE | 0.3443 | 0 | '2023-09-18':10, '2025-10-10':8, '2025-08-04':8, '2023-09-08':8, '2023-06-27':8, '2023-05-26':8 |  |
| received_date | DATE | 0.3407 | 0 | '2023-07-31':9, '2026-04-12':8, '2026-03-23':8, '2025-10-29':8, '2025-05-27':8, '2025-04-23':8 |  |
| corridor | STRING | 0.002 | 0 | 'US->DE':565, 'US->SG':500, 'US->CA':495, 'US->UK':491, 'US->IN':482, 'US->JP':467 | str_len min=6 max=6 avg=6 |


## Relationships — schema-join candidates (dataset-scope DATA_DOCUMENTATION scan)

AUTO-generated join candidates (`inference_source=AGENT` unless noted). **Treat as candidates, not ground truth**: the generator may emit spurious/decoy joins and may OMIT real ones (e.g. a self-referential FK). Each line: `source_table.field = target_table.field  [inference_source]`.

- `account_owners.account_id = accounts.account_id`  [AGENT]
- `account_owners.customer_id = customers.customer_id`  [AGENT]
- `accounts.account_id = balance_snapshots.account_id`  [AGENT]
- `accounts.customer_id = customers.customer_id`  [AGENT]
- `accounts.account_id = transactions.account_id`  [AGENT]
- `customers.customer_id = customer_segment_history.customer_id`  [AGENT]
- `customers.customer_id = loan_applications.customer_id`  [AGENT]
- `customers.customer_id = payments.customer_id`  [AGENT]
- `customers.customer_id = support_tickets.customer_id`  [AGENT]
- `customers.customer_id = wire_transfers.customer_id`  [AGENT]
- `investors.investor_id = loan_investors.investor_id`  [AGENT]
- `loan_applications.application_id = loan_investors.application_id`  [AGENT]


## Table documentation (Dataplex DATA_DOCUMENTATION — overviews, column descriptions, suggested queries)


### `account_owners`
**overview:** This table establishes the relationships between customer accounts and their respective owners. It details which individuals are associated with specific accounts and their designated roles in that ownership. This table supports analysis of account ownership structures and customer relationships.
**columns:**
- `account_id`: This column holds the unique identifier for each bank account.
- `customer_id`: This column holds the unique identifier for each customer.
- `ownership_role`: This column holds the specific role a customer has in relation to an account.
**suggested queries (28 total; first 6 shown):**
- Identify customer_ids that own a significantly higher number of accounts compared to the average customer, potentially indicating a high-value customer or an anomaly in account creation.
  `SELECT customer_id, COUNT(DISTINCT account_id) AS number_of_accounts FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.account_owners` GROUP BY customer_id HAVING COUNT(DISTINCT account_id) > ( SELECT AVG(account`
- Find ownership_roles that are extremely rare, occurring less frequently than the 1st percentile of all ownership roles, potentially highlighting specialized or erroneous roles.
  `SELECT ownership_role, COUNT(*) AS role_occurrence_count FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.account_owners` GROUP BY ownership_role HAVING COUNT(*) < ( SELECT APPROX_QUANTILES(role_count, 100)[OFFS`
- Identify customer_ids that have a single ownership_role across all their accounts, but that specific role is highly unusual (e.g., not 'Primary' or 'Joint'), indicating a potential outlier in customer behavior.
  `WITH customer_role_counts AS ( SELECT customer_id, ownership_role, COUNT(DISTINCT account_id) AS num_accounts_with_role, COUNT(DISTINCT ownership_role) OVER (PARTITION BY customer_id) AS total_distinct_roles_for_customer`
- Identify customer pairs who share ownership of at least two different accounts, and the number of accounts they co-own.
  `SELECT a.customer_id AS customer_id_1, b.customer_id AS customer_id_2, COUNT(DISTINCT a.account_id) AS co_owned_accounts FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.account_owners` AS a JOIN `royston-dev-82`
- Identify the top 3 ownership roles that are most frequently associated with accounts having multiple owners, and the average number of owners for accounts with these roles.
  `SELECT ownership_role, COUNT(DISTINCT account_id) AS accounts_with_multiple_owners, AVG(num_owners) AS average_owners_for_multi_owner_accounts FROM (SELECT account_id, ownership_role, COUNT(customer_id) AS num_owners FRO`
- Find the ownership role with the highest standard deviation in the number of accounts owned per customer.
  `SELECT ownership_role, STDDEV(accounts_per_customer) AS stddev_accounts_per_customer FROM (SELECT ownership_role, customer_id, COUNT(DISTINCT account_id) AS accounts_per_customer FROM `royston-dev-8253.cymbal_bank_v6z_sc`

### `accounts`
**overview:** This table stores comprehensive information about financial accounts. It provides details on individual accounts, including their type, financial standing, and associated rates. The data supports analysis of customer account portfolios and financial product performance.
**columns:**
- `customer_id`: This column contains a unique identifier for the customer associated with the account.
- `account_type`: This column specifies the type of the financial account.
- `balance`: This column stores the current monetary value held in the account.
- `interest_rate`: This column contains the interest rate applicable to the account.
- `open_date`: This column records the date when the account was opened.
- `load_batch_id`: This column holds an identifier for the data loading batch.
- `account_id`: This column holds a unique identifier for each individual account.
**suggested queries (28 total; first 6 shown):**
- Identify the top 3 account types that have seen the largest percentage increase in average balance over the last two years compared to the two years prior.
  `WITH AccountBalances AS ( SELECT account_type, AVG(CASE WHEN open_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 YEAR) THEN balance ELSE NULL END) AS avg_balance_last_2_years, AVG(CASE WHEN open_date < DATE_SUB(CURRENT_DATE`
- This query identifies accounts with unusually high balances for their account type, defined as balances exceeding 3 standard deviations above the average balance for that specific account type.
  `SELECT account_id, account_type, balance, avg_balance, stddev_balance FROM ( SELECT account_id, account_type, balance, AVG(balance) OVER (PARTITION BY account_type) AS avg_balance, STDDEV(balance) OVER (PARTITION BY acco`
- This query flags accounts opened on dates that are significantly outside the typical opening date distribution for a given `load_batch_id`, specifically those in the earliest 1st percentile or latest 99th percentile.
  `SELECT account_id, open_date, load_batch_id FROM ( SELECT account_id, open_date, load_batch_id, PERCENTILE_CONT(UNIX_DATE(open_date), 0.01) OVER (PARTITION BY load_batch_id) AS p1_open_date, PERCENTILE_CONT(UNIX_DATE(ope`
- This query identifies `customer_id`s that have an unusually high number of accounts compared to the average number of accounts per customer, specifically those exceeding the 95th percentile.
  `SELECT customer_id, num_accounts FROM ( SELECT customer_id, COUNT(account_id) AS num_accounts, PERCENTILE_CONT(COUNT(account_id), 0.95) OVER () AS p95_num_accounts FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_cop`
- This query detects accounts with an `interest_rate` that is an outlier compared to other accounts of the same `account_type`, specifically those falling outside 1.5 times the interquartile range (IQR).
  `SELECT account_id, account_type, interest_rate, q1_interest_rate, q3_interest_rate, iqr FROM ( SELECT account_id, account_type, interest_rate, PERCENTILE_CONT(interest_rate, 0.25) OVER (PARTITION BY account_type) AS q1_i`
- Calculate the year-over-year growth rate of the total balance for each account type.
  `WITH YearlyBalances AS ( SELECT EXTRACT(YEAR FROM open_date) AS account_year, account_type, SUM(balance) AS total_balance FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.accounts` GROUP BY account_year, account`

### `balance_snapshots`
**overview:** This table stores historical financial information for various accounts. It provides a monthly record of financial holdings. This data supports analysis of account value trends over time. It is used for tracking financial performance and changes in account status.
**columns:**
- `snapshot_month`: This column holds the specific month for which the account balance was recorded.
- `balance`: This column holds the recorded financial amount for the account at the specified month.
- `account_id`: This column holds a unique identifier for each individual account.
**suggested queries (22 total; first 6 shown):**
- Identify accounts that have experienced a sudden and significant drop in balance, defined as a decrease of more than 50% from the previous month's balance, and where the previous month's balance was above a certain threshold (e.g., 1000).
  `SELECT t1.account_id, t1.snapshot_month, t1.balance AS current_month_balance, t2.balance AS previous_month_balance, (t1.balance - t2.balance) AS balance_drop, (t1.balance - t2.balance) / t2.balance AS percentage_drop FRO`
- Calculate the correlation between an account's balance and its snapshot month (represented as a numerical value) to understand if there's a linear relationship between time and balance changes for each account.
  `SELECT account_id, CORR(balance, UNIX_DATE(snapshot_month)) AS balance_time_correlation FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.balance_snapshots` GROUP BY account_id;`
- Identify accounts where the balance has consistently decreased for three consecutive months.
  `SELECT account_id FROM ( SELECT account_id, snapshot_month, balance, LAG(balance, 1) OVER (PARTITION BY account_id ORDER BY snapshot_month) AS prev_balance_1, LAG(balance, 2) OVER (PARTITION BY account_id ORDER BY snapsh`
- Identify accounts whose balance has increased by more than 20% in any given month compared to the previous month.
  `SELECT account_id, snapshot_month, balance, LAG(balance, 1) OVER (PARTITION BY account_id ORDER BY snapshot_month) AS previous_month_balance FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.balance_snapshots` WH`
- Calculate the average monthly balance for each account, showing the percentage change from the previous month's average balance.
  `SELECT account_id, snapshot_month, AVG(balance) AS average_monthly_balance, (AVG(balance) - LAG(AVG(balance), 1, 0) OVER (PARTITION BY account_id ORDER BY snapshot_month)) / LAG(AVG(balance), 1, 1) OVER (PARTITION BY acc`
- Identify accounts where the balance has consistently increased over the last three recorded months, indicating a positive trend.
  `SELECT account_id FROM ( SELECT account_id, snapshot_month, balance, LAG(balance, 1) OVER (PARTITION BY account_id ORDER BY snapshot_month) AS prev_month_balance, LAG(balance, 2) OVER (PARTITION BY account_id ORDER BY sn`

### `calendar`
**overview:** This table provides a comprehensive calendar of dates. It includes information about each specific date, its corresponding year, and its quarterly designation. The table also indicates whether a given date is a holiday and specifies the day of the week. This resource supports time-based analysis and reporting.
**columns:**
- `day_of_week`: This column contains the day of the week for the date.
- `cal_date`: This column holds the specific date.
- `cal_year`: This column contains the year associated with the date.
- `cal_quarter`: This column stores the calendar quarter for the date.
- `fiscal_quarter`: This column holds the fiscal quarter for the date.
- `is_holiday`: This column indicates if the date is a holiday.
**suggested queries (26 total; first 6 shown):**
- Identify days where the number of holidays in a given fiscal quarter deviates significantly from the average number of holidays for that fiscal quarter across all years, using a 1.5 standard deviation threshold.
  `WITH FiscalQuarterHolidayStats AS ( SELECT fiscal_quarter, cal_year, COUNTIF(is_holiday) AS num_holidays_in_quarter FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.calendar` GROUP BY fiscal_quarter, cal_year ),`
- Identify specific days of the week that are unusually frequently marked as holidays within a given calendar quarter, by comparing their holiday count to the 90th percentile of holiday counts for other days of the week in that quarter.
  `WITH DayOfWeekHolidayCounts AS ( SELECT cal_quarter, day_of_week, COUNTIF(is_holiday) AS holidays_on_day FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.calendar` GROUP BY cal_quarter, day_of_week ), QuarterlyD`
- Identify the calendar quarter with the most consistent number of holidays across all years, measured by the lowest standard deviation of holiday counts.
  `SELECT cal_quarter, STDDEV(holiday_count) AS stddev_holidays FROM (SELECT cal_year, cal_quarter, COUNTIF(is_holiday) AS holiday_count FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.calendar` GROUP BY cal_year,`
- Calculate the sample covariance between the calendar year and a numerical representation of the calendar quarter, grouped by whether it's a holiday, to understand their relationship on holidays vs. non-holidays.
  `SELECT t1.is_holiday, COVAR_SAMP(t1.cal_year, CASE WHEN t1.cal_quarter = 'Q1' THEN 1 WHEN t1.cal_quarter = 'Q2' THEN 2 WHEN t1.cal_quarter = 'Q3' THEN 3 WHEN t1.cal_quarter = 'Q4' THEN 4 ELSE NULL END ) AS year_quarter_c`
- Find the year and fiscal quarter combination that had the highest proportion of holidays compared to the total number of days in that quarter.
  `SELECT cal_year, fiscal_quarter, COUNTIF(is_holiday) * 100.0 / COUNT(*) AS holiday_proportion FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.calendar` GROUP BY cal_year, fiscal_quarter ORDER BY holiday_proport`
- For each year, calculate the difference between the maximum and minimum number of holidays in any given quarter.
  `SELECT cal_year, MAX(holiday_count) - MIN(holiday_count) AS holiday_range FROM (SELECT cal_year, cal_quarter, COUNTIF(is_holiday) AS holiday_count FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.calendar` GROUP`

### `customer_segment_history`
**overview:** This table tracks the historical segmentation of customers. It records the different segments a customer belonged to over time. This data supports analysis of customer segment changes and their impact. It also enables understanding customer lifecycle within various segments.
**columns:**
- `customer_id`: This column contains a unique identifier for each customer.
- `segment`: This column contains the assigned segment for a customer.
- `valid_from`: This column contains the date from which a customer's segment became active.
- `valid_to`: This column contains the date until which a customer's segment was active.
**suggested queries (19 total; first 6 shown):**
- Identify customers who have an unusually high number of segment changes within a short period (e.g., 30 days), indicating potential data anomalies or highly volatile customer behavior.
  `SELECT customer_id, COUNT(segment) AS segment_change_count, MIN(valid_from) AS first_segment_change, MAX(valid_to) AS last_segment_change FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customer_segment_history`
- Find customers whose average segment duration is significantly shorter than the typical segment duration for their most frequent segment, suggesting unusual churn or rapid re-segmentation.
  `WITH CustomerSegmentDurations AS ( SELECT customer_id, segment, DATE_DIFF(valid_to, valid_from, DAY) AS segment_duration_days FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customer_segment_history` WHERE vali`
- Identify the top 5 segments with the highest churn rate, defined as the percentage of customers who moved out of a segment within 90 days of joining it.
  `WITH SegmentEntryExit AS ( SELECT customer_id, segment, valid_from AS entry_date, LEAD(valid_from) OVER (PARTITION BY customer_id ORDER BY valid_from) AS next_segment_entry_date, LEAD(segment) OVER (PARTITION BY customer`
- Find the segments that have experienced the most significant growth in customer count over the last year, measured by the percentage increase in unique customers.
  `WITH CurrentYearCustomers AS ( SELECT segment, COUNT(DISTINCT customer_id) AS current_year_customer_count FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customer_segment_history` WHERE valid_from >= DATE_SUB(C`
- Identify customer segments that exhibit the highest variability in their membership duration, indicating potentially volatile or frequently changing customer statuses.
  `SELECT segment, VAR_SAMP(DATE_DIFF(valid_to, valid_from, DAY)) AS variance_in_segment_duration FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customer_segment_history` GROUP BY segment ORDER BY variance_in_seg`
- Calculate the average number of segment changes a customer undergoes within a specific time frame, and the standard deviation of these changes, to assess customer churn or migration patterns between segments.
  `SELECT AVG(segment_change_count) AS average_segment_changes, STDDEV_SAMP(segment_change_count) AS stddev_segment_changes FROM ( SELECT customer_id, COUNT(DISTINCT segment) - 1 AS segment_change_count FROM `royston-dev-82`

### `customers`
**overview:** This table stores comprehensive information about individual customers. It captures key demographic and registration details for each customer. This data supports analysis of customer segmentation, regional distribution, and acquisition trends. It also facilitates understanding customer origins and geographic spread.
**columns:**
- `city`: This column contains the city where the customer resides.
- `customer_id`: This column holds a unique identifier for each customer.
- `name`: This column contains the full name of the customer.
- `segment`: This column stores the assigned segment for each customer.
- `region`: This column holds the geographical region where the customer is located.
- `signup_date`: This column contains the date when the customer registered.
- `referred_by`: This column stores the identifier of the customer who referred the current customer.
- `state`: This column contains the state where the customer resides.
**suggested queries (26 total; first 6 shown):**
- Find customers who were referred by an unusually high number of other customers, indicating potential referral fraud or a highly influential customer, by identifying those in the top 1% of referrers.
  `WITH ReferralCounts AS ( SELECT referred_by AS referrer_customer_id, COUNT(customer_id) AS referred_count FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customers` WHERE referred_by IS NOT NULL GROUP BY referr`
- Identify customers who signed up on dates that are significantly outside the typical signup patterns for their respective regions, defined by a 3-standard-deviation threshold from the regional average signup date.
  `WITH RegionalSignupStats AS ( SELECT region, AVG(UNIX_DATE(signup_date)) AS avg_signup_unix_date, STDDEV(UNIX_DATE(signup_date)) AS stddev_signup_unix_date FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.custom`
- Calculate the correlation between the number of customers in a city and the average signup date (represented as days since a fixed epoch) for that city, within each region.
  `SELECT region, CORR(customer_count, avg_signup_date_days) AS customer_signup_date_correlation FROM (SELECT region, city, COUNT(customer_id) AS customer_count, AVG(UNIX_DATE(signup_date)) AS avg_signup_date_days FROM `roy`
- Find the top 5 regions with the highest growth rate in customer sign-ups between the first and second half of the year, considering only customers who were referred.
  `SELECT region, (SUM(CASE WHEN EXTRACT(MONTH FROM signup_date) BETWEEN 7 AND 12 THEN 1 ELSE 0 END) - SUM(CASE WHEN EXTRACT(MONTH FROM signup_date) BETWEEN 1 AND 6 THEN 1 ELSE 0 END)) * 100.0 / SUM(CASE WHEN EXTRACT(MONTH `
- Find the state with the highest ratio of referred customers to non-referred customers, considering only customers who signed up in the last two years.
  `SELECT state FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.customers` WHERE signup_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 YEAR) GROUP BY state ORDER BY COUNT(CASE WHEN referred_by IS NOT NULL THEN 1 END)`
- Identify customer segments that have a significantly lower or higher average signup date compared to the overall average signup date across all customers, using a 2-standard-deviation threshold.
  `WITH OverallSignupStats AS ( SELECT AVG(UNIX_DATE(signup_date)) AS overall_avg_signup_unix_date, STDDEV(UNIX_DATE(signup_date)) AS overall_stddev_signup_unix_date FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy`

### `investors`
**overview:** This table stores information about individuals or entities that provide financial capital. It serves as a central repository for identifying and categorizing these financial contributors. The data supports analysis of different types of financial backing and their associated details. This table is essential for understanding the sources of funding.
**columns:**
- `investor_id`: This column contains a unique numerical identifier for each investor.
- `name`: This column holds the full name of the investor.
- `investor_type`: This column specifies the category or classification of the investor.
**suggested queries (30 total; first 6 shown):**
- This query identifies individual investors whose names are significantly longer or shorter than the average name length for their respective investor types, potentially highlighting data entry anomalies or unique naming conventions.
  `WITH InvestorNameLengths AS ( SELECT investor_id, name, investor_type, LENGTH(name) AS name_length FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.investors` ), TypeAverageNameLengths AS ( SELECT investor_type,`
- This query identifies investor types that have an unusually low count compared to the average count of all investor types, potentially indicating rare or niche investor categories.
  `SELECT investor_type, COUNT(investor_id) AS investor_type_count FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.investors` GROUP BY investor_type HAVING COUNT(investor_id) < ( SELECT AVG(investor_type_counts.co`
- This query identifies investor types that have a disproportionately high number of investors compared to the total number of investors, indicating a dominant or overrepresented investor category.
  `SELECT investor_type, COUNT(investor_id) AS investor_count, (COUNT(investor_id) * 100.0 / (SELECT COUNT(investor_id) FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.investors`)) AS percentage_of_total FROM `roy`
- Identify investor types where the number of unique investors is less than the average number of unique investors across all types.
  `SELECT investor_type, COUNT(DISTINCT investor_id) AS unique_investor_count FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.investors` GROUP BY investor_type HAVING COUNT(DISTINCT investor_id) < (SELECT AVG(uniq`
- Identify investor types where the median length of investor names is above the overall median name length across all investors.
  `SELECT investor_type, APPROX_QUANTILES(LENGTH(name), 2)[OFFSET(1)] AS median_name_length FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.investors` GROUP BY investor_type HAVING APPROX_QUANTILES(LENGTH(name), 2`
- This query finds investor names that appear only once in the entire dataset, which could signify unique, potentially erroneous, or highly specialized entries.
  `SELECT name, COUNT(investor_id) AS name_occurrence FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.investors` GROUP BY name HAVING COUNT(investor_id) = 1;`

### `loan_applications`
**overview:** This table stores comprehensive records of financial product applications. It tracks the lifecycle of each application from submission through various stages of approval and funding. The data supports analysis of application volumes, processing times, and the overall flow of financial product requests.
**columns:**
- `amount`: This column holds the monetary value associated with the application.
- `applied_date`: This column holds the date when the application was submitted.
- `approved_date`: This column holds the date when the application received approval.
- `funded_date`: This column holds the date when the funds for the application were disbursed.
- `closed_date`: This column holds the date when the application's lifecycle was concluded.
- `application_id`: This column holds a unique identifier for each loan application.
- `customer_id`: This column holds a unique identifier for the customer submitting the application.
- `product_type`: This column holds the type of financial product being applied for.
**suggested queries (23 total; first 6 shown):**
- Find customers who have an unusually high number of loan applications within a short period (e.g., 30 days), indicating potential fraud or unusual activity, by comparing their application count to the average and standard deviation of applications per customer.
  `WITH CustomerApplicationCounts AS ( SELECT customer_id, COUNT(application_id) AS total_applications, MIN(applied_date) AS first_application_date, MAX(applied_date) AS last_application_date, DATE_DIFF(MAX(applied_date), M`
- Calculate the population covariance between the loan amount and the duration from application to closure, for each product type, to understand how these two variables move together within different loan categories.
  `SELECT product_type, COVAR_POP(amount, DATE_DIFF(closed_date, applied_date, DAY)) AS amount_to_closure_covariance FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_applications` WHERE closed_date IS NOT NULL`
- Calculate the correlation between the loan amount and the time taken from application to approval, grouped by product type, to understand if larger loans or specific product types have longer approval processes.
  `SELECT product_type, CORR(amount, DATE_DIFF(approved_date, applied_date, DAY)) AS amount_to_approval_time_correlation FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_applications` WHERE applied_date BETWEE`
- Identify loan applications where the approved amount is significantly higher or lower than the typical amount for that product type, defined as outside 1.5 times the interquartile range (IQR).
  `WITH ProductAmountStats AS ( SELECT product_type, PERCENTILE_CONT(amount, 0.25) OVER (PARTITION BY product_type) AS q1, PERCENTILE_CONT(amount, 0.75) OVER (PARTITION BY product_type) AS q3 FROM `royston-dev-8253.cymbal_b`
- Find the product types with the highest variance in loan amounts and the lowest average time from approval to closure, indicating potentially volatile but efficiently managed product lines.
  `SELECT product_type, VAR_SAMP(amount) AS loan_amount_variance, AVG(DATE_DIFF(closed_date, approved_date, DAY)) AS avg_approval_to_closure_days FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_applications` `
- Identify customers who have a higher average loan amount for their funded applications compared to their overall average loan amount across all applications, and list their average funded amount.
  `WITH CustomerAverages AS ( SELECT customer_id, AVG(amount) AS overall_avg_amount, AVG(CASE WHEN funded_date IS NOT NULL THEN amount ELSE NULL END) AS funded_avg_amount FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo`

### `loan_investors`
**overview:** This table records the involvement of various investors in loan applications. It details how different investors contribute to specific loan applications. The table supports analysis of investor participation across the loan portfolio. It also helps in understanding the distribution of loan allocations among investors.
**columns:**
- `application_id`: This column contains a unique identifier for each loan application.
- `investor_id`: This column contains a unique identifier for each investor.
- `allocation_pct`: This column contains the percentage of a loan application allocated to a specific investor.
- `participation_tier`: This column contains a categorical description of an investor's participation level.
**suggested queries (30 total; first 6 shown):**
- Find applications where the total sum of allocation percentages from all investors does not equal 100% (allowing for a small tolerance due to floating point arithmetic), indicating potential data anomalies.
  `SELECT application_id, SUM(allocation_pct) AS total_allocation_pct FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_investors` GROUP BY application_id HAVING ABS(SUM(allocation_pct) - 1.0) > 0.001;`
- Identify applications where a single investor has an unusually high allocation percentage, defined as being above the 99th percentile of all investor allocations.
  `SELECT application_id, investor_id, allocation_pct FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_investors` WHERE allocation_pct > ( SELECT PERCENTILE_CONT(allocation_pct, 0.99) OVER() FROM `royston-dev-`
- Find investors whose average allocation percentage across all applications deviates significantly (more than 2 standard deviations) from the overall average investor allocation.
  `WITH InvestorAvgAllocation AS ( SELECT investor_id, AVG(allocation_pct) AS avg_investor_allocation FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_investors` GROUP BY investor_id ), OverallStats AS ( SELEC`
- Identify applications where the number of unique investors is an outlier, specifically less than the 5th percentile of unique investors per application.
  `WITH ApplicationInvestorCount AS ( SELECT application_id, COUNT(DISTINCT investor_id) AS unique_investor_count FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_investors` GROUP BY application_id ) SELECT ai`
- Calculate the correlation between an investor's average allocation percentage and the number of applications they participate in.
  `SELECT CORR(avg_allocation, num_applications) AS allocation_application_correlation FROM (SELECT investor_id, AVG(allocation_pct) AS avg_allocation, COUNT(DISTINCT application_id) AS num_applications FROM `royston-dev-82`
- Calculate the population covariance between `allocation_pct` and `application_id` (treated as a numerical proxy for application complexity/size) for each `participation_tier`.
  `SELECT participation_tier, COVAR_POP(allocation_pct, application_id) AS population_covariance_allocation_application FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.loan_investors` GROUP BY participation_tier O`

### `payments`
**overview:** This table records individual financial transactions. It captures details about monetary transfers and their associated attributes. The data supports analysis of transaction volumes, customer spending patterns, and payment channel usage. It provides a historical record of financial movements.
**columns:**
- `payment_id`: This column holds a unique identifier for each individual payment transaction.
- `customer_id`: This column contains a unique identifier for the customer associated with each payment.
- `amount`: This column stores the monetary value of each payment.
- `payment_date`: This column records the specific date on which each payment was made.
- `payment_month`: This column indicates the month in which each payment occurred.
- `channel`: This column specifies the method or platform used for each payment.
**suggested queries (18 total; first 6 shown):**
- This query pinpoints individual payments that are exceptionally large, specifically those exceeding the 99th percentile of all payment amounts, suggesting potential fraudulent or erroneous transactions.
  `SELECT customer_id, payment_id, amount, payment_date FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.payments` WHERE amount > (SELECT APPROX_QUANTILES(amount, 100)[OFFSET(99)] FROM `royston-dev-8253.cymbal_bank`
- This query identifies customers whose average payment amount significantly deviates (more than 3 standard deviations) from the overall average payment amount across all customers, indicating potential high-value or low-value outliers.
  `SELECT customer_id, AVG(amount) AS average_payment_amount, (SELECT AVG(amount) FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.payments`) AS overall_average_payment_amount, (SELECT STDDEV(amount) FROM `royston-`
- This query detects customers who have an unusually high number of payments within a single month compared to their historical average, potentially indicating a surge in activity or a data anomaly.
  `WITH MonthlyPaymentCounts AS ( SELECT customer_id, payment_month, COUNT(payment_id) AS monthly_payment_count FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.payments` GROUP BY customer_id, payment_month ), Cust`
- This query identifies payment channels that exhibit an unusually high average transaction amount compared to the overall average for that channel, indicating potential misuse or a shift in transaction patterns.
  `WITH ChannelAvgAmounts AS ( SELECT channel, AVG(amount) AS channel_avg_amount, STDDEV(amount) AS channel_stddev_amount FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.payments` GROUP BY channel ) SELECT p.chann`
- Identify customers whose average monthly payment amount has significantly increased or decreased compared to their previous month's average, indicating a change in spending habits.
  `WITH MonthlyAvg AS ( SELECT customer_id, payment_month, AVG(amount) AS avg_monthly_amount FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.payments` WHERE payment_date BETWEEN '2023-01-01' AND '2023-12-31' GROUP`
- Analyze the correlation between payment amount and the number of payments made by a customer on a given day, segmented by payment channel.
  `SELECT channel, CORR(daily_total_amount, daily_payment_count) AS amount_payment_count_correlation FROM ( SELECT customer_id, channel, payment_date, SUM(amount) AS daily_total_amount, COUNT(payment_id) AS daily_payment_co`

### `support_tickets`
**overview:** This table stores information about customer support interactions. It tracks individual requests for assistance. The data supports analysis of customer service operations. It helps in understanding the volume and nature of customer inquiries. This table is essential for monitoring and improving customer support efficiency.
**columns:**
- `channel`: This column indicates the communication method used for the support ticket.
- `priority`: This column contains a numerical value representing the urgency level of the support ticket.
- `ticket_id`: This column contains a unique identifier for each support ticket.
- `customer_id`: This column holds the unique identifier for the customer associated with the support ticket.
- `created_date`: This column stores the date when the support ticket was created.
**suggested queries (26 total; first 6 shown):**
- Identify days where the number of high-priority (priority = 1) tickets is significantly higher than the average number of high-priority tickets for that day of the week, indicating a potential anomaly in workload.
  `WITH DailyHighPriorityTickets AS ( SELECT created_date, FORMAT_DATE('%A', created_date) AS day_of_week, COUNT(ticket_id) AS high_priority_ticket_count FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.support_tic`
- Identify channels that experience a sudden surge in ticket volume on a specific date compared to their typical daily volume, potentially indicating a channel-specific issue or event.
  `WITH DailyChannelTickets AS ( SELECT created_date, channel, COUNT(ticket_id) AS daily_ticket_count FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.support_tickets` GROUP BY created_date, channel ), ChannelRolli`
- Compute the population covariance between the priority of tickets and the number of tickets created by each customer on a given day, to see if customers who create more tickets also tend to create higher priority tickets.
  `SELECT customer_id, created_date, COVAR_POP(priority, ticket_count) AS priority_ticket_count_covariance FROM ( SELECT customer_id, created_date, AVG(priority) AS priority, COUNT(ticket_id) AS ticket_count FROM `royston-d`
- Calculate the correlation between ticket priority and the number of tickets created on a given date to understand if higher priority issues tend to be reported more frequently on certain days.
  `SELECT CORR(priority, ticket_count) AS priority_ticket_count_correlation FROM ( SELECT created_date, AVG(priority) AS priority, COUNT(ticket_id) AS ticket_count FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.s`
- Identify customers whose most recent ticket's priority is higher than their average ticket priority across all their tickets.
  `SELECT t1.customer_id FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.support_tickets` AS t1 JOIN (SELECT customer_id, MAX(created_date) AS last_ticket_date FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_`
- Calculate the moving average of ticket priority over a 7-day window for each customer.
  `SELECT created_date, customer_id, priority, AVG(priority) OVER (PARTITION BY customer_id ORDER BY created_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS seven_day_moving_avg_priority FROM `royston-dev-8253.cymbal_bank`

### `transactions`
**overview:** This table stores individual financial transactions. It provides a record of monetary movements associated with accounts. This data supports analysis of spending patterns and financial activity. It is useful for tracking account debits and credits.
**columns:**
- `txn_date`: This column holds the date when the transaction occurred.
- `amount`: This column holds the monetary value of the transaction.
- `merchant_category`: This column holds the category of the merchant involved in the transaction.
- `transaction_id`: This column holds a unique identifier for each transaction.
- `account_id`: This column holds the identifier for the account associated with the transaction.
**suggested queries (24 total; first 6 shown):**
- Compute the sample covariance between the transaction amount and the number of distinct merchant categories visited by each account, for a given period, to see if accounts with higher spending also explore more merchant types.
  `SELECT COVAR_SAMP(t.amount, account_merchant_diversity.distinct_merchants) AS amount_merchant_diversity_covariance FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.transactions` AS t JOIN ( SELECT account_id, CO`
- Calculate the Pearson correlation coefficient between transaction amount and the number of transactions per account for a specific date, to understand if higher transaction amounts are associated with more frequent transactions.
  `SELECT CORR(t.amount, account_txn_counts.num_transactions) AS amount_transaction_count_correlation FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.transactions` AS t JOIN ( SELECT account_id, COUNT(transaction_`
- Calculate the cumulative sum of transaction amounts for each account, ordered by transaction date, and identify the date when 50% of the total amount was reached.
  `SELECT account_id, txn_date, cumulative_amount FROM (SELECT account_id, txn_date, amount, SUM(amount) OVER (PARTITION BY account_id ORDER BY txn_date) AS cumulative_amount, SUM(amount) OVER (PARTITION BY account_id) AS t`
- Find the top 5 accounts with the highest standard deviation in their daily transaction amounts over the last 30 days.
  `SELECT account_id, STDDEV(daily_total_amount) AS stddev_daily_amount FROM (SELECT account_id, txn_date, SUM(amount) AS daily_total_amount FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.transactions` WHERE txn_`
- Identify accounts that have made transactions in at least 5 different merchant categories within a single month, and list the count of distinct categories for each.
  `SELECT account_id, FORMAT_DATE('%Y-%m', txn_date) AS transaction_month, COUNT(DISTINCT merchant_category) AS distinct_categories_count FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.transactions` GROUP BY acco`
- Find the top 5 accounts with the highest average transaction amount, along with the variance of their transaction amounts, for a specific quarter, to identify high-value accounts with potentially volatile spending habits.
  `SELECT account_id, AVG(amount) AS average_transaction_amount, VAR_SAMP(amount) AS transaction_amount_variance FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.transactions` WHERE EXTRACT(QUARTER FROM txn_date) =`

### `wire_transfers`
**overview:** This table stores records of financial transfers between accounts. It captures details about the movement of funds, including the amounts and timing of these transactions. The table supports analysis of transfer activity and financial flows. It provides a historical record of all completed transfers.
**columns:**
- `customer_id`: This column contains the identifier for the customer initiating the transfer.
- `amount`: This column contains the monetary value of the transfer.
- `sent_date`: This column contains the date when the transfer was initiated.
- `received_date`: This column contains the date when the transfer was completed and received.
- `corridor`: This column contains information about the geographical or transactional path of the transfer.
- `transfer_id`: This column contains a unique identifier for each individual transfer.
**suggested queries (26 total; first 6 shown):**
- For each customer, find the longest streak of consecutive days they sent transfers, and the total amount transferred during that streak.
  `WITH DailyTransfers AS ( SELECT customer_id, sent_date, SUM(amount) AS daily_amount FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.wire_transfers` GROUP BY customer_id, sent_date ), Streaks AS ( SELECT custome`
- Identify customers whose average transfer amount has decreased by more than 20% in the last 6 months compared to the previous 6 months.
  `WITH CustomerAvg AS ( SELECT customer_id, AVG(CASE WHEN sent_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 6 MONTH) THEN amount ELSE NULL END) AS current_avg, AVG(CASE WHEN sent_date < DATE_SUB(CURRENT_DATE(), INTERVAL 6 MON`
- Calculate the correlation between the amount of wire transfers and the duration it takes for them to be received, grouped by the transfer corridor, to identify corridors where higher amounts might be associated with faster or slower processing.
  `SELECT corridor, CORR(amount, DATE_DIFF(received_date, sent_date, DAY)) AS amount_duration_correlation FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.wire_transfers` WHERE received_date IS NOT NULL AND sent_da`
- Identify wire transfers with amounts significantly higher than the average for their respective corridors, potentially indicating fraudulent activity or errors.
  `SELECT customer_id, transfer_id, amount, corridor, avg_corridor_amount, (amount - avg_corridor_amount) / stddev_corridor_amount AS z_score FROM ( SELECT customer_id, transfer_id, amount, corridor, AVG(amount) OVER (PARTI`
- Calculate the population covariance between the transfer amount and the duration (in days) for each corridor, to understand how these two variables move together within specific transfer routes.
  `SELECT corridor, COVAR_POP(amount, DATE_DIFF(received_date, sent_date, DAY)) AS amount_duration_covariance FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.wire_transfers` WHERE received_date IS NOT NULL AND sen`
- Find the top 5 corridors with the highest variance in wire transfer amounts and the corresponding average transfer duration, to pinpoint corridors with volatile transaction values and their typical processing times.
  `SELECT corridor, VAR_SAMP(amount) AS amount_variance, AVG(DATE_DIFF(received_date, sent_date, DAY)) AS average_transfer_duration_days FROM `royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy.wire_transfers` WHERE receiv`
