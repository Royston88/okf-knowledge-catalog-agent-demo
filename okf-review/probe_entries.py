#!/usr/bin/env python3
"""Probe: what does a LIVE `@bigquery` entry actually carry at `view=ALL`?

Four questions, none of which can be answered offline, and three of which
change the design (plan Phase 0a):

  1. Does a live `Aspect` carry `createTime`/`updateTime`? kcmd's own type
     declares only `{aspectType?, data?}`, so its absence there is evidence
     about kcmd, not about the API. The Phase 5 drift fast path — "name the
     changed CHANNEL without diffing a byte" — assumes yes.
  2. Which aspects actually exist on these entries? Sets the tier-A mirror
     scope from evidence rather than from remembered names.
  3. Does the `schema` aspect carry BigQuery's native COLUMN descriptions? If
     it does, the tier-A cache and the tier-C `descriptions` aspect hold two
     different sets of column prose and the bundle must show both without
     implying they are one value.
  4. Are BigQuery's own table/column descriptions even populated here? These
     tables came from a copy script, so the question may be moot.

Read-only. Writes `_state/probe_entries.json` (tracked, as Measurement
evidence, alongside `g_*.json`) and prints the summary that goes in
docs/MEASUREMENTS.md.

    python okf-review/probe_entries.py
"""
import json
import os
import pathlib
import subprocess
import sys
import urllib.request

PROJECT = os.environ.get("OKF_PROJECT", "royston-dev-8253")
LOCATION = os.environ.get("OKF_LOCATION", "us")
DATASET = os.environ.get("OKF_BQ_DATASET", "cymbal_bank_v6z_scaffold_demo_copy")
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "_state" / "probe_entries.json"


def token() -> str:
    """The push identity, explicitly. Never the globally active gcloud config."""
    tok = os.environ.get("KCMD_ACCESS_TOKEN")
    if tok:
        return tok
    return subprocess.check_output(
        ["gcloud", "auth", "print-access-token"], text=True
    ).strip()


def get(url: str, tok: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def entry_url(entry_id: str) -> str:
    # The entry id contains literal slashes and is NOT percent-encoded: encoding
    # it returns a bare 404 that reads exactly like "the entry does not exist".
    return (
        f"https://dataplex.googleapis.com/v1/projects/{PROJECT}/locations/{LOCATION}"
        f"/entryGroups/@bigquery/entries/{entry_id}?view=ALL"
    )


def main() -> int:
    tok = token()
    bundle = ROOT / "okf-bundle"
    tables = sorted(
        p.stem for p in (bundle / "tables").glob("*.md") if p.stem != "index"
    )
    prefix = f"bigquery.googleapis.com/projects/{PROJECT}/datasets/{DATASET}"
    targets = [(f"tables/{t}", f"{prefix}/tables/{t}") for t in tables]
    targets.append((f"datasets/{DATASET}", prefix))

    out = {"project": PROJECT, "location": LOCATION, "dataset": DATASET, "entries": {}}
    aspect_ids: dict[str, int] = {}
    ts_ok = 0
    for rel, entry_id in targets:
        e = get(entry_url(entry_id), tok)
        aspects = e.get("aspects") or {}
        rec = {
            "entryType": e.get("entryType"),
            "createTime": e.get("createTime"),
            "updateTime": e.get("updateTime"),
            "entrySource": e.get("entrySource"),
            "aspects": {},
        }
        for key, a in aspects.items():
            aid = key.split(".")[-1]
            aspect_ids[aid] = aspect_ids.get(aid, 0) + 1
            if a.get("createTime") and a.get("updateTime"):
                ts_ok += 1
            rec["aspects"][key] = {
                "createTime": a.get("createTime"),
                "updateTime": a.get("updateTime"),
                "aspectSource": a.get("aspectSource"),
                "dataKeys": sorted((a.get("data") or {}).keys()),
            }
        # Q3: does the schema aspect carry column descriptions?
        sk = next((k for k in aspects if k.endswith(".schema")), None)
        if sk:
            fields = (aspects[sk].get("data") or {}).get("fields") or []
            rec["schemaFieldKeys"] = sorted({k for f in fields for k in f})
            rec["schemaFieldsWithDescription"] = sum(
                1 for f in fields if f.get("description")
            )
            rec["schemaFieldCount"] = len(fields)
        out["entries"][rel] = rec

    # Q4: BigQuery's OWN descriptions, read from BigQuery rather than the catalog.
    bq = {}
    for t in tables:
        raw = subprocess.check_output(
            ["bq", f"--project_id={PROJECT}", "--format=prettyjson", "show",
             f"{PROJECT}:{DATASET}.{t}"], text=True)
        d = json.loads(raw)
        bq[f"tables/{t}"] = {
            "description": d.get("description"),
            "columnsWithDescription": sum(
                1 for f in d["schema"]["fields"] if f.get("description")),
            "columnCount": len(d["schema"]["fields"]),
        }
    raw = subprocess.check_output(
        ["bq", f"--project_id={PROJECT}", "--format=prettyjson", "show",
         f"{PROJECT}:{DATASET}"], text=True)
    bq[f"datasets/{DATASET}"] = {"description": json.loads(raw).get("description")}
    out["bigqueryNative"] = bq

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    n_aspects = sum(len(r["aspects"]) for r in out["entries"].values())
    print(f"entries probed          {len(out['entries'])}")
    print(f"aspects seen            {n_aspects}")
    print(f"Q1 aspect timestamps    {ts_ok}/{n_aspects} carry createTime AND updateTime")
    print("Q2 aspect inventory     " + ", ".join(
        f"{k} x{v}" for k, v in sorted(aspect_ids.items())))
    sd = sum(r.get("schemaFieldsWithDescription", 0) for r in out["entries"].values())
    sf = sum(r.get("schemaFieldCount", 0) for r in out["entries"].values())
    keys = sorted({k for r in out["entries"].values()
                   for k in r.get("schemaFieldKeys", [])})
    print(f"Q3 schema.fields keys   {keys}")
    print(f"   with a description   {sd}/{sf}")
    bqt = sum(1 for v in bq.values() if v.get("description"))
    bqc = sum(v.get("columnsWithDescription", 0) for v in bq.values())
    bqn = sum(v.get("columnCount", 0) for v in bq.values())
    print(f"Q4 BQ native table desc {bqt}/{len(bq)} populated")
    print(f"   BQ native col desc   {bqc}/{bqn} populated")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
