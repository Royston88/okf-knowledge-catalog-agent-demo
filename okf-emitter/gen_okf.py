#!/usr/bin/env python3
"""Third emitter: spec.yaml -> OKF concepts, alongside gen_graph and gen_lookml.

The same `spec.yaml` that produces the BigQuery property graph and the LookML
model also produces a set of OKF concept documents. Whatever the LookML explore
enforces structurally, this states in prose a reader can consult.

**These are documentation of semantics, not a semantic layer.** A LookML explore
makes the fan trap unwritable (symmetric aggregates); an OKF join concept
describes it and hopes the reader heeds it. Nothing parses these as structure.

Scope: this emitter owns `references/joins/**` and `references/metrics/**` only.
Table and dataset concepts are authored by reference_agent — it enumerates the
concept set from BigQuery and cannot invent concepts, which is exactly why the
joins and metrics have to come from here.

Determinism: `generated.at` is an explicit input (`--generated-at`, defaulting to
the spec file's mtime), never wall-clock, so re-emitting from the same spec is
byte-identical. The repo freezes snapshots by sha256; an emitter that embeds
now() would defeat that.

Run:
    python gen_okf.py --spec spec.yaml --out ../okf-bundle
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Reuse the real generator's contract check and helpers — no existing function is
# modified. validate_spec is the same gate gen_graph/gen_lookml run behind.
from generate_models import validate_spec, table_singular, _as_list  # noqa: E402

GENERATED_BY = "generate_models/okf"


# ---------------------------------------------------------------- frontmatter
def _fm(d: dict) -> str:
    order = ["type", "resource", "title", "description", "tags",
             "status", "generated", "sources"]
    out = {k: d[k] for k in order if d.get(k) is not None}
    for k, v in d.items():
        if k not in out and v is not None:
            out[k] = v
    return "---\n" + yaml.safe_dump(out, sort_keys=False, width=100).rstrip() + "\n---\n\n"


def _doc(meta: dict, body: str) -> str:
    return _fm(meta) + body.strip() + "\n"


def _base_meta(spec: dict, at: str, kind: str, title: str, desc: str, tags: list[str]) -> dict:
    return {
        "type": kind,
        "title": title,
        "description": desc,
        "tags": tags,
        "status": "stable",
        "generated": {"by": GENERATED_BY, "at": at},
        "sources": [{
            "id": "spec",
            "resource": f"bq-modeling-spec://{spec['project']}/{spec['dataset']}",
            "title": "Reviewed BI modeling spec (layer1_structure + layer2_semantics)",
        }],
    }


def _tbl_link(t: str) -> str:
    return f"[{t}](../../tables/{t}.md)"


# ---------------------------------------------------------------------- joins
def _join_docs(spec: dict, at: str) -> dict[str, str]:
    l1 = spec["layer1_structure"]
    l2 = spec.get("layer2_semantics") or {}
    dedup = l2.get("dedup") or {}
    tables = l1["tables"]
    out: dict[str, str] = {}

    def dedup_note(t: str) -> str:
        d = dedup.get(t)
        if not d:
            return ""
        return (f"\n> **{t} must be de-duplicated first.** It carries duplicate loads; take one row "
                f"per `{d['partition_by']}` ordered by `{d['order_by']}` before aggregating, or every "
                f"measure over it is overstated.\n")

    for r in l1["relationships"]:
        parent, child, fk = r["parent"], r["child"], r["fk"]
        label, alias, as_of = r.get("label", "relates to"), r.get("alias"), r.get("as_of")
        name = f"{parent}__{child}" + (f"__{alias}" if alias else "")
        ppk = _as_list(tables.get(parent, {}).get("primary_key") or [fk])[0]
        title = f"{parent} → {child}" + (f" ({alias})" if alias else "")
        desc = (f"One {table_singular(parent, tables)} {label} many "
                f"{child} rows, joined on {fk}.")
        body = [
            f"`{parent}` **one-to-many** `{child}`.\n",
            "| | |", "|---|---|",
            f"| Parent | {_tbl_link(parent)} (`{ppk}`) |",
            f"| Child | {_tbl_link(child)} (`{fk}`) |",
            "| Cardinality | **1:N** — one parent row, many child rows |",
        ]
        if alias:
            body.append(f"| Role | `{alias}` — this table joins {parent} more than once; "
                        f"pick the role deliberately |")
        if as_of:
            body.append(f"| Effective-dated | `{as_of}` — pick the version valid at the "
                        f"reporting instant, not all versions |")
        body.append("")
        body.append(
            f"```sql\n{parent}.{ppk} = {child}.{fk}\n```\n\n"
            f"**Fan-out.** Because this is 1:N, joining {child} to {parent} repeats each "
            f"{table_singular(parent, tables)} row once per matching {child} row. Any measure on "
            f"`{parent}` aggregated *after* this join is multiplied by the child count. Aggregate "
            f"each side separately and join the pre-aggregated results on `{fk}`."
        )
        body.append(dedup_note(parent))
        body.append(dedup_note(child))
        out[f"references/joins/{name}.md"] = _doc(
            _base_meta(spec, at, "Join", title, desc,
                       ["join", "one-to-many", parent, child]), "\n".join(body))

    for bridge, info in (l1.get("bridges") or {}).items():
        (a, ak), (b, bk) = list(info["between"].items())
        m2n = (l2.get("m2n") or {}).get(bridge) or {}
        entity, allocation = m2n.get("entity"), m2n.get("allocation")
        desc = f"{a} and {b} are many-to-many; {bridge} is the bridge that resolves them."
        body = [
            f"`{a}` **many-to-many** `{b}`, resolved through the bridge {_tbl_link(bridge)}.\n",
            "| | |", "|---|---|",
            f"| Side A | {_tbl_link(a)} (`{ak}`) |",
            f"| Side B | {_tbl_link(b)} (`{bk}`) |",
            f"| Bridge | {_tbl_link(bridge)} |",
            "| Cardinality | **M:N** |",
        ]
        if allocation:
            body.append(f"| Allocation | `{allocation}` — how a measure on "
                        f"`{entity}` is apportioned across the bridge |")
        body.append("")
        body.append(
            f"```sql\n{a}.{ak} = {bridge}.{ak}\n  AND {bridge}.{bk} = {b}.{bk}\n```\n\n"
            f"**Double counting.** Traversing the bridge repeats each `{a}` row once per related "
            f"`{b}` row (and vice versa). A plain `SUM` over `{entity or a}` across this join "
            f"double counts."
            + (f" The declared treatment is `{allocation}`: count each "
               f"{table_singular(entity or a, tables)} once rather than once per partner.\n"
               if allocation == "count_once" else "\n")
        )
        body.append(dedup_note(a)); body.append(dedup_note(b))
        out[f"references/joins/{a}__{b}__via_{bridge}.md"] = _doc(
            _base_meta(spec, at, "Join", f"{a} ↔ {b} (via {bridge})", desc,
                       ["join", "many-to-many", "bridge", a, b]), "\n".join(body))
    return out


# -------------------------------------------------------------------- metrics
_TYPE_NOTE = {
    "additive": "Additive — safe to SUM across every dimension.",
    "filtered_sum": "Additive over a filtered subset.",
    "ratio": "Ratio — compute numerator and denominator separately, then divide. "
             "Never average a ratio.",
    "filtered_ratio": "Ratio over a filtered subset; the denominator must include rows "
                      "with zero matches or the average is overstated.",
    "rate": "Weighted rate — weight by the declared column, never a plain AVG.",
    "semi_additive": "**Semi-additive** — additive across every dimension EXCEPT the period. "
                     "Pick a single period; summing across periods double counts.",
    "semi_additive_avg": "**Semi-additive average** — average the per-period totals; do not "
                         "average the raw rows.",
    "allocated_sum": "**Allocated** across a many-to-many bridge — apportion, do not SUM.",
    "milestone_lag": "Elapsed time between two milestone dates.",
    "period_over_period": "Period-over-period comparison against the same measure shifted "
                          "one period.",
    "cumulative": "Running total ordered by the declared column.",
    "moving_avg": "Moving average over the declared window.",
    "percent_of_total": "Share of a partition total.",
    "aggregate": "Plain aggregate.",
}


def _metric_docs(spec: dict, at: str) -> dict[str, str]:
    l1, l2 = spec["layer1_structure"], (spec.get("layer2_semantics") or {})
    dedup, snapshots = l2.get("dedup") or {}, l1.get("snapshots") or {}
    out: dict[str, str] = {}
    for m in l2.get("measures") or []:
        table, name, mtype = m["table"], m["name"], m["type"]
        desc = (m.get("description") or "").strip().split(". ")[0].rstrip(".")
        desc = (desc + ".") if desc else f"{mtype.replace('_', ' ')} measure on {table}."
        rows = [f"| Table | {_tbl_link(table)} |", f"| Type | `{mtype}` |"]
        for k in ("column", "numerator", "denominator", "weight_by", "period", "order_by",
                  "window", "partition_by", "agg", "filter_field", "filter_value",
                  "amount_table", "amount_column", "weight", "from", "to", "unit", "base"):
            if m.get(k) is not None:
                rows.append(f"| `{k}` | `{m[k]}` |")
        body = [f"**{_TYPE_NOTE.get(mtype, mtype)}**\n", "| | |", "|---|---|", *rows, ""]
        if m.get("description"):
            body.append(m["description"].strip() + "\n")
        if table in dedup:
            d = dedup[table]
            body.append(
                f"> **Precondition — de-duplicate `{table}` first.** One row per "
                f"`{d['partition_by']}` ordered by `{d['order_by']}`. Computed over the raw "
                f"table this measure is overstated.\n")
        if table in snapshots:
            s = snapshots[table]
            body.append(
                f"> **Precondition — single period.** `{table}` is a snapshot keyed on "
                f"`{s['entity_key']}` per `{s['period']}`. Constrain to one `{s['period']}`; "
                f"summing across periods counts the same {s['singular_label']} repeatedly.\n")
        out[f"references/metrics/{table}__{name}.md"] = _doc(
            _base_meta(spec, at, "Metric", f"{name} ({table})", desc,
                       ["metric", mtype, table]), "\n".join(body))
    return out


# --------------------------------------------------------------------- public
def gen_okf(spec: dict, at: str) -> dict[str, str]:
    """spec -> {relative path: OKF concept markdown}. Pure; no I/O."""
    docs = {}
    docs.update(_join_docs(spec, at))
    docs.update(_metric_docs(spec, at))
    for folder, title in (("references/joins", "Joins"), ("references/metrics", "Metrics")):
        kids = sorted(p for p in docs if p.startswith(folder + "/"))
        lines = [f"# {title}", ""]
        for p in kids:
            stem = Path(p).stem
            lines.append(f"* [{stem}]({stem}.md)")
        docs[f"{folder}/index.md"] = "\n".join(lines) + "\n"
    docs["references/index.md"] = (
        "# References\n\n* [joins](joins/index.md)\n* [metrics](metrics/index.md)\n")
    return docs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True, help="bundle root (concepts land under references/)")
    ap.add_argument("--generated-at", default=None,
                    help="ISO-8601 for generated.at (default: the spec file's mtime). "
                         "Explicit so re-emission is byte-identical.")
    args = ap.parse_args()

    spec = yaml.safe_load(open(args.spec))
    for w in validate_spec(spec):
        print(f"WARNING: {w}", file=sys.stderr)

    at = args.generated_at or _dt.datetime.fromtimestamp(
        os.path.getmtime(args.spec), tz=_dt.timezone.utc).isoformat(timespec="seconds")

    docs = gen_okf(spec, at)
    root = Path(args.out)
    for rel, content in sorted(docs.items()):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    n_joins = sum(1 for k in docs if k.startswith("references/joins/") and not k.endswith("index.md"))
    n_metrics = sum(1 for k in docs if k.startswith("references/metrics/") and not k.endswith("index.md"))
    print(f"wrote {n_joins} join + {n_metrics} metric concept(s) "
          f"(+3 index) -> {root}  [generated.at={at}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
