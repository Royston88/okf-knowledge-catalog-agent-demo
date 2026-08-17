import os
import shutil
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

import google.auth
import google.auth.transport.requests

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from .tools import execute_sql

MODEL = os.environ.get("OKF_AGENT_MODEL", "gemini-2.5-flash")
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id")
DATASET = os.environ.get("BIGQUERY_DATASET", "your-bigquery-dataset")

# Get GCP credentials
try:
    credentials, project = google.auth.default()
    if not credentials.valid:
        auth_request = google.auth.transport.requests.Request()
        credentials.refresh(auth_request)
    token = credentials.token
except Exception as e:
    token = None
    project = None

mcp_env = os.environ.copy()
if token:
    mcp_env["KCMD_ACCESS_TOKEN"] = token
mcp_env["GOOGLE_CLOUD_PROJECT"] = PROJECT or project
mcp_env["DATAPLEX_PROJECT"] = PROJECT or project
mcp_env.setdefault("DATAPLEX_LOCATION", "us")

ENTRY_VIEW_ALL = 4


def _force_full_view(tool, args, tool_context):
    """Ensure lookup_entry always fetches view=4 (ALL) to retrieve non-required aspects like overview."""
    if tool.name == "lookup_entry" and args.get("view") != ENTRY_VIEW_ALL:
        args["view"] = ENTRY_VIEW_ALL
    return None


_CURRENT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _CURRENT_DIR.parent.parent
_LOCAL_BUNX = _REPO_ROOT / "kcmd" / "node_modules" / ".bin" / "bunx"
BUNX_CMD = os.environ.get("BUNX_PATH") or shutil.which("bunx") or (str(_LOCAL_BUNX) if _LOCAL_BUNX.exists() else "npx")

kc_mcp = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=BUNX_CMD,
            args=["--yes", "@toolbox-sdk/server@>=1.1.0", "--prebuilt", "dataplex", "--stdio"],
            env=mcp_env,
        ),
        timeout=120.0,
    )
)

INSTRUCTION = f"""You are a data analyst answering questions about the BigQuery dataset `{PROJECT}.{DATASET}`.

Use your metadata tools to discover the tables and to understand what the data means before writing any SQL. Then use execute_sql to run a query and answer.

Table names in SQL must be written as `{PROJECT}.{DATASET}.TABLE`.

Give the final answer as a single number or concise summary answering the user question."""

root_agent = Agent(
    name="knowledge_catalog_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=INSTRUCTION,
    tools=[kc_mcp, execute_sql],
    before_tool_callback=_force_full_view,
)

app = App(
    root_agent=root_agent,
    name="app",
)
