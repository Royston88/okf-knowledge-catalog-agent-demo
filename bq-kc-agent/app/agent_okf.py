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

_CURRENT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _CURRENT_DIR.parent.parent
WORKSPACE_DIR = _REPO_ROOT / "okf-eval" / "armk-workspace"
KCMD_PATH = _REPO_ROOT / "kcmd"

# Refresh bundle in armk-workspace
src_bundle = _REPO_ROOT / "okf-bundle"
dst_bundle = WORKSPACE_DIR / "bundle"
if src_bundle.exists():
    if dst_bundle.exists():
        shutil.rmtree(dst_bundle)
    shutil.copytree(src_bundle, dst_bundle)

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
mcp_env["CLOUDSDK_COMPUTE_REGION"] = "us"

kcmd_mcp = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="node",
            args=[str(KCMD_PATH / "run_mcp_server.js"), "--workspace", str(WORKSPACE_DIR)],
            env=mcp_env,
        ),
        timeout=60.0,
    )
)

INSTRUCTION = f"""You are a data analyst answering questions about the BigQuery dataset `{PROJECT}.{DATASET}`.

Use your metadata tools to discover the tables and to understand what the data means before writing any SQL. Then use execute_sql to run a query and answer.

Table names in SQL must be written as `{PROJECT}.{DATASET}.TABLE`.

Give the final answer as a single number or concise summary answering the user question."""

root_agent = Agent(
    name="okf_bundle_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=INSTRUCTION,
    tools=[kcmd_mcp, execute_sql],
)

app = App(
    root_agent=root_agent,
    name="app",
)
