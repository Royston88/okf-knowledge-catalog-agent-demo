#!/usr/bin/env python3
"""Count the EntryLinks on each `@bigquery` table entry, FOLLOWING PAGINATION.

Pagination is not an optimisation here, it is the correctness condition — this
is kcmd defect 6 in a second implementation. The first version of this count
issued one request per entry and reported `related: 47` where the truth is 58,
because two entries came back with a `nextPageToken` it ignored. Worse, the
boundary is **not** at the 50 the page-size default suggests: `accounts` returned
a token after **10** links. A high-degree entry is therefore not a hypothetical
in this dataset, it is the normal case.

    python okf-review/count_links.py
"""
import collections
import json
import os
import pathlib
import subprocess
import sys
import urllib.parse
import urllib.request

PROJECT = os.environ.get("OKF_PROJECT", "royston-dev-8253")
LOCATION = os.environ.get("OKF_LOCATION", "us")
DATASET = os.environ.get("OKF_BQ_DATASET", "cymbal_bank_v6z_scaffold_demo_copy")
ROOT = pathlib.Path(__file__).resolve().parent.parent


def token() -> str:
    tok = os.environ.get("KCMD_ACCESS_TOKEN")
    if tok:
        return tok
    return subprocess.check_output(
        ["gcloud", "auth", "print-access-token"], text=True).strip()


def lookup_all(entry: str, tok: str) -> tuple[list[dict], int]:
    """Every link touching `entry`, and how many pages it took."""
    out, page, pages = [], "", 0
    while True:
        url = (f"https://dataplex.googleapis.com/v1/projects/{PROJECT}"
               f"/locations/{LOCATION}:lookupEntryLinks"
               f"?entry={urllib.parse.quote(entry, safe='')}"
               + (f"&pageToken={urllib.parse.quote(page, safe='')}" if page else ""))
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
        d = json.load(urllib.request.urlopen(req))
        out.extend(d.get("entryLinks") or [])
        pages += 1
        page = d.get("nextPageToken") or ""
        if not page:
            return out, pages


def main() -> int:
    tok = token()
    tables = sorted(p.stem for p in (ROOT / "okf-bundle" / "tables").glob("*.md")
                    if p.stem != "index")
    prefix = (f"projects/{PROJECT}/locations/{LOCATION}/entryGroups/@bigquery/entries/"
              f"bigquery.googleapis.com/projects/{PROJECT}/datasets/{DATASET}/tables/")

    total = collections.Counter()
    first_page_only = collections.Counter()
    multipage = []
    for t in tables:
        links, pages = lookup_all(prefix + t, tok)
        total.update(l["entryLinkType"].split("/")[-1] for l in links)
        if pages > 1:
            multipage.append((t, len(links), pages))
        # What a page-one-only client would have seen, i.e. the defect-6 blast
        # radius, reported as a number rather than as a warning.
        first, _ = lookup_all(prefix + t, tok) if pages == 1 else (None, None)
        if first is None:
            url = (f"https://dataplex.googleapis.com/v1/projects/{PROJECT}"
                   f"/locations/{LOCATION}:lookupEntryLinks"
                   f"?entry={urllib.parse.quote(prefix + t, safe='')}")
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
            first = (json.load(urllib.request.urlopen(req)).get("entryLinks") or [])
        first_page_only.update(l["entryLinkType"].split("/")[-1] for l in first)

    print(f"tables                  {len(tables)}")
    print(f"links, paginated        {dict(total)}  (total {sum(total.values())})")
    print(f"links, page one only    {dict(first_page_only)}  "
          f"(total {sum(first_page_only.values())})")
    print(f"entries needing >1 page {len(multipage)}  "
          + ", ".join(f"{t}={n} in {p} pages" for t, n, p in multipage))
    if sum(total.values()) != sum(first_page_only.values()):
        print("\n  ^ that difference IS kcmd defect 6. A page-one-only client sees "
              f"{sum(first_page_only.values())} of {sum(total.values())} links, and a "
              "RECONCILER that sees a partial set re-creates what it cannot see "
              "and can never clean up anything past page one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
