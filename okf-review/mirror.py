#!/usr/bin/env python3
r"""The mirrored tier: refresh the bundle's cache of platform-owned facts.

WHY A BUNDLE-ONLY READER NEEDS THIS. Phase 8's Arm K — the arm that scored
11/15 — read the bundle over MCP with **no catalog access at all**. For a reader
like that, what is not in the bundle does not exist. It got column names, types
and descriptions and **zero distributional facts**: no null rates, no
cardinalities, no ranges, no top values. Those are exactly the facts that change
how a query gets written.

THE RULE IS *DISTILLED AND AUTHORED, NEVER MIRRORED* — and this does not break
it, because the test is AUTHORITY, not knowledge-versus-data. Column types and
null rates are plainly knowledge (OKF §4.2 makes `# Schema` a conventional
heading for exactly this). The line is who is authoritative:

  * the bundle is the source of truth for what it AUTHORS, and push is total and
    declarative — what the bundle says, the catalog gets;
  * `schema` and `storage` are authored by BigQuery. Mirroring them asserts an
    authority we neither have nor want, and kcmd correctly DROPS them on push
    for ingested entries. So they are cached here and **never pushed** — the
    offline suite asserts no tier-A aspect ever appears in `expected`.

COMPUTED FROM BIGQUERY, NOT FROM THE `data-profile` ASPECT — for two reasons,
one of principle and one of fact.

  * Of principle: the catalog's profile is reproducible but NOT accurate. It
    reports 1,201 distinct `account_id` where the warehouse has 1,200. RESULTS
    §1's burn was exactly that number copied into authored prose and never
    checked; mirroring it would institutionalise the failure.
  * Of fact: `okf-review/probe_entries.py` found **no `data-profile` aspect on
    any of the 14 entries**. There is nothing to mirror even if we wanted to.

THE MERGE IS FIELD-SCOPED, NEVER FILE-SCOPED. This is the risk the whole tier
carries — a refresh clobbering an authored field is the exact failure rule 3
exists to prevent — so `# Schema` merges **keyed on column name**: Type and Mode
are refreshed from the warehouse, **Description is preserved byte-identical**
because it is ours (tier C, and `userManaged=true` on all 13 tables). A column
that appears in BigQuery and not in the bundle is added and **flagged
undocumented**, never silently blank-filled; a column that disappears is flagged
rather than deleted.

    python okf-review/mirror.py --check     exit 1 if the cache is stale
    python okf-review/mirror.py --write     refresh it
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import pathlib
import re
import sys

import yaml
from google.cloud import bigquery

PROJECT = os.environ.get("OKF_PROJECT", "royston-dev-8253")
DATASET = os.environ.get("OKF_BQ_DATASET", "cymbal_bank_v6z_scaffold_demo_copy")
ROOT = pathlib.Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "okf-bundle"

SCHEMA_HEADING = "# Schema"
CHARS_HEADING = "# Data characteristics"
UNDOCUMENTED = "_Undocumented — added by the warehouse; needs prose._"

# How long a mirrored fact is trusted. OKF §5.5 wants an ABSOLUTE date so
# staleness is a plain comparison with no reference to when the concept was
# read, which means the policy has to live somewhere — here. 90 days is a
# judgement, not a measurement: long enough that a stable warehouse does not
# generate churn, short enough that a year-old cardinality is never quoted as
# current. This is the FIRST defensible use of `stale_after` in this bundle;
# authored prose has no honest ageing date, which is why it stays 0/58 there.
STALE_AFTER_DAYS = 90

# Above this many distinct values a string column gets a count instead of a
# value list. A top-values list is useful precisely when it is short enough to
# constrain a WHERE clause.
TOP_VALUES_MAX_DISTINCT = 12

NUMERIC = {"INTEGER", "INT64", "FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC"}
TEMPORAL = {"DATE", "DATETIME", "TIMESTAMP", "TIME"}


# -------------------------------------------------------------------- identity
def bq_client() -> bigquery.Client:
    """A BigQuery client on the SAME identity the rest of this tooling uses.

    Ambient ADC on this workstation is a different principal from the one that
    owns the catalog project, so a plain `bigquery.Client(project=…)` fails with
    `403 bigquery.tables.get denied` — which reads like a missing grant and is
    actually the wrong identity. `KCMD_ACCESS_TOKEN` is already the explicit,
    deliberate credential everywhere else here (see `config.ts`: the CLI
    otherwise mints one from the globally active gcloud config), so use it when
    it is set and fall back to ADC when it is not.
    """
    tok = os.environ.get("KCMD_ACCESS_TOKEN")
    if tok:
        from google.oauth2.credentials import Credentials
        return bigquery.Client(project=PROJECT, credentials=Credentials(token=tok))
    return bigquery.Client(project=PROJECT)


# --------------------------------------------------------------------- markdown
def split(text: str) -> tuple[dict | None, str]:
    if not text.startswith("---\n"):
        return None, text
    try:
        end = text.index("\n---\n", 3)
    except ValueError:
        return None, text
    return yaml.safe_load(text[4:end]) or {}, text[end + 5:]


def sections(body: str) -> list[tuple[str | None, list[str]]]:
    """Split a body into (top-level heading | None, lines) in order."""
    out: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in body.split("\n"):
        if re.match(r"^#(?!#)\s", line):
            out.append((line.strip(), []))
        else:
            out[-1][1].append(line)
    return out


def rebuild(secs: list[tuple[str | None, list[str]]]) -> str:
    parts = []
    for head, lines in secs:
        chunk = "\n".join(lines).strip()
        if head is None:
            if chunk:
                parts.append(chunk)
            continue
        parts.append(head + ("\n\n" + chunk if chunk else ""))
    return "\n\n".join(parts) + "\n"


def parse_schema_table(lines: list[str]) -> tuple[list[str], list[list[str]], int, int]:
    """(header cells, rows, index of the Type column, index of the Mode column).

    The bundle is NOT uniform — its 13 table concepts were authored by an LLM
    and it invented two layouts, `| Field | Type | Description |` and
    `| Field Name | Type | Mode | Description |`. The columns are located by
    HEADER NAME rather than by position, because assuming a position is what
    made an earlier parser silently produce zero fields for 4 of 13 tables.
    """
    header: list[str] = []
    rows: list[list[str]] = []
    past_sep = False
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.split("|")[1:-1]]
        if not header:
            header = cells
            continue
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            past_sep = True
            continue
        if past_sep:
            rows.append(cells)
    low = [h.lower() for h in header]
    ti = low.index("type") if "type" in low else -1
    mi = low.index("mode") if "mode" in low else -1
    return header, rows, ti, mi


def col_name(cell: str) -> str:
    return cell.replace("`", "").replace("*", "").strip()


# ------------------------------------------------------------------- bigquery
def bq_facts(client: bigquery.Client, table: str) -> dict:
    """Row count, and per-column nulls / distinct / range / top values."""
    ref = client.get_table(f"{PROJECT}.{DATASET}.{table}")
    cols = [(f.name, f.field_type, f.mode) for f in ref.schema]

    parts = ["COUNT(*) AS __rows"]
    for name, ftype, _ in cols:
        q = f"`{name}`"
        parts.append(f"COUNTIF({q} IS NULL) AS `null__{name}`")
        parts.append(f"COUNT(DISTINCT {q}) AS `dist__{name}`")
        if ftype in NUMERIC or ftype in TEMPORAL:
            parts.append(f"MIN({q}) AS `min__{name}`")
            parts.append(f"MAX({q}) AS `max__{name}`")
    sql = (f"SELECT {', '.join(parts)} FROM "
           f"`{PROJECT}.{DATASET}.{table}`")
    row = list(client.query(sql).result())[0]

    facts: dict = {"__rows": row["__rows"], "columns": {}}
    for name, ftype, mode in cols:
        rec = {
            "type": ftype,
            "mode": mode,
            "nulls": row[f"null__{name}"],
            "distinct": row[f"dist__{name}"],
        }
        if f"min__{name}" in row.keys():
            rec["min"], rec["max"] = row[f"min__{name}"], row[f"max__{name}"]
        facts["columns"][name] = rec

    # Top values, only where the list would be short enough to be useful.
    for name, ftype, _ in cols:
        rec = facts["columns"][name]
        if ftype not in ("STRING", "BOOL", "BOOLEAN"):
            continue
        if not (0 < rec["distinct"] <= TOP_VALUES_MAX_DISTINCT):
            continue
        sql = (f"SELECT `{name}` AS v, COUNT(*) AS n FROM "
               f"`{PROJECT}.{DATASET}.{table}` GROUP BY v ORDER BY n DESC")
        rec["top"] = [(r["v"], r["n"]) for r in client.query(sql).result()]
    return facts


def fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def render_characteristics(table: str, facts: dict, at: str) -> list[str]:
    n = facts["__rows"]
    lines = [
        f"_Computed from BigQuery on {at} by `okf-review/mirror.py`. The warehouse "
        f"is authoritative for this section — it is a cache, not an assertion, and "
        f"a refresh overwrites it._",
        "",
        f"**{n:,} rows.**",
        "",
        "| Column | Nulls | Distinct | Range / top values |",
        "| :--- | ---: | ---: | :--- |",
    ]
    for name, rec in facts["columns"].items():
        pct = f"{rec['nulls'] / n * 100:.1f}%" if n else "—"
        nulls = "0" if rec["nulls"] == 0 else f"{rec['nulls']:,} ({pct})"
        detail = ""
        if "top" in rec:
            detail = ", ".join(
                f"`{v}` {c / n * 100:.1f}%" for v, c in rec["top"]) if n else ""
        elif "min" in rec and rec["min"] is not None:
            detail = f"{fmt(rec['min'])} – {fmt(rec['max'])}"
        lines.append(f"| `{name}` | {nulls} | {rec['distinct']:,} | {detail} |")
    # The one fact the row count alone hides, and the one this dataset is built
    # around: a table with duplicate loads has fewer entities than rows.
    key = next(iter(facts["columns"]), None)
    if key and facts["columns"][key]["distinct"] < n:
        lines += ["", f"> **{n:,} rows, {facts['columns'][key]['distinct']:,} "
                      f"distinct `{key}`.** The row count is not the entity count; "
                      f"de-duplicate before aggregating."]
    return lines


# ---------------------------------------------------------------------- merge
def merge_schema(lines: list[str], facts: dict) -> tuple[list[str], list[str]]:
    """Refresh Type/Mode from the warehouse, PRESERVE Description. Keyed on name."""
    header, rows, ti, mi = parse_schema_table(lines)
    if not header:
        return lines, []
    notes: list[str] = []
    by_name = {col_name(r[0]): r for r in rows if r}
    out_rows: list[list[str]] = []

    for name, rec in facts["columns"].items():
        row = by_name.get(name)
        if row is None:
            new = list(row) if row else [""] * len(header)
            new[0] = f"`{name}`"
            if ti >= 0:
                new[ti] = rec["type"]
            if mi >= 0:
                new[mi] = rec["mode"]
            new[-1] = UNDOCUMENTED
            out_rows.append(new)
            notes.append(f"+{name} (new in BigQuery, undocumented)")
            continue
        new = list(row) + [""] * max(0, len(header) - len(row))
        if ti >= 0 and new[ti] != rec["type"]:
            notes.append(f"~{name} type {new[ti]} -> {rec['type']}")
            new[ti] = rec["type"]
        if mi >= 0 and new[mi] != rec["mode"]:
            notes.append(f"~{name} mode {new[mi]} -> {rec['mode']}")
            new[mi] = rec["mode"]
        # new[-1], the Description, is NOT touched. That is the guarantee.
        out_rows.append(new)

    for name in by_name:
        if name not in facts["columns"]:
            notes.append(f"-{name} (in the bundle, NOT in BigQuery)")
            out_rows.append(by_name[name])

    sep = [":---" if i == 0 or i == len(header) - 1 else ":---:"
           for i in range(len(header))]
    table = ["| " + " | ".join(header) + " |",
             "| " + " | ".join(sep) + " |"]
    table += ["| " + " | ".join(r) + " |" for r in out_rows]

    # Keep any prose that surrounded the table.
    prose_before, seen = [], False
    for line in lines:
        if line.strip().startswith("|"):
            seen = True
            continue
        if not seen:
            prose_before.append(line)
    head = "\n".join(prose_before).strip()
    return ([head, ""] if head else []) + table, notes


def refresh(path: pathlib.Path, facts: dict, at: str) -> tuple[str, list[str]]:
    src = path.read_text(encoding="utf-8")
    fm, body = split(src)
    if fm is None:
        return src, []
    secs = sections(body)
    notes: list[str] = []

    for i, (head, lines) in enumerate(secs):
        if head == SCHEMA_HEADING:
            merged, n = merge_schema(lines, facts)
            secs[i] = (head, merged)
            notes += n

    chars = render_characteristics(path.stem, facts, at)
    at_idx = next((i for i, (h, _) in enumerate(secs) if h == CHARS_HEADING), None)
    if at_idx is not None:
        secs[at_idx] = (CHARS_HEADING, chars)
    else:
        # After `# Schema`, before `# Common query patterns`: the reader has just
        # seen the columns and is about to see SQL over them.
        pos = next((i for i, (h, _) in enumerate(secs) if h == SCHEMA_HEADING), None)
        secs.insert(len(secs) if pos is None else pos + 1, (CHARS_HEADING, chars))
        notes.append("+# Data characteristics")

    fm = dict(fm)
    stale = (_dt.date.fromisoformat(at) + _dt.timedelta(days=STALE_AFTER_DAYS))
    fm["stale_after"] = stale.isoformat()

    out = ("---\n"
           + yaml.safe_dump(fm, sort_keys=False, width=100, allow_unicode=True).rstrip()
           + "\n---\n\n" + rebuild(secs).strip() + "\n")
    return out, notes


def selftest() -> int:
    """The merge guarantee, offline: Type refreshes, Description NEVER moves.

    This is the risk the whole tier carries — "a mirror refresh clobbers an
    authored field" is the exact failure rule 3 exists to prevent — so it is
    asserted against a hand-edited table with synthetic warehouse facts rather
    than only observed in a live run. No BigQuery, no credentials.
    """
    lines = [
        "| Field | Type | Description |",
        "| :--- | :--- | :--- |",
        "| `a` | STRING | HAND EDITED, must survive byte-identical. |",
        "| `b` | INTEGER | Another authored one, with a [link](/tables/x.md). |",
        "| `gone` | STRING | Documents a column BigQuery no longer has. |",
    ]
    facts = {"__rows": 10, "columns": {
        "a": {"type": "STRING", "mode": "NULLABLE", "nulls": 0, "distinct": 3},
        # `b` has CHANGED TYPE in the warehouse: INTEGER -> FLOAT.
        "b": {"type": "FLOAT", "mode": "NULLABLE", "nulls": 1, "distinct": 9},
        # `c` is NEW in the warehouse.
        "c": {"type": "DATE", "mode": "REQUIRED", "nulls": 0, "distinct": 10},
    }}
    merged, notes = merge_schema(lines, facts)
    _, rows, ti, _ = parse_schema_table(merged)
    by = {col_name(r[0]): r for r in rows}

    fails = []
    if by["a"][-1] != "HAND EDITED, must survive byte-identical.":
        fails.append(f"authored description for `a` changed: {by['a'][-1]!r}")
    if by["b"][-1] != "Another authored one, with a [link](/tables/x.md).":
        fails.append(f"authored description for `b` changed: {by['b'][-1]!r}")
    if by["b"][ti] != "FLOAT":
        fails.append(f"type for `b` not refreshed: {by['b'][ti]!r}")
    if by["a"][ti] != "STRING":
        fails.append(f"type for `a` wrongly changed: {by['a'][ti]!r}")
    if "c" not in by:
        fails.append("new warehouse column `c` was not added")
    elif by["c"][-1] != UNDOCUMENTED:
        fails.append(f"new column `c` not flagged undocumented: {by['c'][-1]!r}")
    if "gone" not in by:
        fails.append("`gone` was DELETED rather than flagged")
    elif by["gone"][-1] != "Documents a column BigQuery no longer has.":
        fails.append("`gone`'s description was altered")
    if not any(n.startswith("-gone") for n in notes):
        fails.append(f"`gone` was not reported as absent from BigQuery: {notes}")
    if not any(n.startswith("+c") for n in notes):
        fails.append(f"`c` was not reported as new: {notes}")

    # Idempotence: merging the merged result again must be a no-op.
    again, _ = merge_schema(merged, facts)
    if again != merged:
        fails.append("merge is not idempotent")

    for f in fails:
        print(f"  FAIL {f}")
    print(f"mirror selftest: {'OK' if not fails else f'{len(fails)} FAILURE(S)'} "
          f"— types refresh, authored descriptions do not move, "
          f"new columns are flagged, dropped columns are kept and reported")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    g.add_argument("--selftest", action="store_true",
                   help="offline: assert the merge never touches an authored field")
    ap.add_argument("--at", default=_dt.date.today().isoformat(),
                    help="the refresh date (default: today). Explicit so a "
                         "re-run can be byte-identical.")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    client = bq_client()
    tables = sorted(p for p in (BUNDLE / "tables").glob("*.md") if p.stem != "index")

    changed, all_notes = [], []
    for p in tables:
        facts = bq_facts(client, p.stem)
        out, notes = refresh(p, facts, args.at)
        if notes:
            all_notes.append((p.stem, notes))
        if out != p.read_text(encoding="utf-8"):
            changed.append((p, out))

    for stem, notes in all_notes:
        for n in notes:
            print(f"  {stem}: {n}")
    print(f"\n{len(tables)} table concept(s); {len(changed)} would change")

    if args.write:
        for p, out in changed:
            p.write_text(out, encoding="utf-8")
        print(f"refreshed {len(changed)} file(s)")
        return 0
    for p, _ in changed:
        print(f"  stale: {p.relative_to(ROOT)}")
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
