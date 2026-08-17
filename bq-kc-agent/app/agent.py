import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
load_dotenv()

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from .tools import execute_sql

MODEL = "gemini-2.5-flash"

import os
import google.auth
import google.auth.transport.requests

# Paths to kcmd
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_CURRENT_DIR))
KCMD_WORKSPACE = os.environ.get("KCMD_WORKSPACE", os.path.join(_PROJECT_ROOT, "bq-okf-workspace"))
KCMD_PATH = os.environ.get("KCMD_PATH", os.path.join(_PROJECT_ROOT, "kcmd"))

# Get GCP credentials to pass to MCP server to avoid slow gcloud calls
try:
    credentials, project = google.auth.default()
    if not credentials.valid:
        auth_request = google.auth.transport.requests.Request()
        credentials.refresh(auth_request)
    token = credentials.token
except Exception as e:
    print(f"Warning: Failed to get GCP credentials: {e}")
    token = None
    project = None

mcp_env = os.environ.copy()
if token:
    mcp_env["KCMD_ACCESS_TOKEN"] = token
if project:
    mcp_env["GOOGLE_CLOUD_PROJECT"] = project
mcp_env["GOOGLE_CLOUD_LOCATION"] = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

kcmd_mcp = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="node",
            args=[f"{KCMD_PATH}/run_mcp_server.js", "--workspace", KCMD_WORKSPACE],
            env=mcp_env,
        ),
        timeout=30.0,
    )
)

root_agent = Agent(
    name="bq_kc_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are a data assistant. Your goal is to answer user questions by querying BigQuery.
    1. Use the kcmd MCP tools to search and lookup table schemas and descriptions to understand the data.
    2. Formulate a SQL query based on the metadata.
       Note on BigQuery Table Names: Convert the GCP resource name (e.g. `projects/PROJECT/datasets/DATASET/tables/TABLE`) 
       to BigQuery SQL format: `PROJECT.DATASET.TABLE`. Always wrap the full table name in backticks, e.g. `PROJECT.DATASET.TABLE`.
    3. Use the execute_sql tool to run the query and get results.
    4. Answer the user based on the query results.
    
    5. **Chasm & Fan Traps Warning**: Never perform joins between multiple independent one-to-many child tables (e.g., joining both `accounts` and `support_tickets` to `customers`) before aggregation. This causes duplicate calculations and fan-out errors. Instead, perform aggregations in separate subqueries (CTEs) first, and then join the pre-aggregated results on the group key.
    6. **Parent-Child Fan-out Warning**: Never join a parent table to a child table and aggregate metrics from both in the same query (or aggregate parent metrics after the join), because the parent metrics will be duplicated by the child records. Always aggregate parent metrics and child metrics separately before joining.
    7. **Zero-Count Cohort Averages**: When calculating the average of a metric per entity (e.g., average support tickets per customer, or average transactions per account), do not simply average the counts of active rows. You must compute the total count and divide it by the *total count of all parent entities* (e.g. total tickets divided by total customers in the customers table), including those with zero occurrences.
    8. **BigQuery QUALIFY Syntax**: In BigQuery, the `QUALIFY` clause must appear **after** the `WHERE` and `GROUP BY` clauses. 
    9. **De-duplication in Aggregation**: If you need to de-duplicate rows (using `QUALIFY ROW_NUMBER() OVER (...) = 1`) and then perform an aggregation (like `SUM` or `COUNT`) across the whole table or grouped by key, you **cannot** use `QUALIFY` in the same query block as the aggregation. You MUST perform the de-duplication inside a CTE or subquery first, and then run the aggregation on the de-duplicated subquery in the outer SELECT.
    10. **Case-Insensitive String Filters**: BigQuery string filters are case-sensitive. Always query distinct values of a string column if you are filtering by a categorical value (like customer segment, account type, or product type) to ensure you match the exact case stored in the database. Furthermore, always wrap comparisons in LOWER() on both sides (e.g. `LOWER(account_type) = LOWER('checking')`) as a defensive measure.
    11. **Window Function Partition Ordering**: When calculating trailing moving averages (e.g., trailing 3-month moving average of payments), always order the window by the date/time column in ASCENDING (`ASC`) order. If you order by `DESC`, the 'preceding' rows will be empty for the most recent month, resulting in a single-month value rather than a trailing average.
    12. **Parent Row Multiplication in Joins**: Joining a parent table to a child table multiplies the parent rows in the join result. If you aggregate metrics from the parent table (like counting unique parent entities or sum of parent balances) after the join, you must use `DISTINCT` (e.g. `COUNT(DISTINCT parent.id)`) to avoid inflated calculations. Alternatively, always pre-aggregate child metrics in a CTE first before joining to the parent.
    
    Always use the tools to find the schema before writing queries. Do not assume table structures.
    """,
    tools=[kcmd_mcp, execute_sql],
)

app = App(
    root_agent=root_agent,
    name="app",
)
