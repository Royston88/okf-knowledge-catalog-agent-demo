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
    
    Always use the tools to find the schema before writing queries. Do not assume table structures.
    """,
    tools=[kcmd_mcp, execute_sql],
)

app = App(
    root_agent=root_agent,
    name="app",
)
