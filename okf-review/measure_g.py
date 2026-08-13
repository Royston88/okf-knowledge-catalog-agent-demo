#!/usr/bin/env python3
"""Measurement G — does curated content survive a Knowledge Catalog re-scan?

REFRAMED FROM THE PLAN. The plan watched a `<!-- curated:v1 -->` sentinel inside
the `overview` aspect. Track A established that the `@bigquery` entries have NO
`overview` aspect at all — absent, not empty. What the DATA_DOCUMENTATION scan
actually writes is `descriptions` and `queries`, both stamped `userManaged:
false`. So G is pointed at `descriptions`, and the variable under test is
`userManaged` — Knowledge Catalog's own marker for "content a scan may
overwrite" — rather than the sentinel, which is only how we recognise our text.

Testing the okf aspect instead would be vacuous: no scan owns a custom aspect
type, so its survival is knowable without measuring.

DESIGN — a 2x2 plus untouched controls, so a survival difference can be
attributed to `userManaged` and not to the OKF trust flag or to the table:

  table                 curated?  userManaged  okf `verified`
  accounts              yes       false        FLAGGED
  customers             yes       TRUE         FLAGGED
  account_owners        yes       TRUE         control
  balance_snapshots     yes       false        control
  transactions          no        (false)      FLAGGED     <- untouched control
  wire_transfers        no        (false)      control     <- untouched control

  seed      write curated descriptions per the table above
  snapshot  record the current descriptions state to _state/g_<label>.json
  verify    diff two snapshots and report survival
"""
from __future__ import annotations

import argparse
import copy
import json
import pathlib

from google.cloud import dataplex_v1
from google.protobuf.json_format import MessageToDict, ParseDict

EG = "projects/royston-dev-8253/locations/us/entryGroups/@bigquery"
BASE = ("bigquery.googleapis.com/projects/royston-dev-8253/datasets/"
        "cymbal_bank_v6z_scaffold_demo_copy")
KEY = "655216118709.global.descriptions"
SENTINEL = "<!-- curated:v1 -->"
STATE = pathlib.Path(__file__).resolve().parent.parent / "_state"

# table -> (curate?, set_user_managed)
PLAN = {
    "accounts":          (True,  False),
    "customers":         (True,  True),
    "account_owners":    (True,  True),
    "balance_snapshots": (True,  False),
    "transactions":      (False, None),
    "wire_transfers":    (False, None),
}
ALL_TABLES = ["accounts", "account_owners", "balance_snapshots", "calendar",
              "customers", "customer_segment_history", "investors",
              "loan_applications", "loan_investors", "payments",
              "support_tickets", "transactions", "wire_transfers"]

CURATED = ("{s} CURATED by Phase 6 sign-off. This description was written by a "
           "human reviewer and deliberately replaces the generated text for {t}.")


def entry_name(t: str) -> str:
    return f"{EG}/entries/{BASE}/tables/{t}"


def read(c, t: str) -> dict:
    d = MessageToDict(c.get_entry(request=dataplex_v1.GetEntryRequest(
        name=entry_name(t), view=dataplex_v1.EntryView.ALL))._pb)
    a = d.get("aspects", {}).get(KEY, {}).get("data", {})
    return {
        "userManaged": a.get("userManaged"),
        "description": a.get("description", ""),
        "has_sentinel": SENTINEL in a.get("description", ""),
        "job": (a.get("job") or {}).get("name", "").split("/dataScans/")[-1],
        "run_time": (a.get("job") or {}).get("runTime"),
    }


def seed(c) -> None:
    for t, (curate, um) in PLAN.items():
        if not curate:
            print(f"{t:20s} untouched control")
            continue
        d = MessageToDict(c.get_entry(request=dataplex_v1.GetEntryRequest(
            name=entry_name(t), view=dataplex_v1.EntryView.ALL))._pb)
        data = copy.deepcopy(d["aspects"][KEY]["data"])
        data["description"] = CURATED.format(s=SENTINEL, t=t)
        if um is not None:
            data["userManaged"] = um
        entry = dataplex_v1.Entry(name=entry_name(t))
        asp = dataplex_v1.Aspect()
        ParseDict(data, asp._pb.data)
        entry.aspects[KEY] = asp
        try:
            c.update_entry(request=dataplex_v1.UpdateEntryRequest(
                entry=entry, update_mask={"paths": ["aspects"]}, aspect_keys=[KEY]))
            got = read(c, t)
            print(f"{t:20s} wrote curated, requested userManaged={um} -> "
                  f"stored {got['userManaged']}, sentinel={got['has_sentinel']}")
        except Exception as ex:  # noqa: BLE001
            print(f"{t:20s} WRITE FAILED: {type(ex).__name__}: {str(ex)[:160]}")


def snapshot(c, label: str) -> None:
    STATE.mkdir(exist_ok=True)
    out = {t: read(c, t) for t in ALL_TABLES}
    p = STATE / f"g_{label}.json"
    p.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"wrote {p}")
    for t in ALL_TABLES:
        r = out[t]
        print(f"  {t:26s} um={str(r['userManaged']):5s} sentinel={str(r['has_sentinel']):5s} "
              f"run={r['run_time']}")


# Tables whose DATA_DOCUMENTATION scan job was triggered and reported SUCCEEDED
# for this measurement. Recorded explicitly because an unchanged `run_time`
# CANNOT be used to infer "no scan ran" — see the note in verify().
RESCANNED = {"accounts", "customers", "account_owners", "balance_snapshots",
             "transactions", "wire_transfers"}


def verify(before: str, after: str) -> None:
    b = json.loads((STATE / f"g_{before}.json").read_text())
    a = json.loads((STATE / f"g_{after}.json").read_text())
    # A protected aspect keeps its ORIGINAL job stamp, because the scan declines
    # to write to it at all. So a stale run_time on a re-scanned table is
    # evidence OF protection, not evidence the scan was skipped. Ground truth
    # for "did a scan run" is the job state, captured in RESCANNED.
    print(f"{'table':26s} {'userManaged':12s} {'scan ran':9s} "
          f"{'aspect rewritten':17s} {'sentinel':13s} verdict")
    for t in ALL_TABLES:
        rb, ra = b[t], a[t]
        ran = t in RESCANNED
        rewritten = rb["run_time"] != ra["run_time"]
        if not rb["has_sentinel"]:
            verdict = "-- not curated"
        elif not ran:
            verdict = "inconclusive (no scan)"
        elif ra["has_sentinel"]:
            verdict = "SURVIVED"
        else:
            verdict = "OVERWRITTEN"
        print(f"{t:26s} {str(rb['userManaged']):12s} {str(ran):9s} "
              f"{str(rewritten):17s} {str(rb['has_sentinel'])+'->'+str(ra['has_sentinel']):13s} {verdict}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    s = sub.add_parser("snapshot"); s.add_argument("label")
    v = sub.add_parser("verify"); v.add_argument("before"); v.add_argument("after")
    a = ap.parse_args()
    c = dataplex_v1.CatalogServiceClient()
    if a.cmd == "seed":
        seed(c)
    elif a.cmd == "snapshot":
        snapshot(c, a.label)
    else:
        verify(a.before, a.after)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
