#!/usr/bin/env python3
"""Count what actually landed in an EntryGroup, at `view=ALL`.

The repo's failure mode is the silent plausible success: `kcmd push` says
"Successfully pushed catalog entries" whether it wrote 58 entries or none. So
the interop claim is not "the push exited 0" — it is this inventory.

    python okf-review/count_entrygroup.py okf_interop_scratch
    python okf-review/count_entrygroup.py okf_cymbal_v6z --expect-concepts 44
"""
import argparse
import collections
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

PROJECT = os.environ.get("OKF_PROJECT", "royston-dev-8253")
LOCATION = os.environ.get("OKF_LOCATION", "us")
BASE = "https://dataplex.googleapis.com/v1"
SIGNAL = ["okf_type", "generated", "sources", "verified", "status",
          "stale_after", "title", "tags"]


def token() -> str:
    tok = os.environ.get("KCMD_ACCESS_TOKEN")
    if tok:
        return tok
    return subprocess.check_output(
        ["gcloud", "auth", "print-access-token"], text=True).strip()


def get(url: str, tok: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def list_entries(group: str, tok: str) -> list[dict]:
    """Every entry in the group, each re-read at `view=ALL`.

    `entries.list` returns names and types only, so the aspect inventory needs a
    per-entry `get`. That is the same reason the Phase 5 differ cannot use the
    list call either.
    """
    out, page = [], ""
    while True:
        url = (f"{BASE}/projects/{PROJECT}/locations/{LOCATION}/entryGroups/{group}"
               f"/entries?pageSize=100" + (f"&pageToken={page}" if page else ""))
        res = get(url, tok)
        out.extend(res.get("entries") or [])
        page = res.get("nextPageToken") or ""
        if not page:
            break
    full = []
    for e in out:
        eid = e["name"].split("/entries/", 1)[1]
        full.append(get(f"{BASE}/projects/{PROJECT}/locations/{LOCATION}"
                        f"/entryGroups/{group}/entries/{eid}?view=ALL", tok))
    return full


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("group")
    ap.add_argument("--expect-concepts", type=int, default=None)
    ap.add_argument("--expect-indexes", type=int, default=None)
    ap.add_argument("--json", action="store_true", help="dump the raw inventory")
    args = ap.parse_args()

    tok = token()
    try:
        entries = list_entries(args.group, tok)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} listing {args.group}: {e.read()[:300].decode()}")
        return 2

    types = collections.Counter()
    aspects = collections.Counter()
    concepts, indexes = [], []
    bodies = signal_complete = 0
    missing_signal = collections.Counter()
    okf_types = collections.Counter()

    # Dataplex auto-creates ONE self-entry per EntryGroup, of type `entrygroup`
    # and named `<group>_entry`. Nothing pushed it and nothing should count it;
    # the first run of this script reported "8 index entries" and the eighth was
    # this. Reported separately rather than filtered silently.
    selfentry = [e for e in entries
                 if str(e.get("entryType")).endswith("/entrygroup")]
    entries = [e for e in entries if e not in selfentry]

    for e in entries:
        eid = e["name"].split("/entries/", 1)[1]
        types[str(e.get("entryType")).split("/")[-1]] += 1
        asp = e.get("aspects") or {}
        for k in asp:
            aspects[k.split(".")[-1]] += 1
        okf = next((asp[k]["data"] for k in asp if k.endswith(".okf")), None)
        ov = next((asp[k]["data"] for k in asp if k.endswith(".overview")), None)
        if ov and (ov.get("content") or "").strip():
            bodies += 1
        if okf is None:
            indexes.append(eid)
            continue
        concepts.append(eid)
        okf_types[str(okf.get("okf_type"))] += 1
        absent = [k for k in SIGNAL if k not in okf]
        # `stale_after` is 0/58 in this bundle and `verified` is not universal,
        # so "all 8 present" is not the bar — "nothing DROPPED that the source
        # had" is, and that is checked offline. Here, report the shape.
        for k in absent:
            missing_signal[k] += 1
        if not absent:
            signal_complete += 1

    print(f"entry group             {args.group}")
    print(f"entries                 {len(entries)} "
          f"(+{len(selfentry)} auto entrygroup self-entry, not ours)")
    print(f"  concepts (okf aspect) {len(concepts)}")
    print(f"  index entries         {len(indexes)}  {sorted(indexes)}")
    print(f"entry types             {dict(types)}")
    print(f"aspects present         {dict(aspects)}")
    print(f"non-empty overview      {bodies}/{len(entries)}")
    print(f"okf_type distribution   {dict(okf_types)}")
    print(f"okf fields absent       {dict(missing_signal)} "
          f"(of {len(concepts)} concepts; all 8 present on {signal_complete})")

    if args.json:
        print(json.dumps({"entries": [e["name"] for e in entries]}, indent=2))

    bad = 0
    if args.expect_concepts is not None and len(concepts) != args.expect_concepts:
        print(f"\nFAIL expected {args.expect_concepts} concepts, got {len(concepts)}")
        bad = 1
    if args.expect_indexes is not None and len(indexes) != args.expect_indexes:
        print(f"FAIL expected {args.expect_indexes} index entries, got {len(indexes)}")
        bad = 1
    if not bad:
        print("\nOK")
    return bad


if __name__ == "__main__":
    sys.exit(main())
