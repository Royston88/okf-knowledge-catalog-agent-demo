#!/usr/bin/env python3
"""Phase 8 — Arm K (kcmd MCP over the OKF bundle) vs Arm D (Knowledge Catalog MCP, live).

NOT A CONTEST. The plan says so and the measurement bears it out: the two arms do
not have comparable tool surfaces, so a score difference is not evidence about
OKF. Report the confound, do not bury it.

  Arm K    tools: list-entries, lookup-entry, modify-entry  (kcmd MCP — NO SEARCH)
  Arm D    tools: the prebuilt dataplex toolbox             (search_entries,
                  lookup_entry, search_aspect_types, …)
  Arm Dall tools: identical to Arm D, but every `lookup_entry` call is FORCED to
                  `view=4 (ALL)` by a before_tool_callback.

WHY Dall EXISTS. `lookup_entry`'s `view` defaults to `2 (FULL)`, and Dataplex's
FULL means "all required aspects and the KEYS of non-required aspects". The
concept body lives in `overview`, which is not required, so the default view
returns its key and withholds its content — 3,619 chars against 18,171 at
`view=4 (ALL)`. Arm D was structurally unable to read the enrichment projected
onto the entries it was querying. Dall isolates that: same server, same prompt,
same catalog, one argument forced.

Arm K can only enumerate and fetch by exact name; Arm D can search semantically.
That is a property of the two MCP servers, not of the metadata behind them.

THE INSTRUCTION IS DELIBERATELY MINIMAL. The bq-kc-agent scaffold ships a system
prompt carrying ten hand-written modelling rules — fan traps, de-duplication,
zero-fill cohorts, SCD2. Those encode exactly the knowledge the OKF bundle is
supposed to supply, so reusing that prompt would answer the questions from the
prompt and measure nothing. Both arms get the same minimal instruction; the
metadata channel is the only variable.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import re
import shutil
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROJECT = "royston-dev-8253"
DATASET = "cymbal_bank_v6z_scaffold_demo_copy"
MODEL = os.environ.get("OKF_AGENT_MODEL", "gemini-2.5-flash")

INSTRUCTION = f"""You are a data analyst answering questions about the BigQuery
dataset `{PROJECT}.{DATASET}`.

Use your metadata tools to discover the tables and to understand what the data
means before writing any SQL. Then use execute_sql to run a query and answer.

Table names in SQL must be written as `{PROJECT}.{DATASET}.TABLE`.

Give the final answer as a single number on its own last line, prefixed exactly
with `ANSWER: `."""


def execute_sql(sql_query: str) -> dict:
    """Executes a SQL query on BigQuery and returns up to 50 rows."""
    from google.cloud import bigquery
    try:
        rows = [dict(r) for r in bigquery.Client(project=PROJECT).query(sql_query).result()]
        for row in rows:
            for k, v in row.items():
                if not isinstance(v, (str, int, float, bool, type(None))):
                    row[k] = str(v)
        return {"status": "success", "rows": rows[:50]}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "message": str(e)}


# Dataplex EntryView.ALL. `lookup_entry` defaults to FULL (2), which returns
# non-required aspects as keys only — so the `overview` body never reaches the
# model. Forcing the argument is deterministic; instructing the model to pass it
# is not.
ENTRY_VIEW_ALL = 4
_FORCED: list[str] = []


def _force_full_view(tool, args, tool_context):  # noqa: ANN001
    """before_tool_callback: rewrite the args in place, then let the call run.

    ADK hands the callback the SAME dict it later passes to the tool
    (`flows/llm_flows/functions.py`), so mutating it here is what actually
    reaches the server. Returning None means "no override, proceed".
    """
    if tool.name == "lookup_entry" and args.get("view") != ENTRY_VIEW_ALL:
        args["view"] = ENTRY_VIEW_ALL
        _FORCED.append(tool.name)
    return None


def _refresh_armk_bundle() -> None:
    """Re-copy `okf-bundle/` into the Arm K workspace before every run.

    Arm K reads a COPY of the bundle over MCP, and nothing used to create that
    copy — it was made by hand once and then read on every subsequent run.
    Found stale: it was missing the `# Related concepts` back-links, the
    `# Data characteristics` mirror and `log.md`, so an Arm K run would have
    scored a bundle two days behind the source of truth and reported it as the
    bundle's score.

    Same failure as the retired `okf-kb-workspace/catalog/` copy: a second
    on-disk copy of the source of truth that can silently diverge, and did.
    Regenerating it here means the copy cannot be older than the run.
    """
    src = ROOT / "okf-bundle"
    dst = ROOT / "okf-agent" / "armk-workspace" / "bundle"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    n = len(list(dst.rglob("*.md")))
    print(f"[arm K] refreshed workspace bundle from okf-bundle/ ({n} md files)")


def build_agent(arm: str):
    from google.adk.agents import Agent
    from google.adk.models import Gemini
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
    from mcp import StdioServerParameters

    env = os.environ.copy()
    env["GOOGLE_CLOUD_PROJECT"] = PROJECT

    if arm == "K":
        # MUST be the okf-layout workspace, not okf-kb-workspace. The documents
        # layout indexes on `catalogEntry.name`, which clean OKF files do not
        # carry, so pointing the MCP server at okf-kb-workspace makes
        # `list-entries` return ZERO — the Phase 5 blocker resurfacing on the
        # read path. Run 1 of this experiment did exactly that; its transcripts
        # are kept in results_run1_armK_empty_catalog.json.
        _refresh_armk_bundle()
        params = StdioServerParameters(
            command="node",
            args=[str(ROOT / "kcmd" / "run_mcp_server.js"),
                  "--workspace", str(ROOT / "okf-agent" / "armk-workspace")],
            env=env,
        )
    elif arm in ("D", "Dall"):
        # The prebuilt dataplex toolbox reads its target from DATAPLEX_PROJECT /
        # DATAPLEX_LOCATION and refuses to start without the former. Point it at
        # the copy, in the catalog location where the @bigquery entries live —
        # NOT at the plugin cache's default, which is kenly-lakehouse-dev-1.
        env["DATAPLEX_PROJECT"] = PROJECT
        env.setdefault("DATAPLEX_LOCATION", "us")
        params = StdioServerParameters(
            command="npx",
            args=["-y", "@toolbox-sdk/server@>=1.1.0", "--prebuilt", "dataplex", "--stdio"],
            env=env,
        )
    else:
        raise ValueError(arm)

    toolset = McpToolset(connection_params=StdioConnectionParams(
        server_params=params, timeout=120.0))
    return Agent(name=f"arm_{arm}", model=Gemini(model=MODEL),
                 instruction=INSTRUCTION, tools=[toolset, execute_sql],
                 before_tool_callback=_force_full_view if arm == "Dall" else None)


async def ask(arm: str, question: str) -> tuple[str, list[str], int]:
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    _FORCED.clear()
    runner = InMemoryRunner(agent=build_agent(arm), app_name="okf_phase8")
    s = await runner.session_service.create_session(app_name="okf_phase8", user_id="u")
    text, calls = "", []
    async for ev in runner.run_async(
        user_id="u", session_id=s.id,
        new_message=types.Content(role="user", parts=[types.Part(text=question)]),
    ):
        for p in (ev.content.parts if ev.content else []) or []:
            if getattr(p, "function_call", None):
                calls.append(p.function_call.name)
            if getattr(p, "text", None):
                text += p.text
    return text, calls, len(_FORCED)


NUM = re.compile(r"ANSWER:\s*\$?(-?[\d,]+(?:\.\d+)?)")


def classify(text: str, correct: float, trap: float) -> tuple[str, float | None]:
    m = NUM.findall(text or "")
    if not m:
        nums = re.findall(r"(-?[\d,]+\.?\d*)", text or "")
        m = nums[-1:] if nums else []
    if not m:
        return "no_answer", None
    try:
        v = float(m[-1].replace(",", ""))
    except ValueError:
        return "no_answer", None
    tol = max(abs(correct) * 0.005, 0.01)
    if abs(v - correct) <= tol:
        return "correct", v
    if abs(v - trap) <= max(abs(trap) * 0.005, 0.01):
        return "trap", v
    return "other", v


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="K,D")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--out", default=str(ROOT / "okf-agent" / "results.json"))
    a = ap.parse_args()

    qs = yaml.safe_load((ROOT / "okf-agent" / "questions.yaml").read_text())
    results = []
    for rep in range(a.repeats):
      for arm in a.arms.split(","):
        for q in qs:
            try:
                text, calls, forced = await ask(arm, q["question"])
                verdict, value = classify(text, float(q["correct"]), float(q["trap"]))
                err = None
            except Exception as e:  # noqa: BLE001
                text, calls, forced, verdict, value = "", [], 0, "error", None
                err = f"{type(e).__name__}: {e}"[:300]
            print(f"rep{rep} arm {arm} {q['id']}: {verdict:9s} value={value} "
                  f"forced={forced} tools={sorted(set(calls))}{' ERR='+err if err else ''}")
            results.append(dict(rep=rep, arm=arm, id=q["id"], verdict=verdict, value=value,
                                forced_view_calls=forced,
                                tools=sorted(set(calls)), n_tool_calls=len(calls),
                                error=err, text=(text or "")[-1200:]))
            pathlib.Path(a.out).write_text(json.dumps(results, indent=2))
    print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
