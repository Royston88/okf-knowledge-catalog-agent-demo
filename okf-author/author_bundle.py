#!/usr/bin/env python3
"""Author the OKF bundle with reference_agent, grounded on the KC capture.

`reference_agent`'s stock BigQuerySource reads BigQuery and nothing else: its
`read_concept` returns schema, row/byte counts, partitioning and clustering, and
`sample_rows` returns 5 rows. It touches **no Dataplex metadata at all** — no
aspects, no profile statistics, no glossary, no lineage. So out of the box the
author cannot see anything a Knowledge Catalog scan produced.

`Source.read_concept` is declared `-> dict[str, Any]` with no schema constraint,
so the fix is a subclass rather than a new tool: merge the frozen KC capture into
the dict the agent already fetches via `read_concept_raw`. Adding a bespoke
filesystem tool instead would sidestep the `get_context().source` rhythm every
existing tool follows.

Run (identity comes from the gc wrapper + an explicit ADC file — see README):

    OKF_KC_DIR=../kc-capture python author_bundle.py \
        --dataset royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy \
        --out ../okf-kb-workspace/catalog \
        --model gemini-3.5-flash
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from reference_agent.runner import ReferenceRunner
from reference_agent.sources.base import ConceptRef
from reference_agent.sources.bigquery import BigQuerySource

# Keep the injected payload bounded. The raw profile JSON runs to tens of KB per
# table (top_n_values alone can be hundreds of entries); the stock tools return
# small predictable shapes and the agent's context should not be flooded.
TOP_N = 6


class KCBigQuerySource(BigQuerySource):
    """BigQuerySource + the Knowledge Catalog capture for the same dataset."""

    name = "bq+kc"

    def __init__(self, dataset: str, kc_dir: Path, billing_project: str | None = None):
        super().__init__(dataset=dataset, billing_project=billing_project)
        self.kc_dir = Path(kc_dir)
        rel = self.kc_dir / "relationships.json"
        self._joins: list[dict[str, Any]] = []
        if rel.is_file():
            data = json.loads(rel.read_text(encoding="utf-8"))
            for link in data.get("links", []):
                self._joins.extend(link.get("joins", []))

    # -- helpers ---------------------------------------------------------
    def _profile_for(self, table: str) -> dict[str, Any] | None:
        path = self.kc_dir / "profile" / f"{table}.json"
        if not path.is_file():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        fields = []
        for f in raw.get("profile", {}).get("fields", []):
            p = f.get("profile", {}) or {}
            top = [
                {"value": v.get("value"), "count": v.get("count"), "ratio": v.get("ratio")}
                for v in (p.get("top_n_values") or [])[:TOP_N]
            ]
            entry: dict[str, Any] = {"name": f.get("name")}
            for k in ("distinct_ratio", "null_ratio", "average", "min", "max"):
                if p.get(k) is not None:
                    entry[k] = p[k]
            if top:
                entry["top_values"] = top
            fields.append(entry)
        return {"row_count": raw.get("row_count"), "fields": fields}

    def _joins_for(self, table: str) -> list[dict[str, Any]]:
        out = []
        for j in self._joins:
            if table in (j.get("source_table"), j.get("target_table")):
                out.append({
                    "source": f"{j.get('source_table')}.{','.join(j.get('source_fields') or [])}",
                    "target": f"{j.get('target_table')}.{','.join(j.get('target_fields') or [])}",
                    "inference_source": j.get("inference_source"),
                })
        return out

    # -- the one override ------------------------------------------------
    def read_concept(self, ref: ConceptRef) -> dict[str, Any]:
        d = super().read_concept(ref)
        kind = ref.id[0] if ref.id else None

        if kind == "tables":
            table = ref.hint.get("table_id") or ref.hint.get("family_prefix") or ref.id[-1]
            profile = self._profile_for(table)
            if profile:
                d["kc_data_profile"] = profile
                d["kc_data_profile_note"] = (
                    "Dataplex DATA_PROFILE over 100% of rows. `distinct_ratio` is "
                    "distinct/rows (1.0 = unique); `null_ratio` is the fraction null; "
                    "`top_values` are the most frequent values. These are measured "
                    "facts about this table — prefer them over assumptions."
                )
            joins = self._joins_for(table)
            if joins:
                d["kc_schema_joins"] = joins
                d["kc_schema_joins_note"] = (
                    "Relationships proposed by the Dataplex dataset-scope "
                    "DATA_DOCUMENTATION scan. `inference_source: AGENT` means "
                    "LLM-inferred and NOT verified — they may be incomplete, "
                    "directionally reversed, or ambiguous where several paths "
                    "connect the same pair. Carry no cardinality."
                )
        elif kind == "datasets":
            d["kc_schema_joins_all"] = [
                {"source": f"{j.get('source_table')}.{','.join(j.get('source_fields') or [])}",
                 "target": f"{j.get('target_table')}.{','.join(j.get('target_fields') or [])}",
                 "inference_source": j.get("inference_source")}
                for j in self._joins
            ]
        return d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", required=True, help="project.dataset")
    ap.add_argument("--out", required=True, type=Path, help="bundle root")
    ap.add_argument("--kc-dir", type=Path,
                    default=Path(os.environ.get("OKF_KC_DIR", "../kc-capture")))
    ap.add_argument("--model", default="gemini-3.5-flash")
    ap.add_argument("--billing-project", default=None)
    ap.add_argument("--concept", action="append", default=None,
                    help="restrict to concept id(s), e.g. tables/accounts")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if not (args.kc_dir / "relationships.json").is_file():
        print(f"error: no KC capture at {args.kc_dir} "
              f"(expected relationships.json + profile/)", file=sys.stderr)
        return 2

    source = KCBigQuerySource(dataset=args.dataset, kc_dir=args.kc_dir,
                              billing_project=args.billing_project)
    concepts = source.list_concepts()
    print(f"source {source.name}: {len(concepts)} concept(s); "
          f"KC capture {args.kc_dir} ({len(source._joins)} join(s))", file=sys.stderr)

    runner = ReferenceRunner(source=source, bundle_root=args.out,
                             model=args.model, web_seeds=None, verbose=args.verbose)
    only = [tuple(c.split("/")) for c in args.concept] if args.concept else None
    written = runner.enrich_all(only=only)
    print(f"wrote {written} concept doc(s) -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
