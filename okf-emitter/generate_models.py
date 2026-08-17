"""POC: generate BigQuery property-graph DDL + LookML from a (keys + 1:N) spec.

Proves the playbook's thesis by construction. The spec (specs/cymbal_v6x.yaml) is organized by the
two MODELING LAYERS of PLAYBOOK.md §2 — and the two build STAGES map onto them 1:1:
  LAYER 1 structure  (grains + relationships + columns) -> fan/chasm/zero-fill-safe STRUCTURE
                                            (nodes/edges; LookML views+PK+joins) + dimension exposure
  LAYER 2 semantics  (dedup + m2n + measures + unpivot) -> the derived / business layer: the 4 things
                                            schema can't tell you (dedup, weighting, semi-additivity,
                                            M:N allocation) PLUS every named derived measure

Exposure is a cross-cutting AXIS, not a layer: exposing a structural column (type/hidden) is Layer 1;
naming a derived measure is Layer 2. Whether a measure's formula needed business input is a per-measure
teaching note (a comment in the spec), NOT a block. main() normalizes the two layers into the internal
`schema`/`columns`/`semantics` keys before emitting.

It emits the artifacts AND prints a coverage report showing which scenario each stage unlocks —
making "handle the traps (model correctly) -> the rest of BI rides free" literally visible.

Usage:
  python bi_modeling_playbook/engine/generate_models.py                                  # both layers (full v6x)
  python bi_modeling_playbook/engine/generate_models.py --skip-semantics                 # Layer 1 only (structure + dims)
  python bi_modeling_playbook/engine/generate_models.py --out bi_modeling_playbook/generated/full
  gc <profile> python bi_modeling_playbook/engine/generate_models.py --check-types        # + live BQ type check
"""
from __future__ import annotations

import argparse
import os
import re
import sys

import yaml

from pathlib import Path as _P
_R = _P(__file__).resolve()
while _R != _R.parent and not (_R / "config").is_dir():
    _R = _R.parent                       # repo root = nearest ancestor holding config/
assert (_R / "bi_modeling_playbook").is_dir(), f"repo root not found above {__file__}"
# PLAYBOOK, not this file's dir: `specs/` and `generated/` are siblings of engine/, and
# scaffold_spec.py reads `gm.PLAYBOOK` for its own --out default.
PLAYBOOK = str(_R / "bi_modeling_playbook")
sys.path.insert(0, str(_R / "bi_modeling_playbook" / "scaffold" / "archive"))
# gap 28's ONE rule (scaffold/archive/archive_paths.py), adopted 2026-08-05 by W5. Stdlib only,
# no side effects, so importing it here costs the offline generator nothing.
import archive_paths as _AP   # noqa: E402


# --------------------------------------------------------------------------- helpers
def pk_cols(tbl_spec) -> list[str]:
    pk = tbl_spec["primary_key"]
    return pk if isinstance(pk, list) else [pk]


def _as_list(x) -> list:
    """Coerce a scalar-or-list spec value to a list (so `partition_by`/`order_by` accept both)."""
    return x if isinstance(x, list) else [x]


def _dedup_over(dd: dict) -> str:
    """The `PARTITION BY … ORDER BY …` body for a dedup QUALIFY, from `partition_by`/`order_by`
    (each a column or a list) + optional `order_desc`. Multi-column support lets you keep the
    'current' row of a bitemporal / dual-period snapshot — the ordering IS the business decision."""
    desc = " DESC" if dd.get("order_desc") else ""
    pb = ", ".join(_as_list(dd["partition_by"]))
    ob = ", ".join(f"{c}{desc}" for c in _as_list(dd["order_by"]))
    return f"PARTITION BY {pb} ORDER BY {ob}"


def _latest_cond(period, col_ref, subq_table: str) -> tuple[str, str]:
    """(flag_name, SQL) marking the row(s) at the latest period. `period` is a column or a list (a
    compound / bitemporal period). `col_ref(p)` renders a column reference for the current stack
    (e.g. `${TABLE}.p` for LookML, `dd.p` for a graph node view). The flag name is derived
    deterministically from the FULL period column(s) — never a name-split guess; compound uses a
    lexicographic STRUCT match."""
    pers = _as_list(period)
    if len(pers) == 1:
        p = pers[0]
        return f"is_latest_{p}", f"{col_ref(p)} = (SELECT MAX({p}) FROM {subq_table})"
    order = ", ".join(f"{p} DESC" for p in pers)
    outer = "STRUCT(" + ", ".join(col_ref(p) for p in pers) + ")"
    inner = "(SELECT AS STRUCT " + ", ".join(pers) + f" FROM {subq_table} ORDER BY {order} LIMIT 1)"
    return "is_latest", f"{outer} = {inner}"


def read_patterns(l1: dict) -> dict:
    """Build the {bridges, snapshots} classification from the EXPLICIT `layer1_structure.bridges` /
    `.snapshots` blocks — no shape/name inference. Returns the SAME dict shape the old
    detect_patterns() produced, so the emitters are unchanged:
      bridges[b]   = {"cols": [colA, colB], "between": [tableA, tableB]}   (from `between`)
      snapshots[s] = {"entity_key": <col>, "period": <col|list>}          (from the snapshot block)
    """
    bridges = {b: {"cols": list(info["between"].values()),
                   "between": list(info["between"].keys())}
               for b, info in (l1.get("bridges") or {}).items()}
    snapshots = {s: {"entity_key": info["entity_key"], "period": info["period"]}
                 for s, info in (l1.get("snapshots") or {}).items()}
    # hierarchies (drill paths) and accumulating snapshots (milestone columns) are read through
    # verbatim — the emitters consume them directly (no shape transform needed).
    return {"bridges": bridges, "snapshots": snapshots,
            "hierarchies": l1.get("hierarchies") or {},
            "accumulating": l1.get("accumulating") or {}}


def _pascal(snake: str) -> str:
    """snake_case -> PascalCase (support_ticket -> SupportTicket, person -> Person)."""
    return "".join(w.capitalize() for w in snake.split("_")) or snake


def table_singular(table: str, tables: dict) -> str:
    """Singular (snake_case) for a table = its DECLARED `singular_label` (required; the validator
    guarantees presence). No inference — declared over derived."""
    return tables[table]["singular_label"]


def node_label(table: str, tables: dict) -> str:
    """Graph node label = PascalCase of the table's declared `singular_label`."""
    return _pascal(table_singular(table, tables))


# --- columns-map helpers (layer1_structure.columns value = a type string OR {type, hidden}) -------
def col_type(v) -> str:
    """The LookML type from a columns-map value (a bare type string, or a {type, hidden} mapping)."""
    return v["type"] if isinstance(v, dict) else v


def col_hidden(v) -> bool:
    """Whether a columns-map value declares the dimension hidden (only the {type, hidden} form can)."""
    return bool(v.get("hidden")) if isinstance(v, dict) else False


def col_desc(v) -> str | None:
    """Optional one-line description on a columns-map value (only the dict form carries it)."""
    return v.get("description") if isinstance(v, dict) else None


def _esc_desc(s: str) -> str:
    """Escape a description for embedding in a double-quoted LookML/SQL string literal."""
    return s.replace('"', "'")


# The Conversational Analytics API binds at most this many Looker explores to one data agent, and
# queries exactly ONE of them per question — there is no cross-explore join. So an explore is a hard
# wall, and the number of them is a budget the gate has to enforce rather than a modelling taste.
# https://docs.cloud.google.com/gemini/data-agents/conversational-analytics-api/known-limitations
CA_MAX_EXPLORES = 5


# --------------------------------------------------------------------------- spec contract + validation
# *** EVERY MESSAGE THIS FILE PRINTS OR RAISES IS PINNED. DO NOT EDIT ONE ALONE. ***
# Y1, 2026-08-05, second adversarial audit finding A2-F2. This engine is [D], and in the
# strict-blind cold-start loop its console IS a channel to the [A] author — twice over:
#
#   1. `gate.txt` is the whole stdout+stderr of `generate_models.py --check-compile --check-data`,
#      and `assemble_author_input` relays that file to [A] VERBATIM as a bundle section. Every
#      validator error, every WARN/INFO line of the three checks, the coverage report's row labels
#      and `declared: bridges=… snapshots=…` are read by the author on the turn after they are
#      printed. (`declared:` is in 15 archived gate.txt files and 19 archived author bundles.)
#   2. `SpecError`'s message is relayed a SECOND time inside an amendment-A4 repair turn:
#      `run_spec_author._check_spec_shape` wraps it in one of four pinned templates and
#      `relay_audit._recompute_harness_output` re-derives it from the model's own archived
#      response — so BOTH halves of that audit agree with a poisoned validator. A2 appended one
#      sentence here ("HINT: your accounts table needs a dedup rule …") and reached the author with
#      the pin check clean and all 411 tests passing.
#
# So these strings are now a pinned family, `_PIN_ENGINE_FRAGMENTS` in
# `bi_modeling_playbook/scaffold/archive/relay_audit.py` — the AUDITOR, deliberately not here.
# `relay_audit.declared_engine_fragments()` DERIVES the [A]-facing set by following the text back
# from every `print` / `sys.exit` / `SpecError`, so a message added anywhere on that path is
# pinned automatically and shows up as UNPINNED until someone re-pins it. `run_spec_author.py`
# REFUSES TO RUN in between. Procedure: edit the message, run
# `relay_audit.py --print-pin engine`, paste, record the amendment in the gap-fix ledger.
#
# What you may say freely: anything that comes through an f-string hole — the spec's own table,
# column and measure names, counts, types. Those are the AUTHOR's artifact quoted back, they are
# not pinned, and the pin holds the template (`"{}: grain ({}) is NOT unique"`). What you may not
# say is a fix, a hypothesis, or a noun this dataset owns; the vocabulary check refuses those and
# sanctions only the contract vocabulary that `specs/SPEC_REFERENCE_BLIND.md` already gives [A].
class SpecError(ValueError):
    """Raised when a specs/*.yaml file violates the field contract (see specs/SPEC_REFERENCE.md)."""


# AUTHORITATIVE measure-type contract — the single source of truth shared by the validator below
# AND specs/SPEC_REFERENCE.md. Every measure ALSO requires the common keys `table`, `name`, `type`.
# Each `type` maps to exactly one branch in gen_lookml()/gen_graph(); adding a NEW type means adding
# a branch there, not just a spec line. Keep this dict in lockstep with those branches.
MEASURE_SPEC: dict[str, dict[str, list[str]]] = {
    "additive":          {"required": ["column"],                                    "optional": []},
    "rate":              {"required": ["column", "weight_by"],                        "optional": []},
    "semi_additive":     {"required": ["column", "period"],                           "optional": []},
    # inner SUM per period, outer `across` across periods (default avg). avg uses an in-explore
    # identity; max/min/median emit a per-period rollup view + explore (no nested-aggregate identity).
    "semi_additive_avg": {"required": ["column", "period"],                           "optional": ["across", "value_format"]},
    "ratio":             {"required": ["numerator", "denominator"],                   "optional": ["value_format"]},
    "filtered_sum":      {"required": ["column", "filter_field", "filter_value"],     "optional": []},
    "filtered_ratio":    {"required": ["numerator_table", "numerator_period_col", "parameter"],
                          # denominator is IMPLICIT — always the measure view's own `count` (= ALL
                          # parents), so it is NOT a key (unlike `ratio`, which takes an explicit one).
                          "optional": ["value_format", "materialize_graph_years"]},
    # M:N SPLIT. Default = EQUAL share (amount / weight, weight = owner_count). An optional
    # `weight_column` (a per-bridge-row factor whose values sum to 1 per entity — the Kimball
    # weighting-factor bridge) switches to a WEIGHTED share (amount * weight_column) instead.
    "allocated_sum":     {"required": ["amount_table", "amount_column", "weight"],    "optional": ["weight_column"]},
    # ACCUMULATING-SNAPSHOT milestone duration: DATE_DIFF(to, from) then aggregated (default average).
    # Pairs with a `layer1_structure.accumulating` table (which also auto-emits reached-stage counts).
    "milestone_lag":     {"required": ["from", "to"],                                 "optional": ["unit", "agg", "value_format"]},
    # PERIOD-OVER-PERIOD (YoY/MoM/QoQ). LookML uses the native `type: period_over_period` measure
    # (based_on an existing measure + a time dimension_group + period + kind). The graph has no native
    # PoP, so a per-period rollup NODE with LAG()/growth is materialized (see gen_graph). `column` is
    # the additive column the graph rollup sums; `base` is the LookML measure PoP is based_on.
    "period_over_period":{"required": ["base", "column", "period", "based_on_time"],  "optional": ["kind", "value_format"]},
    # WINDOW / analytic measures (running total, trailing average, share). LookML measures cannot hold
    # a window function, so each emits a per-period rollup `derived_table` view + its own explore (the
    # same escape the non-avg semi_additive_avg uses); the graph materializes the window column on a
    # rollup node. `order_by` is the ordering period; `partition_by` optionally resets/scopes the frame.
    "cumulative":        {"required": ["column", "order_by"],                         "optional": ["partition_by", "value_format"]},
    "moving_avg":        {"required": ["column", "order_by", "window"],              "optional": ["partition_by", "value_format"]},
    "percent_of_total":  {"required": ["column"],                                     "optional": ["partition_by", "value_format"]},
    # Generic NAMED aggregate — one type parameterised by `agg` (sum/average/min/max/count_distinct/
    # median/percentile/…), instead of one type per SQL function. For plain, hazard-free aggregates you
    # only curate when you want a GOVERNED named field; most min/max/count/median ride free as query
    # shapes over an exposed column. (For the AVG *trap* use `rate`/`semi_additive_avg`, not `average`.)
    # An optional `filter_field`/`filter_value` makes it a FILTERED aggregate of ANY agg — filtered
    # count_distinct / max / avg, not just sum. (`filtered_sum` is the named sum-only shortcut.)
    "aggregate":         {"required": ["agg", "column"],
                          "optional": ["value_format", "percentile", "filter_field", "filter_value"]},
    # Raw-expression escape hatch for anything the above can't express (stddev, variance, a custom
    # formula). `sql` is emitted verbatim into a LookML `type: number` measure.
    "number":            {"required": ["sql"],                                       "optional": ["value_format"]},
}
_MEASURE_COMMON = ["table", "name", "type"]
# LookML-native aggregate functions accepted by `type: aggregate`'s `agg` field.
_LKML_AGGS = {"sum", "average", "min", "max", "count_distinct", "median", "percentile",
              "sum_distinct", "average_distinct", "median_distinct", "percentile_distinct"}
# LookML native `type: period_over_period` comparison kinds.
_POP_KINDS = {"previous", "difference", "relative_change"}

# BigQuery data_type families, for the optional `--check-types` live cross-check (check_types()).
_BQ_NUMERIC = {"INT64", "INTEGER", "FLOAT64", "FLOAT", "NUMERIC", "BIGNUMERIC", "DECIMAL", "BIGDECIMAL"}
_BQ_TEMPORAL = {"DATE", "DATETIME", "TIMESTAMP", "TIME"}


def validate_spec(spec: dict) -> list[str]:
    """Validate the 2-layer spec (`layer1_structure` / `layer2_semantics`) against the field
    contract before any emission.

    Turns the two silent failure modes into loud ones: an unknown measure `type` (silently skipped
    by the emitter's if/elif chain) and a missing required key (a raw KeyError deep in emission).
    Collects ALL hard errors and raises SpecError once; returns a list of non-fatal warnings
    (unexpected/ignored keys). See specs/SPEC_REFERENCE.md.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ---- top-level identity ----
    for k in ("project", "dataset", "graph_name", "root"):
        if not spec.get(k):
            errors.append(f"top-level: missing required key `{k}`")
    looker = spec.get("looker") or {}
    for k in ("project", "model", "connection", "bq_dataset_constant"):
        if not looker.get(k):
            errors.append(f"looker: missing required key `{k}`")

    # ---- migration guardrail: the 3-layer spec keys are gone (2-layer reframe) ----
    # Fail LOUD on a half-migrated spec rather than silently dropping its columns / measures.
    for old, hint in (
        ("layer1_grains", "renamed to `layer1_structure`"),
        ("layer3_exposure", "removed — move `columns` into `layer1_structure.columns`, and "
                            "`unpivot` + `measures` into `layer2_semantics`"),
    ):
        if old in spec:
            errors.append(f"top-level `{old}`: 3-layer spec key ({hint}). "
                          "See specs/SPEC_REFERENCE.md 'Migrating from the 3-layer spec'.")

    # ---- LAYER 1: structure — grains, relationships & column exposure ----
    l1 = spec.get("layer1_structure") or {}
    tables = l1.get("tables") or {}                       # ENTITY nodes only
    bridges = l1.get("bridges") or {}
    snapshots = l1.get("snapshots") or {}
    known = set(tables) | set(bridges) | set(snapshots)  # every "is this a table?" check uses this
    if not tables:
        errors.append("layer1_structure.tables: missing or empty (need ≥1 entity table)")
    for t, ts in tables.items():
        if not isinstance(ts, dict) or "primary_key" not in ts:
            errors.append(f"layer1_structure.tables.{t}: missing `primary_key`")
        if not (isinstance(ts, dict) and ts.get("singular_label")):
            errors.append(f"layer1_structure.tables.{t}: missing `singular_label`")
    if spec.get("root") and spec["root"] not in tables:
        errors.append(f"root `{spec.get('root')}` is not an entity in layer1_structure.tables")
    rels = l1.get("relationships") or []
    # Role-playing collision detection: an ALIAS-LESS relationship emits `join: <child>`, so two
    # alias-less relationships to the SAME child collide. Count only the alias-less ones — a plain
    # 1:N to a child that is ALSO role-played (via other aliased relationships) is fine.
    aliasless_child_counts: dict[str, int] = {}
    for r in rels:
        if r.get("child") and not r.get("alias"):
            aliasless_child_counts[r["child"]] = aliasless_child_counts.get(r["child"], 0) + 1
    aliases_seen: set[str] = set()
    for i, r in enumerate(rels):
        for k in ("parent", "child", "fk", "label"):
            if k not in r:
                errors.append(f"layer1_structure.relationships[{i}]: missing `{k}`")
        for end in ("parent", "child"):
            if r.get(end) and r[end] not in known:
                errors.append(f"layer1_structure.relationships[{i}].{end} `{r[end]}` is not a known table")
        alias = r.get("alias")
        # ROLE-PLAYING / self-ref: a child targeted by >1 relationship, or a self-referencing
        # (parent == child) hierarchy edge, MUST carry a distinct `alias` (the many_to_one join name).
        needs_alias = aliasless_child_counts.get(r.get("child"), 0) > 1 or (r.get("parent") and r.get("parent") == r.get("child"))
        if needs_alias and not alias:
            errors.append(f"layer1_structure.relationships[{i}]: `{r.get('child')}` is role-played "
                          "(targeted by >1 relationship, or self-referencing) — add a distinct `alias`")
        if alias:
            if alias in known:
                errors.append(f"layer1_structure.relationships[{i}].alias `{alias}` collides with a table name")
            if alias in aliases_seen:
                errors.append(f"layer1_structure.relationships[{i}].alias `{alias}` is not unique")
            aliases_seen.add(alias)
        # AS-OF (SCD2 effective-dated) join: {fact_date, entity_key, valid_from, valid_to}. An as-of
        # relationship is a many_to_one range join, so it must also carry an `alias` (the versioned dim).
        ao = r.get("as_of")
        if ao is not None:
            if not isinstance(ao, dict):
                errors.append(f"layer1_structure.relationships[{i}].as_of: must be a mapping")
            else:
                for k in ("fact_date", "entity_key", "valid_from", "valid_to"):
                    if not ao.get(k):
                        errors.append(f"layer1_structure.relationships[{i}].as_of: missing `{k}`")
            if not alias:
                errors.append(f"layer1_structure.relationships[{i}]: an `as_of` join needs an `alias` (the versioned dim view)")
    # bridges: `between` = {endpoint_table: bridge_column}, EXACTLY 2 endpoints, both known entities.
    for b, info in bridges.items():
        btw = info.get("between") if isinstance(info, dict) else None
        if not isinstance(btw, dict):
            errors.append(f"layer1_structure.bridges.{b}: missing `between` map {{endpoint_table: column}}")
            continue
        if len(btw) != 2:
            errors.append(f"layer1_structure.bridges.{b}.between must have EXACTLY 2 endpoints (got {len(btw)})")
        for endp in btw:
            if endp not in tables:
                errors.append(f"layer1_structure.bridges.{b}.between: `{endp}` is not an entity in layer1_structure.tables")
    # snapshots: singular_label + entity_key + period; cross-check entity_key vs the incoming relationship fk.
    rel_fk_into = {r["child"]: r.get("fk") for r in (l1.get("relationships") or []) if r.get("child")}
    for s, info in snapshots.items():
        if not isinstance(info, dict):
            errors.append(f"layer1_structure.snapshots.{s}: must be a mapping")
            continue
        for k in ("singular_label", "entity_key", "period"):
            if not info.get(k):
                errors.append(f"layer1_structure.snapshots.{s}: missing `{k}`")
        ek = info.get("entity_key")
        if ek and rel_fk_into.get(s) and rel_fk_into[s] != ek:
            warnings.append(f"layer1_structure.snapshots.{s}.entity_key `{ek}` != the relationship fk "
                            f"`{rel_fk_into[s]}` into `{s}` (should they be the same key?)")

    # hierarchies: {name: {table, levels: [col, ...]}} — a fixed drill path. Emits LookML drill_fields;
    # the graph exposes every level as a property already, so it's LookML-only (a note on the graph).
    for h, info in (l1.get("hierarchies") or {}).items():
        if not isinstance(info, dict):
            errors.append(f"layer1_structure.hierarchies.{h}: must be a mapping")
            continue
        if not info.get("table") or info["table"] not in known:
            errors.append(f"layer1_structure.hierarchies.{h}.table `{info.get('table')}` is not a known table")
        if not isinstance(info.get("levels"), list) or len(info["levels"]) < 2:
            errors.append(f"layer1_structure.hierarchies.{h}: `levels` must be a list of ≥2 columns (drill path)")

    # accumulating: {entity_table: {milestones: [date_col, ...]}} — the 3rd Kimball fact type. The
    # table is a normal entity in `tables`; this only DECLARES its milestone date columns (for
    # reached-stage funnel counts + `milestone_lag` durations). Needs ≥2 milestones to be meaningful.
    for a, info in (l1.get("accumulating") or {}).items():
        if a not in tables:
            errors.append(f"layer1_structure.accumulating.{a}: must be an entity in layer1_structure.tables")
        if not isinstance(info, dict) or not isinstance(info.get("milestones"), list) or len(info["milestones"]) < 2:
            errors.append(f"layer1_structure.accumulating.{a}: `milestones` must be a list of ≥2 date columns")

    # ---- LAYER 2: dedup / m2n ----
    l2 = spec.get("layer2_semantics") or {}
    for t, dd in (l2.get("dedup") or {}).items():
        if t not in known:
            errors.append(f"layer2_semantics.dedup.{t}: not a known table")
        for k in ("partition_by", "order_by"):
            if not isinstance(dd, dict) or k not in dd:
                errors.append(f"layer2_semantics.dedup.{t}: missing `{k}`")
    for b, info in (l2.get("m2n") or {}).items():
        if b not in bridges:
            errors.append(f"layer2_semantics.m2n.{b}: not a declared bridge (add it under layer1_structure.bridges)")
        for k in ("entity", "allocation"):   # entity_key/other are DERIVED from the bridge's `between`
            if not isinstance(info, dict) or k not in info:
                errors.append(f"layer2_semantics.m2n.{b}: missing `{k}`")
        if isinstance(info, dict) and info.get("entity") and b in bridges:
            endpoints = list((bridges[b].get("between") or {}).keys())
            if info["entity"] not in endpoints:
                errors.append(f"layer2_semantics.m2n.{b}.entity `{info['entity']}` must be one of the "
                              f"bridge's `between` endpoints {endpoints}")

    # ---- LAYER 1: columns ({col: type | {type, hidden}} map) — dimension exposure ----
    _LKML_TYPES = {"string", "number", "yesno", "time", "timestamp", "date", "tier"}
    for t, cmap in (l1.get("columns") or {}).items():
        if t not in known:
            errors.append(f"layer1_structure.columns.{t}: not a known table")
        if not isinstance(cmap, dict):
            errors.append(f"layer1_structure.columns.{t}: must be a {{column: type}} map")
            continue
        for col, v in cmap.items():
            ty = v.get("type") if isinstance(v, dict) else v
            if ty not in _LKML_TYPES:
                warnings.append(f"layer1_structure.columns.{t}.{col}: unusual LookML type `{ty}` "
                                f"(known: {', '.join(sorted(_LKML_TYPES))})")
    if l1.get("column_types"):
        warnings.append("layer1_structure.column_types is removed — fold types into the `columns` map "
                        "(e.g. `col: number` or `col: {type: number, hidden: true}`); the block is ignored.")

    # ---- LAYER 2: unpivot (wide -> long) ----
    for uname, u in (l2.get("unpivot") or {}).items():
        if not isinstance(u, dict):
            errors.append(f"layer2_semantics.unpivot.{uname}: must be a mapping")
            continue
        for k in ("table", "name_field", "value_field", "columns"):
            if k not in u:
                errors.append(f"layer2_semantics.unpivot.{uname}: missing `{k}`")
        if u.get("table") and u["table"] not in known:
            errors.append(f"layer2_semantics.unpivot.{uname}.table `{u.get('table')}` is not a known table")
        if u.get("columns") and not isinstance(u["columns"], dict):
            errors.append(f"layer2_semantics.unpivot.{uname}.columns must be a map of source_column -> label")
        if uname in known:
            errors.append(f"layer2_semantics.unpivot.{uname}: name collides with a table name")

    # ---- top-level `defaults` (optional format knobs) ----
    _DEFAULTS_KEYS = {"ratio_format", "rate_format", "currency_format", "timeframes",
                      "native_period_over_period"}
    for k in (spec.get("defaults") or {}):
        if k not in _DEFAULTS_KEYS:
            warnings.append(f"defaults.{k}: unknown key (known: {', '.join(sorted(_DEFAULTS_KEYS))})")

    # ---- LAYER 2: measures (the single measures block) against MEASURE_SPEC ----
    # `(table, name)` must be unique across the whole list. Business-vs-rule-derivable is a
    # teaching distinction (a per-measure comment in the spec), NOT a block — every measure
    # lives here, in `layer2_semantics.measures`.
    seen: set[tuple] = set()
    for i, m in enumerate(l2.get("measures") or []):
        miss = [k for k in _MEASURE_COMMON if k not in m]
        if miss:
            errors.append(f"layer2_semantics.measures[{i}]: missing " + ", ".join(f"`{k}`" for k in miss))
            continue
        at = f"layer2_semantics.measures `{m['name']}`"
        if m["table"] not in known:
            errors.append(f"{at}: table `{m['table']}` is not a known table (entity/bridge/snapshot)")
        key = (m["table"], m["name"])
        if key in seen:
            errors.append(f"{at}: duplicate measure name on table `{m['table']}` (would emit two fields)")
        seen.add(key)
        mtype = m["type"]
        if mtype not in MEASURE_SPEC:
            errors.append(f"{at}: unknown type `{mtype}` (known: {', '.join(sorted(MEASURE_SPEC))}). "
                          "A new type needs a branch in gen_lookml/gen_graph, not just a spec line.")
            continue
        req, opt = MEASURE_SPEC[mtype]["required"], MEASURE_SPEC[mtype]["optional"]
        for k in req:
            if k not in m:
                errors.append(f"{at} (type {mtype}): missing required key `{k}`")
        # `description` is a UNIVERSAL optional on every measure type — a one-line hint the LookML
        # emitter puts on the measure (`description:`, consumed by the Looker CA agent for selection).
        allowed = set(_MEASURE_COMMON) | set(req) | set(opt) | {"description"}
        for k in m:
            if k not in allowed:
                warnings.append(f"{at} (type {mtype}): unexpected key `{k}` — ignored by the generator "
                                f"(allowed: {', '.join(sorted(allowed))})")
        if mtype == "aggregate":
            if m.get("agg") not in _LKML_AGGS:
                warnings.append(f"{at}: agg `{m.get('agg')}` is not a LookML-native aggregate "
                                f"(known: {', '.join(sorted(_LKML_AGGS))}); use type `number` for a custom expression")
            if ("filter_field" in m) != ("filter_value" in m):
                errors.append(f"{at}: `filter_field` and `filter_value` must be given together (or neither)")
        if mtype == "semi_additive_avg" and m.get("across", "avg") not in {"avg", "max", "min", "median"}:
            warnings.append(f"{at}: across `{m.get('across')}` not in avg/max/min/median")
        if mtype == "milestone_lag" and m.get("agg", "average") not in _LKML_AGGS:
            warnings.append(f"{at}: agg `{m.get('agg')}` is not a LookML-native aggregate "
                            f"(known: {', '.join(sorted(_LKML_AGGS))})")
        if mtype == "period_over_period" and m.get("kind", "relative_change") not in _POP_KINDS:
            warnings.append(f"{at}: kind `{m.get('kind')}` not in {', '.join(sorted(_POP_KINDS))}")
        if mtype == "moving_avg" and not (isinstance(m.get("window"), int) and m["window"] >= 1):
            errors.append(f"{at}: `window` must be a positive integer (trailing row count)")

    # ---- a `description` may not route the agent to a rollup artifact (2026-08-10) ----
    #
    # A measure `description` is emitted verbatim into the LookML and READ BY THE AGENT when it
    # picks a field. That makes it the one place in the spec where the author can write a claim
    # about the generator's own output — and the generator's output moves.
    #
    # It already happened. Run 009's author wrote, on `cumulative_payments`: "Lives in its OWN
    # explore cumulative_payments_window; select the month dimension plus this measure there".
    # True when written. Then `_window_needs_rollup` made that measure native and
    # `cumulative_payments_window` stopped existing — so the deployed model shipped a description
    # directing the agent to an explore that is not there. It scored 10/10 anyway (the agent
    # ignored the directions), which is precisely why nothing caught it.
    #
    # The rule is narrow and mechanical: `<name>_window` / `_pop` / `_rollup` is a naming grammar
    # only THIS generator mints, so any such token in a description is a claim about emission and
    # can be checked against what will actually be emitted for this very spec.
    #
    # WARNING, not error, and deliberately so. Archived specs are immutable evidence; making this
    # fatal would permanently block regenerating any frozen spec whose prose has since gone stale
    # — which is exactly the out-of-band comparison run this check was written during. A warning
    # reaches the author while it can still act, and is inert on a replay.
    _emitted_views, _emitted_explores = set(), {"the root explore"}
    for m in (l2.get("measures") or []):
        mt = m.get("type")
        if mt in ("cumulative", "moving_avg", "percent_of_total") and _window_needs_rollup(m):
            _emitted_views.add(f"{m.get('name')}_window")
        elif mt == "semi_additive_avg" and m.get("across", "avg") != "avg":
            _emitted_views.add(f"{m.get('name')}_rollup")
        elif mt == "period_over_period" and not _pop_is_native(spec):
            _emitted_views.add(f"{m.get('name')}_pop")
    _emitted_explores |= set(l2.get("unpivot") or {})
    _rollup_token = re.compile(r"\b([a-z][a-z0-9_]*_(?:window|pop|rollup))\b")
    for m in (l2.get("measures") or []):
        at = f"layer2_semantics.measures[{m.get('name', '?')}].description"
        for tok in dict.fromkeys(_rollup_token.findall(m.get("description") or "")):
            if tok not in _emitted_views and tok not in _emitted_explores:
                warnings.append(
                    f"{at}: names `{tok}`, which this spec does not emit. The description is "
                    f"copied into the LookML and read by the agent when it picks a field, so it "
                    f"would point at something that does not exist.")
            elif tok in _emitted_views and "explore" in (m.get("description") or "").lower():
                warnings.append(
                    f"{at}: calls `{tok}` an explore. It is a VIEW joined into the root explore, "
                    f"not an explore of its own — the agent does not have to go anywhere to reach "
                    f"it, and telling it to will not help.")

    if errors:
        raise SpecError(
            f"spec validation failed ({len(errors)} error(s)):\n  - " + "\n  - ".join(errors)
            + "\n\nSee bi_modeling_playbook/specs/SPEC_REFERENCE.md for the field contract.")
    return warnings


# --------------------------------------------------------------------------- graph DDL
def gen_graph(spec: dict, patterns: dict, with_semantics: bool) -> str:
    d = f"{spec['project']}.{spec['dataset']}"
    g = f"{d}.{spec['graph_name']}"
    schema = spec["schema"]
    tables = schema["tables"]
    dedup = (spec.get("semantics", {}).get("dedup", {}) if with_semantics else {})
    measures = (spec.get("semantics", {}).get("measures", []) if with_semantics else [])
    m2n = (spec.get("semantics", {}).get("m2n", {}) if with_semantics else {})
    unpivot = (spec.get("unpivot", {}) if with_semantics else {})
    cols = spec.get("columns", {})   # Layer-1 exposure — for graph column descriptions (structure-level)
    snapshots = patterns["snapshots"]

    # which enrichment columns to add to a node view (only with semantics)
    rate_measures = [m for m in measures if m["type"] == "rate"]
    semi_measures = [m for m in measures if m["type"] == "semi_additive"]
    ratio_measures = [m for m in measures if m["type"] == "ratio"]
    fratio_measures = [m for m in measures if m["type"] == "filtered_ratio"]
    avg_measures = [m for m in measures if m["type"] == "semi_additive_avg"]
    lag_measures = [m for m in measures if m["type"] == "milestone_lag"]
    pop_measures = [m for m in measures if m["type"] == "period_over_period"]
    window_measures = [m for m in measures if m["type"] in ("cumulative", "moving_avg", "percent_of_total")]
    accumulating = patterns.get("accumulating", {})   # Layer-1: milestone date columns per fact
    rels = schema["relationships"]

    def node_enrichment(t):
        """Derived columns + LEFT JOINs that enrich table t's node — computed INDEPENDENTLY of
        whether t is deduped (a table can need enrichment without a dedup rule). Returns
        (derived, joins); either may be empty."""
        derived, joins = [], []
        # (rate) weighted-avg ingredient: rate*weight product, precomputed per row.
        for m in rate_measures:
            if m["table"] == t:
                derived.append(f"ROUND(dd.{m['column']} * dd.{m['weight_by']}, 6) AS {m['column']}_x_{m['weight_by']}")
        # (M:N) owner_count / is_joint on the entity node. Far key = the OTHER table's real PK
        # (from the schema), NOT a name heuristic — so a PK like `person_id` on table `people` works.
        m2n_entity = next((info for b, info in m2n.items() if info["entity"] == t), None)
        if m2n_entity:
            bridge = next(b for b, info in m2n.items() if info["entity"] == t)
            ek = m2n_entity["entity_key"]                       # entity's fk column IN THE BRIDGE
            entity_pk = pk_cols(tables[t])[0]                   # the entity node's OWN pk column
            far_col = next(c for c in patterns["bridges"][bridge]["cols"] if c != ek)  # bridge's OTHER fk col
            # COUNT the bridge's far fk column (name-agnostic); join the subquery's ek to the node's own
            # pk. In the reference schema the bridge fk is named identically to the endpoint pk, so the
            # far column == the other table's pk and ek == entity_pk -> USING(ek) is byte-identical;
            # under name-masking the two differ and only this form is correct.
            join_on = f"USING ({ek})" if ek == entity_pk else f"ON oc.{ek} = dd.{entity_pk}"
            joins.append(
                f"LEFT JOIN (SELECT {ek}, COUNT(DISTINCT {far_col}) AS owner_count "
                f"FROM `{d}.{bridge}` GROUP BY {ek}) oc {join_on}")
            derived.append("COALESCE(oc.owner_count, 1) AS owner_count")
            derived.append("COALESCE(oc.owner_count, 1) >= 2 AS is_joint")
        # (zero-fill) a per-parent child COUNT for every `ratio` whose numerator is `<child>.count`
        # and whose <child> is a 1:N child of t. Generic over ANY child (not just "transactions");
        # the column is `<child.singular>_count`. Alias stays `tc` for the common single-child case.
        zf = [(m["numerator"][:-len(".count")],
               next((r for r in rels if r["parent"] == t and r["child"] == m["numerator"][:-len(".count")]), None))
              for m in ratio_measures if m["table"] == t and m.get("numerator", "").endswith(".count")]
        zf = [(child, rel) for child, rel in zf if rel]
        parent_pk = pk_cols(tables[t])[0]                      # the enriched node's OWN pk column
        for child, rel in zf:
            cnt = f"{table_singular(child, tables)}_count"
            alias = "tc" if len(zf) == 1 else f"tc_{child}"
            # join the child-count subquery (keyed by the child's fk) to the parent node's own pk. In the
            # reference schema the fk is named == the parent pk, so USING(fk) is byte-identical; under
            # name-masking they differ and the explicit ON is required.
            j = f"USING ({rel['fk']})" if rel["fk"] == parent_pk else f"ON {alias}.{rel['fk']} = dd.{parent_pk}"
            joins.append(
                f"LEFT JOIN (SELECT {rel['fk']}, COUNT(*) AS {cnt} "
                f"FROM `{d}.{child}` GROUP BY {rel['fk']}) {alias} {j}")
            derived.append(f"COALESCE({alias}.{cnt}, 0) AS {cnt}")
        # (child-side-filtered) one COUNT column PER anticipated period (VALUE-SPECIFIC — contrast
        # LookML's single value-INDEPENDENT parameter). Column = `<numerator.singular>_count_<year>`.
        for m in fratio_measures:
            rel = next((r for r in rels if r["parent"] == t and r["child"] == m["numerator_table"]), None)
            if not rel:
                continue
            per, ntab = m["numerator_period_col"], m["numerator_table"]
            parent_pk = pk_cols(tables[t])[0]                  # the enriched node's OWN pk column
            for y in m.get("materialize_graph_years", []):
                col = f"{table_singular(ntab, tables)}_count_{y}"
                j = f"USING ({rel['fk']})" if rel["fk"] == parent_pk else f"ON tc{y}.{rel['fk']} = dd.{parent_pk}"
                joins.append(
                    f"LEFT JOIN (SELECT {rel['fk']}, COUNT(*) AS {col} "
                    f"FROM `{d}.{ntab}` WHERE EXTRACT(YEAR FROM {per}) = {y} "
                    f"GROUP BY {rel['fk']}) tc{y} {j}")
                derived.append(f"COALESCE(tc{y}.{col}, 0) AS {col}")
        # (snapshot combo) if t is a periodic snapshot with a semi-additive measure AND it already
        # carries other enrichment, fold the is_latest_<period> flag in here so the combo gets ONE
        # node view. A PURE snapshot (no other enrichment) adds nothing here and keeps its simpler
        # dedicated view in the snapshot loop below — preserving existing output.
        if (derived or joins) and t in snapshots and any(m["table"] == t for m in semi_measures):
            per = snapshots[t]["period"]
            derived.append(f"dd.{per} = (SELECT MAX({per}) FROM `{d}.{t}`) AS is_latest_{per}")
        # compound (bitemporal) period-end: is_latest over a multi-column period tuple, driven by the
        # measure's period. Single-column stays on the path above / the snapshot loop below.
        for sm in semi_measures:
            if sm["table"] == t and len(_as_list(sm["period"])) > 1:
                flag, cond = _latest_cond(sm["period"], lambda p: f"dd.{p}", f"`{d}.{t}`")
                derived.append(f"{cond} AS {flag}")
                break
        # (accumulating snapshot) reached-stage flags + milestone-lag duration columns on the node, so
        # a funnel count is a single node scan (WHERE n.reached_<m>) and a lag is a precomputed prop.
        if t in accumulating:
            for ms in accumulating[t]["milestones"]:
                derived.append(f"dd.{ms} IS NOT NULL AS reached_{ms}")
        for m in lag_measures:
            if m["table"] == t:
                unit = m.get("unit", "DAY")
                derived.append(f"DATE_DIFF(dd.{m['to']}, dd.{m['from']}, {unit}) AS {m['name']}_{unit.lower()}s")
        return derived, joins

    lines: list[str] = []
    lines.append(f"-- AUTO-GENERATED from specs (legs: structure"
                 f"{' + semantics' if with_semantics else ''}). Graph auto-exposes ALL columns")
    lines.append("-- as properties, so plain-BI dimensions need NO column list here.\n")

    # 1) node views + edge views. A node view is emitted for any (non-bridge) table that is deduped
    #    OR carries enrichment — the two are decoupled (a table can need enrichment with no dedup).
    node_table = {t: t for t in tables}   # logical node -> backing table/view name
    for t in tables:
        if t in patterns["bridges"]:      # bridges are edges, not nodes
            continue
        derived, joins = (node_enrichment(t) if with_semantics else ([], []))
        if t not in dedup and not derived and not joins:
            continue
        node_table[t] = f"{t}_node"
        if t in dedup:
            dd = dedup[t]
            dd_cte = (f"WITH dd AS (\n  SELECT * FROM `{d}.{t}`\n  "
                      f"QUALIFY ROW_NUMBER() OVER ({_dedup_over(dd)}) = 1\n)")
        else:
            dd_cte = f"WITH dd AS (\n  SELECT * FROM `{d}.{t}`\n)"
        derived_sql = (",\n         " + ",\n         ".join(derived)) if derived else ""
        lines.append(f"CREATE OR REPLACE VIEW `{d}.{t}_node` AS")
        lines.append(dd_cte)
        lines.append(f"SELECT dd.*{derived_sql}\nFROM dd\n" + ("\n".join(joins) if joins else "") + ";")
        lines.append("")

    # snapshot node view (is_latest_<period>) if a semi-additive measure exists on it. (Skip if the
    # table already got an enriched node above — a snapshot table that also carries enrichment props
    # is an unsupported combo; split the table or fold the flag in by hand.)
    for t, info in snapshots.items():
        has_semi = any(m["table"] == t for m in semi_measures)
        if has_semi and not node_table[t].endswith("_node"):
            node_table[t] = f"{t}_node"
            lines.append(f"CREATE OR REPLACE VIEW `{d}.{t}_node` AS")
            lines.append(f"SELECT *, {info['period']} = (SELECT MAX({info['period']}) FROM `{d}.{t}`) AS is_latest_{info['period']}\nFROM `{d}.{t}`;")
            lines.append("")

    # monthly-rollup node view for semi_additive_avg (AVERAGE-over-time): materialize per-period
    # totals so the answer is AVG over one scan — the graph analog of LookML's monthly rollup.
    for m in avg_measures:
        t, col = m["table"], m["column"]
        per = ", ".join(_as_list(m["period"]))   # compound period -> GROUP BY p1, p2
        lines.append(f"-- semi-additive AVERAGE-over-time: materialized per-{per} rollup")
        lines.append(f"CREATE OR REPLACE VIEW `{d}.{t}_monthly` AS")
        lines.append(f"SELECT {per}, ROUND(SUM({col}), 2) AS {col}_total FROM `{d}.{t}` GROUP BY {per};")
        lines.append("")

    # period-over-period rollup nodes (graph has NO native PoP): per-period total + LAG + growth, so
    # the agent reads prev_total/growth off one node (the analog of LookML's native period_over_period).
    def _pop_bucket(col_ref: str, period: str) -> str:
        # Always a DATE (period start) — NOT EXTRACT(YEAR)=INT64 — so every PoP rollup node's `period`
        # property has ONE consistent type (BQ property graphs unify same-named properties by type).
        return f"DATE_TRUNC({col_ref}, {period.upper()})"   # year / quarter / month / week / …
    for m in pop_measures:
        t, col, bt, period = m["table"], m["column"], m["based_on_time"], m["period"]
        bucket = _pop_bucket(bt, period)
        # Grouping happens in the INNER query; LAG runs in the OUTER query over the plain `period`
        # alias — a window ORDER BY can't reference a computed grouping expression (EXTRACT/DATE_TRUNC)
        # in the same GROUP BY level (BigQuery: "neither grouped nor aggregated").
        lines.append(f"-- period-over-period ({period}): per-period total, prior period (LAG), growth")
        lines.append(f"CREATE OR REPLACE VIEW `{d}.{t}_{m['name']}` AS")
        lines.append(f"SELECT period, total,")
        lines.append(f"       LAG(total) OVER (ORDER BY period) AS prev_total,")
        lines.append(f"       ROUND(SAFE_DIVIDE(total - LAG(total) OVER (ORDER BY period), "
                     f"LAG(total) OVER (ORDER BY period)), 4) AS growth")
        lines.append(f"FROM (SELECT {bucket} AS period, ROUND(SUM({col}), 2) AS total "
                     f"FROM `{d}.{t}` GROUP BY period)")
        lines.append(f"ORDER BY period;")
        lines.append("")

    # window rollup nodes (running total / trailing moving-avg / %-of-total): materialize the analytic
    # column so a graph query is a single node scan (the agent can also compose the window func live).
    for m in window_measures:
        t, col, name = m["table"], m["column"], m["name"]
        pb = _as_list(m["partition_by"]) if m.get("partition_by") else []
        part = f"PARTITION BY {', '.join(pb)} " if pb else ""
        if m["type"] == "cumulative":
            ob = m["order_by"]; grp = ", ".join(pb + [ob])
            sel = (f"{grp}, ROUND(SUM({col}), 2) AS period_total, "
                   f"SUM(SUM({col})) OVER ({part}ORDER BY {ob} ROWS UNBOUNDED PRECEDING) AS running_total")
            grpby = grp
        elif m["type"] == "moving_avg":
            ob, n = m["order_by"], m["window"]; grp = ", ".join(pb + [ob])
            sel = (f"{grp}, ROUND(SUM({col}), 2) AS period_total, "
                   f"ROUND(AVG(SUM({col})) OVER ({part}ORDER BY {ob} ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW), 2) AS moving_avg")
            grpby = grp
        else:  # percent_of_total
            grp = ", ".join(pb)
            sel = (f"{grp}, ROUND(SUM({col}), 2) AS grp_total, "
                   f"ROUND(SAFE_DIVIDE(SUM({col}), SUM(SUM({col})) OVER ()), 4) AS pct_of_total")
            grpby = grp
        lines.append(f"-- window ({m['type']}): materialized rollup node")
        lines.append(f"CREATE OR REPLACE VIEW `{d}.{t}_{name}_window` AS")
        lines.append(f"SELECT {sel} FROM `{d}.{t}` GROUP BY {grpby};")
        lines.append("")

    # unpivot views (wide -> long): one row per (<source pk>, <name_field>). A standalone analytical
    # surface for "composition BY <name_field>" — sum <value_field> grouped by <name_field>. Kept its
    # own node (NOT edged to the source) so the source's other measures can't fan through the explosion.
    for uname, u in unpivot.items():
        src = u["table"]
        sel = list(dict.fromkeys(pk_cols(tables[src]) + u.get("keep", [])))
        inlist = ", ".join(f"{col} AS '{lbl}'" for col, lbl in u["columns"].items())
        lines.append(f"-- unpivot {uname}: {', '.join(u['columns'])} -> ({u['name_field']}, {u['value_field']})")
        lines.append(f"CREATE OR REPLACE VIEW `{d}.{uname}` AS")
        lines.append(f"SELECT {', '.join(sel)}, {u['name_field']}, {u['value_field']}")
        lines.append(f"FROM `{d}.{src}`")
        lines.append(f"UNPIVOT({u['value_field']} FOR {u['name_field']} IN ({inlist}));")
        lines.append("")

    # edge views (one per relationship). Plain 1:N / role-playing: SELECT the FK + the child's PK. An
    # AS-OF (SCD2) edge instead range-joins the fact to the dim VERSION valid at the fact's date, so the
    # edge lands on the correct versioned dim node (keyed by the dim's composite [entity, valid_from] PK).
    for rel in schema["relationships"]:
        p, c, fk = rel["parent"], rel["child"], rel["fk"]
        vname = f"{p}_{rel['label']}_{c}"
        ao = rel.get("as_of")
        if ao:
            fsel = ", ".join(f"f.{x}" for x in pk_cols(tables[c]))      # fact PK
            dsel = ", ".join(f"d.{x}" for x in pk_cols(tables[p]))      # dim version composite PK
            lines.append(f"-- AS-OF edge {c} -[{rel['label']}]-> {p} (SCD2 version valid at f.{ao['fact_date']})")
            lines.append(f"CREATE OR REPLACE VIEW `{d}.{vname}` AS")
            lines.append(f"SELECT {fsel}, {dsel}")
            lines.append(f"FROM `{d}.{node_table.get(c, c)}` f")
            lines.append(f"JOIN `{d}.{node_table.get(p, p)}` d ON f.{fk} = d.{ao['entity_key']}")
            lines.append(f"  AND f.{ao['fact_date']} >= d.{ao['valid_from']} AND f.{ao['fact_date']} < d.{ao['valid_to']};")
            lines.append("")
            continue
        cpk_list = pk_cols(tables[c])
        sel_cols = list(dict.fromkeys([fk] + cpk_list))
        lines.append(f"-- edge {p} -[{rel['label']}]-> {c}")
        lines.append(f"CREATE OR REPLACE VIEW `{d}.{vname}` AS")
        lines.append(f"SELECT {', '.join(sel_cols)} FROM `{d}.{node_table.get(c, c)}`;")
        lines.append("")

    # 2) property graph
    lines.append(f"CREATE OR REPLACE PROPERTY GRAPH `{g}`")
    lines.append("  NODE TABLES (")
    node_defs = []
    for t, s in tables.items():
        # bridges are modeled as edges, not nodes (unless promoted); skip bridge tables as nodes
        if t in patterns["bridges"]:
            continue
        pk = pk_cols(s)
        keyexpr = ", ".join(pk)
        label = node_label(t, tables)
        node_defs.append(f"    `{d}.{node_table[t]}` AS {label}\n      KEY ({keyexpr})")
    # standalone monthly-rollup nodes for semi_additive_avg (no edges — a materialized aggregate)
    for m in avg_measures:
        t, col = m["table"], m["column"]
        per = ", ".join(_as_list(m["period"]))   # compound period -> composite node KEY
        label = "Monthly" + "".join(w.capitalize() for w in col.split("_"))
        node_defs.append(f"    `{d}.{t}_monthly` AS {label}\n      KEY ({per})")
    # standalone unpivot nodes (no edges) — keyed by (<source pk>, <name_field>)
    for uname, u in unpivot.items():
        key = ", ".join(pk_cols(tables[u["table"]]) + [u["name_field"]])
        node_defs.append(f"    `{d}.{uname}` AS {_pascal(uname)}\n      KEY ({key})")
    # standalone period-over-period rollup nodes (keyed by period)
    for m in pop_measures:
        label = "Pop" + "".join(w.capitalize() for w in m["name"].split("_"))
        node_defs.append(f"    `{d}.{m['table']}_{m['name']}` AS {label}\n      KEY (period)")
    # standalone window rollup nodes (keyed by the grouping/order dims)
    for m in window_measures:
        pb = _as_list(m["partition_by"]) if m.get("partition_by") else []
        key = ", ".join(pb + ([m["order_by"]] if m["type"] in ("cumulative", "moving_avg") else []))
        label = "Win" + "".join(w.capitalize() for w in m["name"].split("_"))
        node_defs.append(f"    `{d}.{m['table']}_{m['name']}_window` AS {label}\n      KEY ({key})")
    lines.append(",\n".join(node_defs))
    lines.append("  )")
    edge_defs = []
    for rel in schema["relationships"]:
        p, c, fk = rel["parent"], rel["child"], rel["fk"]
        vname = f"{p}_{rel['label']}_{c}"
        plabel = node_label(p, tables)
        clabel = node_label(c, tables)
        elabel = "".join(w.capitalize() for w in rel["label"].split("_"))
        ckey = ", ".join(pk_cols(tables[c]))          # full (possibly composite) child PK
        if rel.get("as_of"):
            # AS-OF: the edge runs fact(c) -> dim VERSION(p, composite PK). SOURCE = fact PK, DEST = the
            # resolved dim version PK (both produced by the range-join edge view above).
            pkey = ", ".join(pk_cols(tables[p]))
            edge_defs.append(
                f"    `{d}.{vname}` AS {elabel}\n      KEY ({ckey}, {pkey})\n"
                f"      SOURCE KEY ({ckey}) REFERENCES {clabel} ({ckey})\n"
                f"      DESTINATION KEY ({pkey}) REFERENCES {plabel} ({pkey})")
            continue
        cpk = pk_cols(tables[c])[0]
        ppk = pk_cols(tables[p])[0]
        edge_defs.append(
            f"    `{d}.{vname}` AS {elabel}\n      KEY ({ckey})\n"
            f"      SOURCE KEY ({fk}) REFERENCES {plabel} ({ppk})\n"
            f"      DESTINATION KEY ({ckey}) REFERENCES {clabel} ({ckey})")
    # M:N bridge edges (both directions collapse to a HasOwner-style edge)
    for bridge, info in patterns["bridges"].items():
        a, b = info["between"]              # endpoint TABLE names (between-key order)
        acol, bcol = info["cols"]           # the bridge's OWN fk columns (aligned to between order)
        apk = pk_cols(tables[a])[0]         # endpoint PKs (referenced, not the bridge's key)
        bpk = pk_cols(tables[b])[0]
        alabel = node_label(a, tables)
        blabel = node_label(b, tables)
        # KEY / SOURCE / DESTINATION use the BRIDGE's own fk columns; only REFERENCES uses the endpoint
        # PKs. In the reference schema the bridge fk is named identically to the endpoint PK, so this is
        # byte-identical; under name-masking (global-unique columns) the two differ and only this form is
        # correct (else `KEY (c9,...)` names a column absent from the bridge).
        edge_defs.append(
            f"    `{d}.{bridge}` AS Has{blabel}\n      KEY ({acol}, {bcol})\n"
            f"      SOURCE KEY ({acol}) REFERENCES {alabel} ({apk})\n"
            f"      DESTINATION KEY ({bcol}) REFERENCES {blabel} ({bpk})")
    # A property graph with nodes and NO edges is valid BQ DDL; omit an empty EDGE TABLES clause
    # (an empty `EDGE TABLES ( )` is a syntax error — hit by an edgeless raw scaffold, e.g. a
    # name-masked dataset where no relationships are inferable until the author adds them).
    if edge_defs:
        lines.append("  EDGE TABLES (")
        lines.append(",\n".join(edge_defs))
        lines.append("  );")            # edges present: close EDGE TABLES + statement (original form)
    else:
        lines.append("  ;")             # nodes-only graph: just close the statement (no EDGE TABLES clause)

    # 3) field descriptions (spec `description:`) — captured for completeness / future consumption.
    # IMPORTANT: the CA graph agent does NOT read these today (a `propertyGraphReferences` datasource
    # selects graph properties by NAME, not by column description — verified live, see
    # v6x_traps_agent/RESULTS.md). We still emit them so that (a) column descriptions ARE applied as BQ
    # metadata on the node objects (real graph properties — future-proof if the CA API starts reading
    # them), and (b) measure intent is captured beside the ingredient columns.
    desc_alters = []
    for t in tables:
        for col, cv in (cols.get(t) or {}).items():
            cd = col_desc(cv)
            if not cd:
                continue
            obj = node_table[t]                              # base table, or the generated `_node` view
            kind = "VIEW" if obj.endswith("_node") else "TABLE"
            desc_alters.append(
                f'ALTER {kind} `{d}.{obj}` ALTER COLUMN {col} SET OPTIONS(description="{_esc_desc(cd)}");')
    if desc_alters:
        lines.append("\n-- ==== column descriptions -> BQ metadata on graph node properties ====")
        lines.append("-- (Not consumed by the CA graph agent today; applied for completeness / the future.)")
        lines.extend(desc_alters)

    measure_descs = [m for m in measures if m.get("description")]
    if measure_descs:
        lines.append("\n-- ==== measure descriptions (catalog) ====")
        lines.append("-- Measures are composed LIVE from the properties above; no single graph column")
        lines.append("-- represents one, so they're recorded here as the spec's intended-composition")
        lines.append("-- contract (verified by golden queries + eval, not by a materialized object).")
        for m in measure_descs:
            lines.append(f"--   {m['table']}.{m['name']} ({m['type']}): {m['description']}")

    if not with_semantics:
        lines.append("\n-- # TODO (needs semantics, not derivable from schema):")
        lines.append("--   * dedup: is any declared PK actually non-unique? (profile the data)")
        lines.append("--   * weighted measures: which rate is weighted by which measure?")
        lines.append("--   * semi-additive: which measures are point-in-time stocks (period-end vs avg)?")
        lines.append("--   * M:N allocation: count once / split / allocate?")
        lines.append("-- Until then the agent can sum any property, but sums over a non-unique PK,")
        lines.append("-- a rate, or across snapshot months will be WRONG.")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- LookML
def _window_needs_rollup(m: dict) -> bool:
    """Does this window measure still need a rollup `derived_table` (and therefore an explore)?

    NO for most of them, and the reason is worth stating because the generator got it wrong until
    2026-08-10. A LookML *measure* may not contain `SUM() OVER()` — true — but it does not follow
    that a window measure needs SQL: Looker has **native post-SQL measure types** that compute
    exactly these after the rows come back, with no window function and no derived table.

      * `cumulative`       -> `type: running_total`
      * `percent_of_total` -> `type: percent_of_total`
      * `moving_avg`       -> no native type exists; this one genuinely needs the rollup.

    The one native exception: `running_total` accumulates in the QUERY's sort order and has no
    partition concept, so a `cumulative` that declares `partition_by` cannot be expressed natively
    and keeps its rollup.

    Why it matters beyond tidiness: a rollup gets its own explore, and an explore is a hard wall —
    the Conversational Analytics API binds at most 5 and queries ONE per question, with no
    cross-explore joins. Run 009 measured the cost: 0 of 925 trials ever reached a `_window`
    explore, because the agent is bound to the root explore alone. A native measure lands on the
    root explore, where the agent is already looking.
    """
    t = m.get("type")
    if t == "moving_avg":
        return True
    if t == "cumulative":
        return bool(m.get("partition_by"))   # native running_total cannot partition
    return False


def _pop_is_native(spec: dict) -> bool:
    """Native `type: period_over_period` measure (rung 1), or the portable LAG rollup (rung 2)?

    Looker's native PoP measure needs the NEW LookML runtime plus dialect support, and the
    generator used to assume this instance class lacked both — so it always emitted the portable
    rollup, which cost an explore. That assumption was never tested. Measured on 2026-08-10
    against seaworkshop.cloud.looker.com (BigQuery dialect): a model carrying
    `new_lookml_runtime: yes` + a native PoP measure validates with a **zero error delta** against
    the identical model without it. So native is the DEFAULT.

    Native is strictly better than the rollup on every axis that matters here: no derived table,
    no join, and the measure lands on the owning view — i.e. on the ROOT explore, where the CA
    agent is already looking.

    Set `defaults.native_period_over_period: false` for an instance that rejects the new runtime.
    The fallback is still not exiled: the rollup is JOINED into the root explore (see the join
    emitter in `gen_lookml`), so either way PoP costs zero explores.
    """
    return bool(spec.get("defaults", {}).get("native_period_over_period", True))


def gen_lookml(spec: dict, patterns: dict, with_semantics: bool) -> dict:
    files: dict[str, str] = {}
    lk = spec["looker"]
    const = lk["bq_dataset_constant"]
    schema = spec["schema"]
    tables = schema["tables"]
    cols = spec.get("columns", {})   # Layer-1 dimension exposure — always emitted with structure
    sem = spec.get("semantics", {}) if with_semantics else {}
    dedup = sem.get("dedup", {})
    measures = sem.get("measures", [])
    m2n = sem.get("m2n", {})
    unpivot = spec.get("unpivot", {}) if with_semantics else {}
    snapshots = patterns["snapshots"]

    # format knobs (optional top-level `defaults:`; fall back to the historical hardcoded values)
    df = spec.get("defaults", {})
    ratio_fmt = df.get("ratio_format", "0.00")
    rate_fmt = df.get("rate_format", "0.0000")
    currency_fmt = df.get("currency_format", "usd")
    timeframes = df.get("timeframes", ["raw", "date", "month", "year"])

    def group_name(col: str) -> str:
        """dimension_group name = column minus a recognized time-type suffix (deterministic).

        LOAD-BEARING since 2026-08-10. It used to be safe to call this cosmetic, because measures
        only ever referenced the raw `${TABLE}.col` and never a timeframe field. Two things now
        reference the group by NAME and break silently if this list changes: `fact_ref` (the fact
        side of every rollup join -> `${view.<group>_raw}`) and native period-over-period
        (`based_on_time: <view>.<group>_<period>`). Neither failure shows up in the derived-table
        dry run — only a Looker validate/query catches them."""
        for suf in ("_datetime", "_date", "_time", "_ts", "_at"):
            if col.endswith(suf):
                return col[: -len(suf)]
        return col

    # period_over_period `based_on_time` must reference a TIMEFRAME field of a dimension_group (e.g.
    # payment_year), so that timeframe must be in the group's timeframe list. Collect the periods each
    # time column needs from the PoP measures and fold them in when emitting the dimension_group.
    pop_timeframes: dict[str, set] = {}
    for m in measures:
        if m.get("type") == "period_over_period":
            pop_timeframes.setdefault(m["based_on_time"], set()).add(m["period"])

    def time_group(col: str, dt: str, desc: str | None = None, name: str | None = None) -> str:
        """A LookML dimension_group for a `time` column (datatype date) or a `timestamp` column
        (datatype timestamp + a time-inclusive timeframe list). PoP period timeframes are folded in.

        `name` overrides the derived group name. Needed exactly once: an unpivot's value field sits
        beside its name field and usually shares a stem (`milestone_date` / `milestone`), so
        `group_name` would strip the suffix straight onto the name field's dimension."""
        if dt == "timestamp":
            tf = ["raw", "time", "date"] + [x for x in timeframes if x not in ("raw", "date")]
            datatype = "timestamp"
        else:
            tf, datatype = list(timeframes), "date"
        tf = list(dict.fromkeys(tf + sorted(pop_timeframes.get(col, set()))))   # add PoP period timeframes
        dsc = f'  description: "{_esc_desc(desc)}"' if desc else ""
        return (f"  dimension_group: {name or group_name(col)} {{ type: time  timeframes: [{', '.join(tf)}]  "
                f"datatype: {datatype}{dsc}  sql: ${{TABLE}}.{col} ;; }}")

    # NATIVE period_over_period needs the new LookML runtime declared at the PROJECT level. Emit it
    # only when a native PoP measure is actually emitted, so the runtime switch never rides along on
    # a model that does not need it (its blast radius is the whole project, not one measure).
    _native_pop = with_semantics and _pop_is_native(spec) and any(
        m.get("type") == "period_over_period" for m in measures)
    files["manifest.lkml"] = (
        f'project_name: "{lk["project"]}"\n\n'
        f'constant: bq_dataset {{ value: "{const}" }}\n'
        + ("\nnew_lookml_runtime: yes   # required by native `type: period_over_period`\n"
           if _native_pop else ""))

    # model + explore
    root = spec["root"]

    def fact_ref(t: str, col: str) -> str:
        """The LookML field reference for a BASE-TABLE column, as the view emitter actually named it.

        Needed because a rollup join has a fact side, and `${payments.payment_date}` is NOT a
        referenceable field when `payment_date` was emitted as a `dimension_group`. Two rewrites
        apply, and missing either produces LookML that passes the derived-table dry run and fails
        in Looker:

          1. NAME. `time_group` names the group `group_name(col)` — the column MINUS a recognized
             time suffix. `payment_date` -> group `payment`. So the field is not `payment_date_*`.
          2. TIMEFRAME. A `dimension_group` has no bare field; you must pick a timeframe. `_raw` is
             the untouched column (no timezone conversion, no DATE_TRUNC), which is the only one
             that equals the rollup's own GROUP BY key.

        Both decisions are READ OFF the emitter's own inputs rather than re-derived: the same
        `col_type` test that chooses `time_group(...)`, and the same `group_name`. A single-column
        PK is the one exception — the emitter emits it as a plain typed `dimension` (see the pk
        branch of the view loop) even when it is a date, so it needs no rewrite.

        NB: this makes `group_name`'s output LOAD-BEARING. It was documented as "non-load-bearing"
        while measures only ever referenced `${TABLE}.col`; a join is the first thing to depend on
        the group's *name*. Changing the suffix list now silently breaks joins — see group_name.
        """
        view = lk["model"] if t == root else t          # the root view is aliased by `from:`
        if t in tables and pk_cols(tables[t]) == [col]:
            return f"${{{view}.{col}}}"                 # single-col PK -> plain dimension, any type
        cv = cols.get(t, {}).get(col)
        if cv is not None and col_type(cv) in ("time", "timestamp"):
            return f"${{{view}.{group_name(col)}_raw}}"
        return f"${{{view}.{col}}}"

    ml = [f'connection: "{lk["connection"]}"', "", 'include: "/views/*.view.lkml"', "",
          f"explore: {lk['model']} {{", f"  from: {root}"]
    # joins. Three shapes:
    #   * plain 1:N (fan-OUT from a parent to its child) -> one_to_many, join name = child.
    #   * ROLE-PLAYING (`alias`): a fact joins UP to the same dim more than once (or a self-ref
    #     hierarchy) -> many_to_one, join name = alias, `from:` the dim. Direction is fact->dim.
    #   * AS-OF (`as_of`, SCD2 effective-dated): a many_to_one range join picking the dim VERSION
    #     valid at the fact's date (fact.date in [valid_from, valid_to)).
    for rel in schema["relationships"]:
        p, c, fk = rel["parent"], rel["child"], rel["fk"]
        alias, ao = rel.get("alias"), rel.get("as_of")
        if alias or ao:
            fact_left = lk["model"] if c == root else c   # the fact is the base we join FROM
            ml.append(f"  join: {alias} {{")
            ml.append(f"    from: {p}")
            ml.append(f"    relationship: many_to_one")
            if ao:
                ml.append(f"    # AS-OF: pick the {p} version valid at the fact's {ao['fact_date']}.")
                ml.append(f"    sql_on: ${{{fact_left}.{fk}}} = ${{{alias}.{ao['entity_key']}}}")
                ml.append(f"        AND ${{{fact_left}.{ao['fact_date']}}} >= ${{{alias}.{ao['valid_from']}}}")
                ml.append(f"        AND ${{{fact_left}.{ao['fact_date']}}} <  ${{{alias}.{ao['valid_to']}}} ;;")
            else:
                ppk = pk_cols(tables[p])[0]
                ml.append(f"    # ROLE-PLAYING: {c}.{fk} -> {p} (as {alias})")
                ml.append(f"    sql_on: ${{{fact_left}.{fk}}} = ${{{alias}.{ppk}}} ;;")
            ml.append("  }")
        else:
            ppk = pk_cols(tables[p])[0]
            left = lk["model"] if p == root else p
            ml.append(f"  join: {c} {{")
            ml.append(f"    relationship: one_to_many")
            ml.append(f"    sql_on: ${{{left}.{ppk}}} = ${{{c}.{fk}}} ;;")
            ml.append("  }")
    # join each detected M:N bridge to its entity (needed so cross-view M:N measures resolve)
    if with_semantics:
        for bridge, info in m2n.items():
            entity, ek = info["entity"], info["entity_key"]   # ek = the entity's fk col IN THE BRIDGE
            entity_pk = pk_cols(tables[entity])[0]            # the entity view's OWN pk col
            left = lk["model"] if entity == spec["root"] else entity
            # join the entity's pk to the bridge's entity-fk. Reference schema names them identically so
            # this is byte-identical; under name-masking they differ and `${entity.pk} = ${bridge.ek}`
            # is the only correct form (the entity view has no column named `ek`).
            ml.append(f"  join: {bridge} {{")
            ml.append(f"    relationship: one_to_many")
            ml.append(f"    sql_on: ${{{left}.{entity_pk}}} = ${{{bridge}.{ek}}} ;;")
            ml.append("  }")
        # M:N SPLIT allocation groups by the bridge's OWN column (e.g. ownership_role) — no extra
        # join. We deliberately do NOT join the owner entity to attribute by an owner *attribute*
        # (segment/region): that duplicates the dimension and the CA agent conflates it, breaking
        # plain-BI (measured; view_label/fields did not fix it — see RESULTS.md / PLAYBOOK §B).
    # ------------------------------------------------------------------ rollup JOINS (2026-08-10)
    # Every rollup derived_table that survives the native-measure pass is JOINED INTO THE ROOT
    # EXPLORE rather than given one of its own. An explore is the scarce resource — the CA API
    # binds at most CA_MAX_EXPLORES and queries exactly ONE per question with no cross-explore
    # joins — so an isolated explore is a wall, and a rollup has no reason to sit behind one: it
    # is keyed on columns that exist on its own fact table.
    #
    # Grain: one rollup row per period (per partition), so the join is `many_to_one` FROM the fact
    # and the fact cannot fan. The rollup's own measures are protected by symmetric aggregates —
    # every rollup view declares a primary key (`pk` in the window/semi-additive views, `period` in
    # the PoP view).
    #
    # Ordering matters: these are appended LAST, after the base relationship/bridge joins, so the
    # fact view a rollup keys off is always already in the explore.
    def _join_rollup(vname: str, fact: str, keys: list[str], why: str,
                     key_expr=None, rel: str = "many_to_one") -> None:
        """Join a generated view into the ROOT explore on `keys` of `fact`.

        `rel` is the grain of the joined side: `many_to_one` for a rollup (one row per period, so
        the fact cannot fan) and `one_to_many` for an unpivot (N rows per source row, so it does —
        correctly, and symmetric aggregates keep the source's own measures right).
        """
        conds = " AND ".join(
            f"{(key_expr(k) if key_expr else fact_ref(fact, k))} = ${{{vname}.{k}}}" for k in keys)
        grain = (f"One row per ({', '.join(keys)}); many_to_one so {fact} cannot fan."
                 if rel == "many_to_one" else
                 f"Keyed on {fact}'s PK ({', '.join(keys)}); one_to_many — {fact} DOES fan, and "
                 f"symmetric aggregates (both sides have a primary key) keep its measures correct.")
        ml.append(f"  join: {vname} {{")
        ml.append(f"    # JOIN — {why}. {grain}")
        ml.append(f"    relationship: {rel}")
        ml.append(f"    sql_on: {conds} ;;")
        ml.append("  }")

    if with_semantics:
        # non-avg semi-additive rollup (max/min/median of the per-period total)
        for m in measures:
            if m.get("type") == "semi_additive_avg" and m.get("across", "avg") != "avg":
                _join_rollup(f"{m['name']}_rollup", m["table"], _as_list(m["period"]),
                             f"semi_additive_avg across={m.get('across')}")
        # WINDOW rollups that no native measure type can express (moving_avg, partitioned cumulative)
        for m in measures:
            if m.get("type") in ("cumulative", "moving_avg", "percent_of_total") and _window_needs_rollup(m):
                pb = _as_list(m["partition_by"]) if m.get("partition_by") else []
                keys = pb + ([m["order_by"]] if m["type"] != "percent_of_total" else [])
                if keys:
                    _join_rollup(f"{m['name']}_window", m["table"], keys, f"window {m['type']}")
        # PERIOD-OVER-PERIOD, portable fallback only (native PoP is a plain measure — no view, no join).
        # Its key is DERIVED (`DATE_TRUNC(based_on_time, PERIOD)`), so unlike the others there is no
        # matching column on the fact. Do NOT join it to a dimension_group timeframe field and hope
        # Looker's rendering of `_month`/`_year` matches: write the same DATE_TRUNC into `sql_on`,
        # where it is plain BigQuery SQL and byte-identical to the derived table's own GROUP BY.
        if not _pop_is_native(spec):
            for m in measures:
                if m.get("type") == "period_over_period":
                    bt, per = m["based_on_time"], m["period"].upper()
                    _join_rollup(f"{m['name']}_pop", m["table"], ["period"],
                                 f"period_over_period {m['period']} (portable LAG rollup)",
                                 key_expr=lambda _k, t=m["table"], c=bt, p=per:
                                     f"DATE_TRUNC({fact_ref(t, c)}, {p})")
        # UNPIVOT joins too, as of 2026-08-10 — so the model is ONE explore.
        #
        # It was isolated because it row-MULTIPLIES its source and "joining it would fan every other
        # measure on that source". The fan is real; the conclusion was not. Looker's SYMMETRIC
        # AGGREGATES exist for exactly this, and apply here because both sides declare a primary key
        # (`<src>`'s own, and the unpivot's compound `pk`) — so `type: sum` / `type: count` on the
        # source stay correct under the multiplication.
        #
        # What actually made isolation look necessary was the DUPLICATE DIMENSION that `keep:`
        # produced, which is a measured hazard (PLAYBOOK §B) — and that is removed above by not
        # emitting `keep:` on the joined view, rather than by walling off the whole explore.
        #
        # The cost of NOT joining is what settles it: the CA agent queries ONE explore per question
        # with no cross-explore joins, so an isolated unpivot is a 4-field island with zero joins
        # next to a 138-field root. Binding it would hand the agent a routing decision whose wrong
        # branch has no data at all — an unbounded downside for a measured-zero upside (0 of 370
        # executed queries ever selected it). One explore removes the decision.
        for uname, u in unpivot.items():
            upk = pk_cols(tables[u["table"]])
            _join_rollup(uname, u["table"], upk,
                         f"unpivot of {u['table']} (wide -> long composition)", rel="one_to_many")
    ml.append("}")
    files[f"{lk['model']}.model.lkml"] = "\n".join(ml) + "\n"

    # views
    for t, s in tables.items():
        pk = pk_cols(s)
        v = [f"view: {t} {{"]
        # backing: dedup derived_table (semantics) else sql_table_name
        if t in dedup:
            dd = dedup[t]
            v.append("  # DEDUP (semantics): declared PK is not unique in the data (ETL double-load).")
            v.append("  derived_table: {")
            v.append(f"    sql: SELECT * FROM `@{{bq_dataset}}.{t}`")
            v.append(f"      QUALIFY ROW_NUMBER() OVER ({_dedup_over(dd)}) = 1 ;;")
            v.append("  }")
        else:
            v.append(f"  sql_table_name: `@{{bq_dataset}}.{t}` ;;")
        # primary key dimension (structure). Single-PK type comes from the declared columns map
        # (Layer-1 exposure); if the spec omits this column it is emitted UNTYPED.
        if len(pk) == 1:
            pk_v = cols.get(t, {}).get(pk[0])
            pk_dt = col_type(pk_v) if pk_v is not None else None
            pk_ty = f"  type: {pk_dt}" if pk_dt else ""
            pk_tz = "  convert_tz: no" if pk_dt == "date" else ""   # DATE PK (e.g. a calendar) — no tz wrap
            v.append(f"  dimension: {pk[0]} {{ primary_key: yes{pk_ty}{pk_tz}  sql: ${{TABLE}}.{pk[0]} ;; }}")
        else:
            key_sql = " || '-' || ".join(f"CAST(${{TABLE}}.{c} AS STRING)" for c in pk)
            v.append(f"  dimension: pk {{ primary_key: yes  hidden: yes  sql: {key_sql} ;; }}")
        # dimensions (Layer-1 columns): {col: type | {type, hidden}} — explicit type + explicit hide.
        if t in cols:
            for col, cv in cols[t].items():
                if col in pk and len(pk) == 1:
                    continue
                dt = col_type(cv)
                cd = col_desc(cv)
                if dt in ("time", "timestamp"):
                    v.append(time_group(col, dt, cd))
                else:
                    hide = "  hidden: yes" if col_hidden(cv) else ""
                    dsc = f'  description: "{_esc_desc(cd)}"' if cd else ""
                    # A scalar `type: date` dimension on a BigQuery DATE column must set
                    # `convert_tz: no` — Looker otherwise wraps it in DATE(col, query_tz), which is
                    # DATE(DATE, STRING) and has no matching BQ signature (only DATE(TIMESTAMP,[tz])).
                    # (A `datatype: date` dimension_group already avoids this; a scalar date needs it.)
                    tz = "  convert_tz: no" if dt == "date" else ""
                    v.append(f"  dimension: {col} {{ type: {dt}{hide}{tz}{dsc}  sql: ${{TABLE}}.{col} ;; }}")
        # count measure (structure — the zero-fill denominator + plain counts)
        v.append(f"  measure: count {{ type: count }}")
        # ACCUMULATING SNAPSHOT: a reached-stage yesno + funnel count per milestone (the row reached a
        # milestone iff its date is populated). Milestone-lag DURATIONS ride the `milestone_lag` measure.
        if t in patterns.get("accumulating", {}):
            for ms in patterns["accumulating"][t]["milestones"]:
                v.append(f"  dimension: reached_{ms} {{ hidden: yes  type: yesno  sql: ${{TABLE}}.{ms} IS NOT NULL ;; }}")
                v.append(f"  measure: {ms}_reached_count {{ type: count  filters: [reached_{ms}: \"yes\"] }}  # FUNNEL: rows that reached {ms}")
        # CHILD-SIDE-FILTERED ratio, numerator scaffolding (this view is a numerator table):
        # a VALUE-INDEPENDENT parameter + a conditional-aggregate count. The filter rides the
        # parameter (any period), so — unlike the graph — nothing per-value is materialized.
        for m in [mm for mm in measures if mm.get("type") == "filtered_ratio" and mm.get("numerator_table") == t]:
            par, per = m["parameter"], m["numerator_period_col"]
            dflt = (m.get("materialize_graph_years") or [None])[0]
            dflt_clause = f'  default_value: "{dflt}"' if dflt is not None else ""
            # Liquid ({% parameter %}) is rendered in a `sql:`, NOT in a number-filter value, so the
            # condition lives in a yesno dimension; the measure filters on that yesno. A default_value
            # lets the model compile/validate before the agent supplies a year. The parameter name must
            # not collide with a dimension_group timeframe field (e.g. `txn` -> `txn_year`).
            v.append(f"  parameter: {par} {{ type: number{dflt_clause}  # VALUE-INDEPENDENT: agent supplies the year")
            v.append(f"    description: \"Year to filter the numerator by; the ratio's denominator stays ALL parents.\" }}")
            v.append(f"  dimension: is_{par} {{ hidden: yes  type: yesno  sql: EXTRACT(YEAR FROM ${{TABLE}}.{per}) = {{% parameter {par} %}} ;; }}")
            v.append(f"  measure: count_in_selected_year {{ type: count  filters: [is_{par}: \"yes\"] }}  # conditional aggregate — keeps the denominator intact")
        # measures (LEG 3 semantics)
        for m in [mm for mm in measures if mm["table"] == t]:
            if m["type"] == "additive":
                v.append(f"  measure: {m['name']} {{ type: sum  sql: ${{{t}.{m['column']}}} ;; }}")
            elif m["type"] == "rate":
                num = f"{m['column']}_x_{m['weight_by']}"
                v.append(f"  dimension: {num} {{ hidden: yes  type: number  sql: ${{{m['column']}}} * ${{{m['weight_by']}}} ;; }}")
                v.append(f"  measure: sum_{num} {{ hidden: yes  type: sum  sql: ${{{num}}} ;; }}")
                v.append(f"  measure: sum_{m['weight_by']} {{ hidden: yes  type: sum  sql: ${{{m['weight_by']}}} ;; }}")
                v.append(f"  measure: {m['name']} {{ type: number  value_format: \"{rate_fmt}\"  sql: ${{sum_{num}}} / NULLIF(${{sum_{m['weight_by']}}}, 0) ;; }}  # WEIGHTED avg")
            elif m["type"] == "semi_additive":
                # period-end: latest snapshot. `period` may be a list (compound / bitemporal) -> the
                # latest period TUPLE (lexicographic), the direct dual-axis period-end.
                flag, cond = _latest_cond(m["period"], lambda p: f"${{TABLE}}.{p}", f"`@{{bq_dataset}}.{t}`")
                v.append(f"  dimension: {flag} {{ type: yesno  sql: {cond} ;; }}")
                v.append(f"  measure: {m['name']} {{ type: sum  sql: ${{{m['column']}}} ;;  filters: [{flag}: \"yes\"] }}  # SEMI-ADDITIVE (period-end)")
            elif m["type"] == "ratio":
                # cross-view derived measure: numerator/denominator are <view>.<measure> refs.
                fmt = m.get("value_format", ratio_fmt)
                v.append(f"  measure: {m['name']} {{ type: number  value_format: \"{fmt}\"  sql: ${{{m['numerator']}}} / NULLIF(${{{m['denominator']}}}, 0) ;; }}  # DERIVED ratio (cross-view)")
            elif m["type"] == "filtered_sum":
                # cross-view filtered sum: filter_field may live on another (joined) view.
                v.append(f"  measure: {m['name']} {{ type: sum  sql: ${{{m['column']}}} ;;  filters: [{m['filter_field']}: \"{m['filter_value']}\"] }}  # DERIVED filtered sum (cross-view)")
            elif m["type"] == "filtered_ratio":
                # CHILD-SIDE-FILTERED zero-fill ratio: numerator is the numerator view's
                # parameter-driven conditional count; denominator is THIS view's count (ALL
                # parents). Filtering the child in a WHERE would drop zero-in-window parents.
                fmt = m.get("value_format", ratio_fmt)
                v.append(f"  measure: {m['name']} {{ type: number  value_format: \"{fmt}\"  sql: ${{{m['numerator_table']}.count_in_selected_year}} / NULLIF(${{count}}, 0) ;; }}  # CHILD-SIDE-FILTERED ratio (param {m['numerator_table']}.{m['parameter']}); denominator = ALL parents")
            elif m["type"] == "allocated_sum":
                # M:N SPLIT allocation: sum each owner's equal share (amount / weight). Group by a
                # non-duplicating BRIDGE column (e.g. ownership_role) — NOT a re-joined entity
                # attribute, which duplicates a dimension and the CA agent conflates it (measured;
                # see RESULTS.md). Grand total is conserved. (Shipped v6x precomputes the share as a
                # derived_table column so the sum is robust to symmetric-aggregate keying; the
                # cross-view form here is the illustrative POC.)
                amt = f"{m['amount_table']}.{m['amount_column']}"
                if m.get("weight_column"):
                    # WEIGHTED split (Kimball weighting-factor bridge): a per-row factor summing to 1
                    # per entity -> share = amount * weight_column (NOT equal 1/degree).
                    share = f"${{{amt}}} * ${{{m['weight_column']}}}"
                    tag = f"WEIGHTED (× {m['weight_column']})"
                else:
                    share = f"${{{amt}}} / NULLIF(${{{m['weight']}}}, 0)"       # EQUAL 1/degree share
                    tag = "EQUAL (÷ owner_count)"
                v.append(f"  measure: {m['name']} {{ type: sum  value_format_name: {currency_fmt}  sql: {share} ;; }}  # M:N SPLIT allocation, {tag} (group by a bridge column e.g. ownership_role; total conserved)")
            elif m["type"] == "semi_additive_avg":
                # SEMI-ADDITIVE across-time: inner SUM per period, outer `across` across periods.
                # avg has an in-explore identity (SUM(all)/COUNT(DISTINCT period), no derived table);
                # max/min/median CAN'T nest aggregates in one measure -> a rollup view+explore below.
                if m.get("across", "avg") == "avg":
                    pers = _as_list(m["period"])
                    # Reference the RAW period column(s) (${TABLE}.col), NOT a dimension_group timeframe
                    # field — so measure correctness never depends on the period column's name/type.
                    # compound period -> COUNT(DISTINCT CONCAT(p1,'|',p2)); single -> COUNT(DISTINCT col)
                    distinct = (f"COUNT(DISTINCT ${{TABLE}}.{pers[0]})" if len(pers) == 1 else
                                "COUNT(DISTINCT CONCAT(" + ", '|', ".join(f"CAST(${{TABLE}}.{p} AS STRING)" for p in pers) + "))")
                    v.append(f"  measure: {m['name']} {{ type: number  value_format_name: {currency_fmt}  sql: SUM(${{{m['column']}}}) / NULLIF({distinct}, 0) ;; }}  # SEMI-ADDITIVE average-over-time (avg of period totals)")
            elif m["type"] == "aggregate":
                # generic NAMED aggregate — parameterised by `agg` (one type covers the whole family),
                # optionally FILTERED (any agg, not just sum — filtered count_distinct/max/avg/…).
                fmt = f'  value_format: "{m["value_format"]}"' if m.get("value_format") else ""
                pct = f'  percentile: {m.get("percentile", 50)}' if m["agg"].startswith("percentile") else ""
                flt = f'  filters: [{m["filter_field"]}: "{m.get("filter_value", "")}"]' if m.get("filter_field") else ""
                tag = f" ({m['agg']}{', filtered' if flt else ''})"
                v.append(f"  measure: {m['name']} {{ type: {m['agg']}{pct}  sql: ${{{t}.{m['column']}}} ;;{flt}{fmt} }}  # AGGREGATE{tag}")
            elif m["type"] == "number":
                # raw-expression escape hatch (stddev/variance/custom) — sql emitted verbatim.
                fmt = f'  value_format: "{m["value_format"]}"' if m.get("value_format") else ""
                v.append(f"  measure: {m['name']} {{ type: number  sql: {m['sql']} ;;{fmt} }}  # CUSTOM expression")
            elif m["type"] in ("cumulative", "percent_of_total") and not _window_needs_rollup(m):
                # NATIVE post-SQL window (2026-08-10). Looker computes these AFTER the rows return,
                # so they are ordinary fields on THIS view — on the root explore, reachable by the
                # agent — instead of a rollup derived_table exiled to its own explore.
                # Both native types require `sql:` to reference another numeric measure, hence the
                # hidden base sum; it is `hidden` so it does not enlarge the agent's field surface.
                fmt = f'  value_format: "{m["value_format"]}"' if m.get("value_format") else ""
                base = f"{m['name']}__base"
                v.append(f"  measure: {base} {{ hidden: yes  type: sum  sql: ${{{t}.{m['column']}}} ;; }}")
                if m["type"] == "cumulative":
                    # SORT-ORDER DEPENDENT: `running_total` accumulates down the result as sorted,
                    # so a DESCENDING sort yields a reverse cumulative that looks plausible and is
                    # wrong. The order_by column is named in the description so whoever (or
                    # whatever) builds the query is told which way to sort.
                    v.append(f"  measure: {m['name']} {{ type: running_total  sql: ${{{base}}} ;;{fmt} }}"
                             f"  # NATIVE running total — accumulates in the query's sort order; sort by {m['order_by']} ASCENDING")
                else:
                    v.append(f"  measure: {m['name']} {{ type: percent_of_total  sql: ${{{base}}} ;;{fmt} }}"
                             f"  # NATIVE percent of total — share of the column total; nulls out past the row limit and cannot be filtered on")
            elif m["type"] == "milestone_lag":
                # ACCUMULATING-SNAPSHOT duration: a per-row DATE_DIFF dimension + an aggregate over it.
                unit, agg = m.get("unit", "DAY"), m.get("agg", "average")
                fmt = f'  value_format: "{m["value_format"]}"' if m.get("value_format") else ""
                v.append(f"  dimension: {m['name']}_{unit.lower()}s {{ hidden: yes  type: number  sql: DATE_DIFF(${{TABLE}}.{m['to']}, ${{TABLE}}.{m['from']}, {unit}) ;; }}")
                v.append(f"  measure: {m['name']} {{ type: {agg}  sql: ${{{m['name']}_{unit.lower()}s}} ;;{fmt} }}  # MILESTONE LAG {m['from']}->{m['to']} ({agg} {unit.lower()}s)")
            elif m["type"] == "period_over_period" and _pop_is_native(spec):
                # NATIVE period-over-period (2026-08-10). Looker computes this after the rows
                # return, so — like running_total / percent_of_total above — it is an ordinary
                # field on THIS view, i.e. on the ROOT explore where the agent already is. No
                # derived table, no join, no explore.
                #
                # This replaces a PORTABILITY assumption that was never measured: the generator
                # emitted the LAG rollup because native PoP "requires the new LookML runtime AND
                # dialect support that older instances lack". True in general, false here —
                # validated against the live instance with a zero error delta (see _pop_is_native).
                # `defaults.native_period_over_period: false` restores the rollup.
                #
                # `based_on_time` must name a TIMEFRAME FIELD of a dimension_group, not the column:
                # group `group_name(col)` + the period. `pop_timeframes` (above) has already folded
                # that period into the group's `timeframes` list so the field exists.
                fmt = f'  value_format: "{m["value_format"]}"' if m.get("value_format") else ""
                _bt = f"{t}.{group_name(m['based_on_time'])}_{m['period']}"
                v.append(f"  measure: {m['name']} {{ type: period_over_period  based_on: {t}.{m['base']}"
                         f"  based_on_time: {_bt}  period: {m['period']}"
                         f"  kind: {m.get('kind', 'relative_change')}{fmt} }}"
                         f"  # NATIVE period-over-period ({m['period']}, {m.get('kind', 'relative_change')}) vs {m['base']}")
            # PERIOD-OVER-PERIOD, portable fallback: NOT emitted inline. When
            # `defaults.native_period_over_period: false` (an instance without the new LookML
            # runtime), a per-period LAG rollup derived_table is emitted below instead — and, since
            # 2026-08-10, JOINED into the root explore rather than given one of its own. The graph
            # side is a LAG rollup node either way.
        # M:N joint count on the bridge view
        if t in patterns["bridges"] and t in m2n:
            info = m2n[t]
            v.append(f"  # M:N ALLOCATION (semantics): {info['allocation']} — count each {info['entity_key']} once.")
            v.append(f"  dimension: owner_count {{ hidden: yes  type: number  sql: (SELECT COUNT(*) FROM `@{{bq_dataset}}.{t}` b WHERE b.{info['entity_key']} = ${{TABLE}}.{info['entity_key']}) ;; }}")
            v.append(f"  dimension: is_joint {{ type: yesno  sql: ${{owner_count}} >= 2 ;; }}")
            v.append(f"  measure: joint_{table_singular(info['entity'], tables)}_count {{ type: count_distinct  sql: ${{TABLE}}.{info['entity_key']} ;;  filters: [is_joint: \"yes\"] }}")
        # optional per-measure `description:` — a one-line hint the Looker CA agent reads when picking a
        # field. Injected after dispatch so it rides EVERY measure type without touching each branch;
        # only the named spec measures (not hidden helper measures) get one.
        mdesc = {mm["name"]: mm["description"] for mm in measures
                 if mm["table"] == t and mm.get("description")}
        if mdesc:
            for i, ln in enumerate(v):
                s = ln.lstrip()
                if s.startswith("measure: ") and s.split(None, 2)[1] in mdesc:
                    esc = _esc_desc(mdesc[s.split(None, 2)[1]])
                    v[i] = ln.replace("{", f'{{ description: "{esc}" ', 1)
        # HIERARCHY drill paths (Layer-1 exposure): each level dimension drills into the deeper levels.
        # Graph needs none of this (every level is already a property to GROUP BY) — LookML-only.
        hdrills: dict[str, list[str]] = {}
        for h, info in patterns.get("hierarchies", {}).items():
            if info.get("table") == t:
                lv = info["levels"]
                for idx, col in enumerate(lv[:-1]):
                    hdrills.setdefault(col, []).extend(lv[idx + 1:])
        if hdrills:
            for i, ln in enumerate(v):
                s = ln.lstrip()
                if s.startswith("dimension: ") and s.split(None, 2)[1] in hdrills:
                    dn = s.split(None, 2)[1]
                    v[i] = ln.replace("{", f"{{ drill_fields: [{', '.join(hdrills[dn])}]", 1)
        v.append("}")
        files[f"views/{t}.view.lkml"] = "\n".join(v) + "\n"

    # unpivot views (wide -> long): fee_type-style dimension + a single summed value measure. Its own
    # view/explore; group by <name_field> for the "composition" the wide columns couldn't express.
    for uname, u in unpivot.items():
        src, nf, vf = u["table"], u["name_field"], u["value_field"]
        keep = u.get("keep", [])
        srcpk = pk_cols(tables[src])
        # SELF-CONTAINED derived_table, NOT `sql_table_name` (2026-08-10). This view used to read a
        # BigQuery view of the same name — one that only `gen_graph` emits, as
        # `CREATE OR REPLACE VIEW … UNPIVOT(…)` inside graph.sql. Both halves landed in the same
        # commit (3a74c2a, 2026-07-13) on the implicit contract that both stacks share one dataset,
        # so the graph's DDL was a shared prerequisite. `per_stack_datasets` (50815fe, 2026-08-04,
        # default True) severed that: graph.sql now runs against `…g_demo` and Looker reads
        # `…l_demo`, which never gets the view. Every Looker run since has shipped a view over a
        # table that does not exist — invisible because `--check-compile` only dry-runs
        # `derived_table` SQL, Looker's validate does not check table existence, and the agent is
        # bound to the root explore so nothing ever queried it.
        #
        # Inlining the same UNPIVOT removes the cross-stack prerequisite entirely AND puts the SQL
        # inside the dry-run that already exists. A LookML model should not depend on an artifact
        # the graph emitter happens to create.
        # `keep:` is NOT carried into the LookML view (2026-08-10). It exists so an ISOLATED unpivot
        # explore has something to slice by — but this view is JOINED into the root explore now, and
        # every kept column is by construction already on the source view sitting across that join.
        # Emitting it would duplicate a dimension, which is the shape PLAYBOOK §B measured as
        # actively harmful: the CA agent conflates the two copies and asks which field to use
        # instead of answering (`bi_filter` 10/10 -> 3/10 -> 0/10; `view_label`/`fields:` did not
        # fix it). `keep:` is still honoured by gen_graph, whose unpivot NODE is standalone and has
        # no join to reach the source through — so the spec field keeps its meaning, on the one
        # stack where it has one.
        sel = ", ".join(dict.fromkeys(srcpk))
        inlist = ", ".join(f"{c} AS '{lbl}'" for c, lbl in u["columns"].items())
        # value-field type decides which aggregates even make sense (see the measure below)
        _first = next(iter(u["columns"]), None)
        _vcv = cols.get(src, {}).get(_first) if _first else None
        vdt = col_type(_vcv) if _vcv is not None else None
        uv = [f"view: {uname} {{",
              f"  # UNPIVOT of {', '.join(u['columns'])} -> a groupable `{nf}` dimension + `{vf}`.",
              "  derived_table: { sql:",
              f"    SELECT {sel}, {nf}, {vf} FROM `@{{bq_dataset}}.{src}` "
              f"UNPIVOT({vf} FOR {nf} IN ({inlist})) ;;",
              "  }"]
        keysql = " || '-' || ".join(f"CAST(${{TABLE}}.{c} AS STRING)" for c in srcpk + [nf])
        uv.append(f"  dimension: pk {{ primary_key: yes  hidden: yes  sql: {keysql} ;; }}")
        # the source PK, HIDDEN — not a field for the agent, but the join key the root explore needs.
        # (`pk` above is the unpivot's own compound grain and cannot serve: it includes `nf`.)
        for c in srcpk:
            uv.append(f"  dimension: {c} {{ hidden: yes  sql: ${{TABLE}}.{c} ;; }}")
        uv.append(f"  dimension: {nf} {{ type: string  sql: ${{TABLE}}.{nf} ;; }}")
        # THE VALUE FIELD, typed honestly. A wide-to-long unpivot of DATE columns (an accumulating
        # snapshot's milestones) has no summable value: `SUM(<date>)` is not even valid BigQuery.
        # The generator emitted exactly that, unconditionally, and nothing caught it because the
        # backing table was missing anyway. A date/timestamp value becomes a groupable
        # `dimension_group` — which is what makes "how many hit each milestone per month" askable.
        #
        # The group is named `vf` VERBATIM rather than through `group_name`, which would strip the
        # suffix and collide with the name_field: `milestone_date` -> `milestone`, and
        # `dimension: milestone` already exists two lines up.
        if vdt in ("time", "timestamp"):
            uv.append(time_group(vf, vdt, name=vf))
        else:
            uv.append(f"  measure: total_{vf} {{ type: sum  sql: ${{TABLE}}.{vf} ;; }}  # group by {nf} for the composition")
        # COUNT — the one aggregate meaningful for EVERY unpivot, and the only one meaningful for a
        # date-valued one ("how many rows reached each milestone"). Base views have had this since
        # forever; unpivot views are emitted in this separate loop and never got it, so a date
        # unpivot previously exposed no usable aggregate at all.
        #
        # Named `<name_field>_count`, NOT the bare `count` every base view uses. Once this view is
        # joined into the root explore, a bare `count` would sit beside its own source's `count`
        # while counting a DIFFERENT grain of the same entity — 2154 unpivoted milestone rows vs
        # 800 loan applications. A golden control question asks "how many loan applications do we
        # have?", and picking the wrong one returns a confident 2154. That is a worse failure than
        # the duplicate-dimension one: it is a wrong number, not a request to disambiguate. The
        # name says which grain it counts.
        uv.append(f"  measure: {nf}_count {{ type: count }}  # rows per {nf} — the composition count "
                  f"(grain: one row per {src} x {nf}, NOT per {src})")
        uv.append("}")
        files[f"views/{uname}.view.lkml"] = "\n".join(uv) + "\n"

    # non-avg cross-time semi-additive rollups (MAX/MIN/MEDIAN of the per-period total): a per-period
    # derived-table view + its own explore. (avg uses the in-explore identity above; the graph's
    # _monthly rollup node already covers every outer aggregate — this is the LookML counterpart.)
    for m in measures:
        if m.get("type") != "semi_additive_avg" or m.get("across", "avg") == "avg":
            continue
        t, col, name, across = m["table"], m["column"], m["name"], m["across"]
        pers = _as_list(m["period"])
        grp = ", ".join(pers)   # compound period -> GROUP BY p1, p2
        fmt = f'  value_format: "{m["value_format"]}"' if m.get("value_format") else "  value_format_name: usd"
        vn = f"{name}_rollup"
        rv = [f"view: {vn} {{",
              f"  # SEMI-ADDITIVE {across}-over-time: roll up to per-({grp}) totals, then {across} across periods.",
              "  derived_table: { sql:",
              f"    SELECT {grp}, SUM({col}) AS period_total FROM `@{{bq_dataset}}.{t}` GROUP BY {grp} ;;",
              "  }"]
        rv += [f"  dimension: {p} {{ sql: ${{TABLE}}.{p} ;; }}" for p in pers]
        rv += [f"  measure: {name} {{ type: {across}  sql: ${{TABLE}}.period_total ;;{fmt} }}", "}"]
        files[f"views/{vn}.view.lkml"] = "\n".join(rv) + "\n"

    # WINDOW measures (running total / trailing moving-avg / %-of-total). A LookML measure can't hold a
    # window function, so each rolls up to a per-period derived_table + its own explore (declared above).
    # The analytic value is a groupable DIMENSION (the per-row curve); a companion measure surfaces the
    # headline (final cumulative / avg / share-sum). This is the honest LookML "table-calc" cost.
    for m in measures:
        if m.get("type") not in ("cumulative", "moving_avg", "percent_of_total"):
            continue
        if not _window_needs_rollup(m):
            continue      # NATIVE post-SQL measure on the owning view instead — see _window_needs_rollup
        t, col, name = m["table"], m["column"], m["name"]
        pb = _as_list(m["partition_by"]) if m.get("partition_by") else []
        fmt = f'  value_format: "{m["value_format"]}"' if m.get("value_format") else ""
        vn = f"{name}_window"
        if m["type"] == "cumulative":
            ob = m["order_by"]; dims = pb + [ob]; grp = ", ".join(dims)
            part = f"PARTITION BY {', '.join(pb)} " if pb else ""
            win = f"SUM(SUM({col})) OVER ({part}ORDER BY {ob} ROWS UNBOUNDED PRECEDING)"
            sql = f"SELECT {grp}, SUM({col}) AS period_total, {win} AS running_total FROM `@{{bq_dataset}}.{t}` GROUP BY {grp}"
            analytic, head_agg, note = "running_total", "max", "RUNNING TOTAL (max = final cumulative)"
        elif m["type"] == "moving_avg":
            ob, n = m["order_by"], m["window"]; dims = pb + [ob]; grp = ", ".join(dims)
            part = f"PARTITION BY {', '.join(pb)} " if pb else ""
            win = f"AVG(SUM({col})) OVER ({part}ORDER BY {ob} ROWS BETWEEN {n - 1} PRECEDING AND CURRENT ROW)"
            sql = f"SELECT {grp}, SUM({col}) AS period_total, {win} AS moving_avg FROM `@{{bq_dataset}}.{t}` GROUP BY {grp}"
            analytic, head_agg, note = "moving_avg", "average", f"TRAILING {n}-period MOVING AVERAGE"
        else:  # percent_of_total — share of each group vs the whole (partition_by = the grouping dim)
            dims = pb; grp = ", ".join(dims)
            if grp:
                sql = (f"SELECT {grp}, SUM({col}) AS grp_total, "
                       f"SAFE_DIVIDE(SUM({col}), SUM(SUM({col})) OVER ()) AS pct_of_total "
                       f"FROM `@{{bq_dataset}}.{t}` GROUP BY {grp}")
            else:
                sql = f"SELECT SUM({col}) AS grp_total, 1.0 AS pct_of_total FROM `@{{bq_dataset}}.{t}`"
            analytic, head_agg, note = "pct_of_total", "sum", "PERCENT OF TOTAL (share by the group dim; sum = 1.0)"
        wv = [f"view: {vn} {{",
              f"  # WINDOW: {note}. Analytic value is the `{analytic}` dimension (group by the period/group dim).",
              "  derived_table: { sql:", f"    {sql} ;;", "  }"]
        keysql = " || '-' || ".join(f"CAST(${{TABLE}}.{c} AS STRING)" for c in dims) if dims else "'all'"
        wv.append(f"  dimension: pk {{ primary_key: yes  hidden: yes  sql: {keysql} ;; }}")
        wv += [f"  dimension: {d} {{ sql: ${{TABLE}}.{d} ;; }}" for d in dims]
        wv.append(f"  dimension: {analytic} {{ type: number  sql: ${{TABLE}}.{analytic} ;;{fmt} }}")
        # The author's `description` reaches measures through the per-TABLE view loop, keyed on
        # `mm["table"] == t` — and a rollup lives in its own view, so until 2026-08-10 the
        # description of every exiled window measure was silently DISCARDED. Run 009's author spent
        # an iteration writing one and it appeared nowhere in the emitted LookML.
        wdesc = f' description: "{_esc_desc(m["description"])}" ' if m.get("description") else ""
        wv.append(f"  measure: {name} {{{wdesc} type: {head_agg}  sql: ${{TABLE}}.{analytic} ;;{fmt} }}  # headline {head_agg}")
        wv.append("}")
        files[f"views/{vn}.view.lkml"] = "\n".join(wv) + "\n"

    # PERIOD-OVER-PERIOD portable fallback (native `type: period_over_period` needs the new LookML
    # runtime + dialect support that older instances lack). Per-period rollup derived_table: total +
    # LAG prior + diff + growth; `kind` picks the headline analytic. (Graph side = a LAG rollup node.)
    _POP_ANALYTIC = {"relative_change": "growth", "difference": "diff", "previous": "prev_total"}
    for m in measures:
        if m.get("type") != "period_over_period":
            continue
        if _pop_is_native(spec):
            continue      # NATIVE `type: period_over_period` measure on the owning view instead
        t, col, name = m["table"], m["column"], m["name"]
        period, kind = m["period"], m.get("kind", "relative_change")
        analytic = _POP_ANALYTIC.get(kind, "growth")
        fmt = f'  value_format: "{m["value_format"]}"' if m.get("value_format") else ""
        vn = f"{name}_pop"
        inner = (f"SELECT DATE_TRUNC({m['based_on_time']}, {period.upper()}) AS period, "
                 f"ROUND(SUM({col}), 2) AS total FROM `@{{bq_dataset}}.{t}` GROUP BY period")
        sql = ("SELECT period, total, "
               "LAG(total) OVER (ORDER BY period) AS prev_total, "
               "ROUND(total - LAG(total) OVER (ORDER BY period), 2) AS diff, "
               "ROUND(SAFE_DIVIDE(total - LAG(total) OVER (ORDER BY period), "
               "LAG(total) OVER (ORDER BY period)), 4) AS growth "
               f"FROM ({inner})")
        pv = [f"view: {vn} {{",
              f"  # PERIOD-OVER-PERIOD ({period}, {kind}) — portable rollup (native PoP needs new runtime).",
              "  derived_table: { sql:", f"    {sql} ;;", "  }",
              "  dimension: period { primary_key: yes  type: date  convert_tz: no  sql: ${TABLE}.period ;; }",
              "  dimension: total { type: number  sql: ${TABLE}.total ;; }",
              "  dimension: prev_total { type: number  sql: ${TABLE}.prev_total ;; }",
              "  dimension: diff { type: number  sql: ${TABLE}.diff ;; }",
              '  dimension: growth { type: number  value_format: "0.00%"  sql: ${TABLE}.growth ;; }',
              f"  measure: {name} {{ type: max  sql: ${{TABLE}}.{analytic} ;;{fmt} }}  # headline (latest {analytic})",
              "}"]
        files[f"views/{vn}.view.lkml"] = "\n".join(pv) + "\n"

    return files


# --------------------------------------------------------------------------- live BQ type check
# --------------------------------------------------------------------------- live BQ checks
# Shared plumbing for the three opt-in spec<->BigQuery reconciliation checks (--check-types,
# --check-compile, --check-data). Each needs live BQ (run under the `gc <profile>` wrapper);
# each skips gracefully on an illustrative spec whose dataset doesn't exist; each returns a
# process exit code (1 if any ERROR, else 0) so main() can aggregate with max().
def _bq_modules_or_none():
    """Lazy-import google-cloud-bigquery so the default (offline) generation path stays GCP-free.
    Returns (bigquery, gexc) or (None, None) if the client library isn't installed."""
    try:
        from google.cloud import bigquery
        from google.api_core import exceptions as gexc
        return bigquery, gexc
    except ImportError as e:
        print(f"live BQ checks need google-cloud-bigquery ({e})", file=sys.stderr)
        return None, None


def _dataset_missing(client, gexc, project, dataset, flag) -> bool:
    """True (and prints a skip note) if `project.dataset` doesn't exist — an illustrative spec
    whose tables aren't in BigQuery. Centralizes the graceful-skip branch for every check."""
    try:
        client.get_dataset(f"{project}.{dataset}")
        return False
    except gexc.NotFound:
        print(f"{flag}: `{project}.{dataset}` not found — skipping "
              f"(illustrative spec whose tables don't exist in BigQuery).")
        return True


def _report(title, project, dataset, errors, warns, infos, tail="") -> int:
    """Print the shared ERROR/WARN/INFO banner and return the exit code (1 if any ERROR)."""
    print(f"\n{'=' * 78}\n{title}  `{project}.{dataset}`{tail}\n{'=' * 78}")
    for tag, items in (("ERROR", errors), ("WARN ", warns), ("INFO ", infos)):
        for msg in items:
            print(f"{tag}  {msg}")
    print("-" * 78)
    print(f"{len(errors)} error(s), {len(warns)} warning(s), {len(infos)} info  ->  "
          f"{'FAIL' if errors else 'OK'}")
    print("=" * 78)
    return 1 if errors else 0


def check_types(spec: dict) -> int:
    """OPT-IN cross-check of the declared `layer1_structure.columns` types against the REAL BigQuery
    column types (INFORMATION_SCHEMA) for the spec's own `project.dataset`. Complements the offline
    `validate_spec()` (which checks shape) — this needs live BQ, so it's a separate `--check-types`
    step and only works on specs whose tables actually exist (illustrative specs skip gracefully).

    Credentials come from ADC (run under the `gc <profile>` wrapper); project/dataset come from the
    spec, so no repo `config` coupling is needed. Returns a process exit code: 1 if any ERROR, else 0.
    """
    bigquery, gexc = _bq_modules_or_none()
    if bigquery is None:
        return 1

    project, dataset = spec["project"], spec["dataset"]
    cols = spec.get("columns", {})   # {table: {col: type | {type, hidden}}}
    if not cols:
        print("--check-types: spec declares no layer1_structure.columns — nothing to check")
        return 0

    client = bigquery.Client(project=project)
    if _dataset_missing(client, gexc, project, dataset, "--check-types"):
        return 0

    tables = sorted(cols)
    in_list = ", ".join(f"'{t}'" for t in tables)
    sql = (f"SELECT table_name, column_name, data_type\n"
           f"FROM `{project}.{dataset}`.INFORMATION_SCHEMA.COLUMNS\n"
           f"WHERE table_name IN ({in_list})")
    rows = list(client.query(sql).result())

    # (table -> {col -> BQ data_type}) from BigQuery
    bq: dict[str, dict[str, str]] = {}
    for r in rows:
        bq.setdefault(r["table_name"], {})[r["column_name"]] = r["data_type"]

    errors, warns, infos, ok = [], [], [], 0
    for t in tables:
        bq_cols = bq.get(t)
        if not bq_cols:
            warns.append(f"{t}: table not found in `{project}.{dataset}` (nothing to check)")
            continue
        for col, cv in cols[t].items():
            dt = col_type(cv)
            bqt = bq_cols.get(col)
            if bqt is None:                                             # check 3
                warns.append(f"{t}.{col}: declared `{dt}` but the column is NOT in the BQ table "
                             f"(typo / dropped column — a query would fail)")
                continue
            if dt == "number" and bqt not in _BQ_NUMERIC:              # check 1
                errors.append(f"{t}.{col}: declared `number` but BQ type is {bqt} (aggregation would break)")
            elif dt in ("time", "timestamp", "date") and bqt not in _BQ_TEMPORAL:   # check 1
                errors.append(f"{t}.{col}: declared `{dt}` but BQ type is {bqt} (not a date/time type)")
            elif dt == "string" and bqt in (_BQ_NUMERIC | _BQ_TEMPORAL):           # check 2
                warns.append(f"{t}.{col}: declared `string` but BQ type is {bqt} "
                             f"(likely mistype — expose it as a typed dimension?)")
            else:
                ok += 1
        for bcol in bq_cols:                                          # check 4 (info)
            if bcol not in cols[t]:
                infos.append(f"{t}.{bcol}: in BigQuery ({bq_cols[bcol]}) but not exposed in the spec")

    return _report("TYPE CHECK vs BigQuery", project, dataset, errors, warns, infos,
                   tail=f"  ({len(tables)} tables, {ok} columns OK)")


def check_compile(spec: dict, patterns: dict, with_semantics: bool) -> int:
    """OPT-IN: verify the GENERATED graph DDL actually COMPILES against live BigQuery — the class of
    emission bug that validate_spec() + --check-types can't see (bad column ref, type error in a
    computed expression, a broken join in an edge view). The whole graph.sql runs as ONE dry-run job
    (dry_run=True): zero bytes billed, nothing created, and BQ's scripting analyzer resolves the
    intra-script `_node`/rollup -> edge/property-graph dependencies. The trailing
    `ALTER ... SET OPTIONS(description=...)` metadata block is stripped (not part of the compile
    surface). The parallel LookML window/PoP `derived_table` SQL is dry-run too (same machinery),
    after substituting the `@{bq_dataset}` Looker constant, since those emission bugs never reach the
    graph DDL. Returns a process exit code: 1 if anything fails to compile, else 0."""
    bigquery, gexc = _bq_modules_or_none()
    if bigquery is None:
        return 1
    project, dataset = spec["project"], spec["dataset"]
    client = bigquery.Client(project=project)
    if _dataset_missing(client, gexc, project, dataset, "--check-compile"):
        return 0

    dry = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    errors, warns, infos = [], [], []

    def _bq_err(e):
        """The concise BQ query error (e.errors[0].message) rather than the full HTTP-wrapped one."""
        return (e.errors[0].get("message") if getattr(e, "errors", None) else None) or e.message

    # --- graph.sql: one whole-script dry run (the analyzer resolves intra-script view deps) ---
    graph_ddl = gen_graph(spec, patterns, with_semantics).split("-- ==== column descriptions")[0]
    try:
        client.query(graph_ddl, job_config=dry)
        infos.append("graph.sql: compiles (whole-script dry run OK)")
    except gexc.GoogleAPICallError as e:
        errors.append(f"graph.sql: {_bq_err(e)}")

    # --- LookML derived_table SQL: dry-run each (window/PoP views the graph DDL can't cover) ---
    const = spec["looker"]["bq_dataset_constant"]
    n_derived = 0
    for rel, content in gen_lookml(spec, patterns, with_semantics).items():
        m = re.search(r"derived_table:\s*\{\s*sql:(.*?);;", content, re.DOTALL)
        if not m:
            continue
        n_derived += 1
        sql = m.group(1).replace("@{bq_dataset}", const).strip()
        try:
            client.query(sql, job_config=dry)
        except gexc.GoogleAPICallError as e:
            errors.append(f"{rel}: derived_table SQL failed to compile — {_bq_err(e)}")
    infos.append(f"LookML: {n_derived} derived_table view(s) dry-run")

    # THE ROLLUP VIEWS, BY NAME (2026-08-08; the exile itself removed 2026-08-10).
    #
    # ORIGINALLY: a window measure (`cumulative` / `moving_avg` / `percent_of_total`) cannot be a
    # LookML measure — a measure may not contain `SUM() OVER()` — so each was emitted as a
    # per-period rollup `derived_table` **with its own explore**, named `<measure name>_window`.
    # The CA agent binds to the primary root explore and had to DISCOVER those separately, so the
    # explore's name was the discovery signal, and the name is `m["name"]` from the spec — the
    # author's own choice, carried through verbatim.
    #
    # Run 008's Looker author had `cumulative_payments` and a golden question asking for the
    # "running cumulative total of payment amount". The agent never found the explore, and the
    # author — seeing only the COUNT ("5 derived_table view(s)") — concluded the exile itself was
    # fatal and froze the spec. The reference model, whose measure is `cumulative_payment_amount`,
    # scores 9/10 on the same question. The author could not see the name it had chosen for the
    # thing the agent had to find.
    #
    # SINCE 2026-08-10 the premise is gone in both directions: most window measures are now native
    # post-SQL measures on the owning view (`_window_needs_rollup`), and the rollups that remain are
    # JOINED into the root explore instead of exiled. So nothing here is unreachable any more and the
    # name is no longer a discovery signal. The line is kept — reduced to a plain statement of which
    # measures cost a rollup view — because "this measure could not be expressed natively" is still a
    # fact about the author's own spec that appears nowhere else. No suggestion, no verdict, no
    # reference to any question or answer key.
    # AMENDMENT A7 — description coverage, as a bare count.
    #
    # `description` is a universal optional on every measure type, copied onto the LookML field and
    # read by the Looker CA agent when it picks what to query. It is the author's own field, and
    # whether it is used is invisible from anything else in the gate.
    #
    # Run 008's Looker author described 7 of its 24 measures — and had, one iteration earlier,
    # demonstrated to itself that descriptions resolve an ambiguity ("that confirms the
    # disambiguation lever and I'm leaving it in place"). It never asked where else the lever
    # applied. The reference model describes 20 of 20.
    #
    # This is a COUNT and nothing else — the same class as A2's dropped-field key list. It names no
    # measure, points at no question, and offers no advice; whether a description is worth adding is
    # entirely the author's call.
    _ms = spec.get("layer2_semantics", {}).get("measures") or []
    if _ms:
        _described = sum(1 for m in _ms if m.get("description"))
        infos.append(f"spec: {_described} of {len(_ms)} measure(s) carry a `description` "
                     f"(optional; emitted to LookML and read by the Looker CA agent when it "
                     f"picks a field)")

    exiled = [(m["name"], m["type"]) for m in (spec.get("layer2_semantics", {}).get("measures") or [])
              if m.get("type") in ("cumulative", "moving_avg", "percent_of_total")
              and _window_needs_rollup(m)]
    if exiled:
        infos.append(
            "LookML: %d window measure(s) have no native LookML measure type, so each is a rollup "
            "derived_table view — JOINED into the root explore (many_to_one on its period key), so "
            "the CA agent can still reach it without leaving the explore it is bound to: %s"
            % (len(exiled), ", ".join(f"{n} ({t}) -> view `{n}_window`" for n, t in exiled)))

    # EXPLORE BUDGET (2026-08-10). An explore is the scarce resource, not a derived table: the
    # Conversational Analytics API binds at most 5 explores per agent and queries ONE per question
    # with no cross-explore joins, so every explore past the root is a wall no single question can
    # reach across. Run 009's model emitted SIX and nobody noticed for two runs, because the count
    # appeared nowhere. This states the count and, past the cap, refuses.
    #
    # The list went EMPTY on 2026-08-10 — every generated view is now joined into the root explore,
    # so a spec emits exactly ONE. Rollups join `many_to_one` (one row per period, no fan); the
    # unpivot joins `one_to_many` and does fan, correctly, with symmetric aggregates holding because
    # both sides declare a primary key.
    #
    # The mechanism is KEPT rather than deleted. It is how a future construct that genuinely cannot
    # be joined gets reported and counted against the cap, and the check below is what turns a
    # silently-dropped explore into a refusal. An empty list here is a measurement, not dead code:
    # it says this spec needs no walls.
    _isolated: list[tuple[str, str]] = []
    _n_explores = 1 + len(_isolated)
    _budget_line = ("LookML: %d explore(s) — root + %d isolated%s"
                    % (_n_explores, len(_isolated),
                       (": " + "; ".join(f"`{n}` ({why})" for n, why in _isolated)) if _isolated else ""))
    if _n_explores > CA_MAX_EXPLORES:
        errors.append(
            "%s. The Conversational Analytics API binds at most %d explore(s) per agent, so %d of "
            "these would be UNREACHABLE — and which ones get dropped is not defined here. Reduce "
            "the isolated explores (prefer a native measure type, or a rollup joined into the root "
            "explore) or split the spec."
            % (_budget_line, CA_MAX_EXPLORES, _n_explores - CA_MAX_EXPLORES))
    else:
        infos.append(_budget_line)

    return _report("COMPILE CHECK vs BigQuery", project, dataset, errors, warns, infos)


def check_data(spec: dict, patterns: dict) -> int:
    """OPT-IN: profile the base tables to test the spec's SEMANTIC CLAIMS against real data — the
    hazards the emitter can only flag as TODO comments (grain vs dedup, referential integrity, M:N
    degree, semi-additive periodicity). Turns "trust the spec" into "verify against the data." Small
    aggregate queries only (demo-scale), capped by maximum_bytes_billed. Returns 1 if any ERROR."""
    bigquery, gexc = _bq_modules_or_none()
    if bigquery is None:
        return 1
    project, dataset = spec["project"], spec["dataset"]
    client = bigquery.Client(project=project)
    if _dataset_missing(client, gexc, project, dataset, "--check-data"):
        return 0

    def fq(t):
        return f"`{project}.{dataset}.{t}`"

    cfg = bigquery.QueryJobConfig(maximum_bytes_billed=10 * 1024 ** 3)   # bound scans (tables are tiny)

    def scalar(sql):
        return list(client.query(sql, job_config=cfg).result())[0]

    existing = {r.table_name for r in client.query(
        f"SELECT table_name FROM `{project}.{dataset}`.INFORMATION_SCHEMA.TABLES").result()}

    tables = spec["schema"]["tables"]
    dedup = spec.get("semantics", {}).get("dedup", {})
    m2n = spec.get("semantics", {}).get("m2n", {})
    measures = spec.get("semantics", {}).get("measures", [])
    errors, warns, infos = [], [], []

    # 1) PK grain vs dedup — the core trap check (sums over a non-unique grain double-count) ----
    for t, ts in tables.items():
        if t not in existing:
            continue
        keys = pk_cols(ts)
        key_expr = keys[0] if len(keys) == 1 else f"TO_JSON_STRING(STRUCT({', '.join(keys)}))"
        r = scalar(f"SELECT COUNT(*) n, COUNT(DISTINCT {key_expr}) d FROM {fq(t)}")
        pk_disp = ", ".join(keys)
        if r.n > r.d:                                          # duplicates on the declared grain
            if t in dedup:
                infos.append(f"{t}: grain ({pk_disp}) is non-unique — {r.n - r.d} dup row(s); "
                             f"dedup rule present (expected).")
            else:
                errors.append(f"{t}: declared grain ({pk_disp}) is NOT unique — {r.n - r.d} dup "
                              f"row(s); sums will double-count (add a layer2_semantics.dedup rule).")
        elif t in dedup:                                      # unique, yet a dedup rule is declared
            infos.append(f"{t}: dedup rule declared but grain ({pk_disp}) is already unique "
                         f"(rule may be unnecessary / the trap isn't present in this data).")

    # 2) FK referential integrity — orphans silently NULL the parent's attributes in a 1:N join --
    for rel in spec["schema"]["relationships"]:
        if rel.get("as_of"):                                  # range join, not an equality FK
            continue
        parent, child, fk = rel["parent"], rel["child"], rel["fk"]
        if parent not in existing or child not in existing:
            continue
        ppk = pk_cols(tables[parent])
        if len(ppk) != 1:
            warns.append(f"{child}->{parent} on {fk}: parent has a composite key {ppk}; "
                         f"skipping FK integrity check.")
            continue
        r = scalar(f"SELECT COUNT(*) orphans FROM {fq(child)} c "
                   f"LEFT JOIN {fq(parent)} p ON c.{fk} = p.{ppk[0]} "
                   f"WHERE p.{ppk[0]} IS NULL AND c.{fk} IS NOT NULL")
        if r.orphans:
            warns.append(f"{child}.{fk} -> {parent}.{ppk[0]}: {r.orphans} orphan row(s) with no "
                         f"matching parent (a 1:N join silently NULLs the parent's attributes).")

    # 3) M:N bridge degree — is the M:N modeling actually exercised, or does the data behave 1:N? --
    for b, info in m2n.items():
        if b not in existing:
            continue
        binfo = patterns["bridges"].get(b)
        if not binfo:
            continue
        between, cols = binfo["between"], binfo["cols"]
        entity = info.get("entity")
        if entity not in between:
            continue
        ei = between.index(entity)
        entity_key, other_key = cols[ei], cols[1 - ei]
        r = scalar(f"SELECT MAX(c) mx FROM (SELECT {entity_key}, COUNT(DISTINCT {other_key}) c "
                   f"FROM {fq(b)} GROUP BY {entity_key})")
        if (r.mx or 0) <= 1:
            infos.append(f"{b}: max {other_key} per {entity_key} is {r.mx} — the M:N relationship "
                         f"isn't exercised in this data (behaves 1:N).")

    # 4) semi-additive periodicity — "period-end" is trivial if the snapshot has one period --------
    for m in measures:
        if m.get("type") not in ("semi_additive", "semi_additive_avg"):
            continue
        t, period = m["table"], m.get("period")
        if t not in existing or not period:
            continue
        r = scalar(f"SELECT COUNT(DISTINCT {period}) p FROM {fq(t)}")
        if (r.p or 0) <= 1:
            infos.append(f"{t}.{m['name']}: only {r.p} distinct {period} — semi-additive "
                         f"'period-end' is trivial with a single period.")

    return _report("DATA CHECK vs BigQuery", project, dataset, errors, warns, infos)


# --------------------------------------------------------------------------- report
def _has_measure(spec, *types) -> bool:
    """True iff this spec declares at least one measure whose `type` is in `types`."""
    return any(m.get("type") in types for m in spec.get("semantics", {}).get("measures", []))


def coverage_report(spec, patterns, with_semantics) -> str:
    # PER-SPEC coverage: each `covered` cell is a PRESENCE predicate evaluated against THIS spec
    # instance — does the spec actually populate the construct — NOT whether a build stage is enabled.
    # main() has already bridged the 2-layer input onto spec["semantics"] (dedup/m2n/measures) and
    # left the raw Layer-1 on spec["layer1_structure"]; read both directly.
    l1 = spec.get("layer1_structure", {}) or {}
    sem = spec.get("semantics", {}) or {}
    rels = l1.get("relationships") or []
    tables = l1.get("tables") or {}
    columns = l1.get("columns") or {}

    # ---- structure presence predicates ----------------------------------------------------------
    has_tables = bool(tables)
    has_rels = bool(rels)
    parents = [r.get("parent") for r in rels]
    has_chasm = any(parents.count(p) >= 2 for p in set(parents))            # one parent, ≥2 children
    has_graph = bool(spec.get("graph_name"))
    has_columns = bool(columns)
    has_alias_role = any(r.get("alias") and r.get("parent") != r.get("child") for r in rels)
    has_hierarchies = bool(l1.get("hierarchies"))
    has_self_ref = any(r.get("parent") == r.get("child") for r in rels)
    has_accumulating = bool(l1.get("accumulating"))
    has_as_of = any(r.get("as_of") for r in rels)

    # ---- semantics presence predicates ----------------------------------------------------------
    has_dedup = bool(sem.get("dedup"))
    has_m2n = bool(sem.get("m2n"))
    has_weighted_alloc = any(m.get("type") == "allocated_sum" and m.get("weight_column")
                             for m in sem.get("measures", []))

    rows = [
        ("plain aggregate (count/sum)", "structure", has_tables, "graph: any property; LookML: count (sums need a measure decl)"),
        ("fan trap safety", "structure", has_rels, "LookML symmetric agg (auto); graph: aggregate per MATCH"),
        ("chasm trap safety", "structure", has_chasm, "two independent children handled per-fact"),
        ("zero-fill denominator", "structure", has_tables, "count over parent view / all nodes"),
        ("filter / group-by / top-N / recency (graph)", "structure", has_graph and has_columns, "graph auto-exposes all columns as properties"),
        ("filter / group-by / top-N / recency (LookML)", "structure", has_columns, "LookML dimension per column (rides with structure)"),
        ("duplication (hidden non-unique PK)", "semantics.dedup", has_dedup, "de-dup view / derived_table"),
        ("weighted average (avg-of-avg)", "semantics.rate", _has_measure(spec, "rate"), "ratio measure / rate_x_weight property"),
        ("semi-additive over time", "semantics.semi_additive", _has_measure(spec, "semi_additive"), "period-end filter / is_latest flag"),
        ("M:N allocation", "semantics.m2n", has_m2n, "count_distinct / owner_count"),
        ("child-side-filtered ratio (time filter)", "semantics.filtered_ratio", _has_measure(spec, "filtered_ratio"), "LookML: value-INDEPENDENT parameter; graph: one materialized column PER period"),
        ("M:N split allocation (attribute per owner)", "semantics.allocated_sum", _has_measure(spec, "allocated_sum"), "graph: FREE (owner_count prop + bridge edge); LookML: new measure + owner join"),
        ("semi-additive AVERAGE over time", "semantics.semi_avg", _has_measure(spec, "semi_additive_avg"), "BOTH pay: LookML identity SUM/COUNT(DISTINCT); graph materialized monthly node"),
        ("role-playing dimension (same dim, N roles)", "structure.relationships.alias", has_alias_role, "LookML many_to_one aliased joins (from:); graph distinct labeled edges"),
        ("hierarchy drill path", "structure.hierarchies", has_hierarchies, "LookML drill_fields; graph exposes every level as a property (no drill needed)"),
        ("recursive/self-ref hierarchy", "structure.relationships.alias (self)", has_self_ref, "GRAPH WIN: variable-length MATCH; LookML many_to_one self-join (one level)"),
        ("accumulating snapshot (funnel counts)", "structure.accumulating", has_accumulating, "reached-stage flag + count per milestone (both stacks)"),
        ("milestone lag (duration between stages)", "semantics.milestone_lag", _has_measure(spec, "milestone_lag"), "DATE_DIFF dimension + agg (LookML); precomputed lag node prop (graph)"),
        ("period-over-period (YoY/MoM)", "semantics.period_over_period", _has_measure(spec, "period_over_period"), "LookML native type: period_over_period; graph LAG rollup node"),
        ("as-of / effective-dated (SCD2) join", "structure.relationships.as_of", has_as_of, "range join on validity window (both stacks); graph as-of edge view"),
        ("window: running total / moving avg / %-of-total", "semantics.window", _has_measure(spec, "cumulative", "moving_avg", "percent_of_total"), "LookML rollup derived_table (table-calc cost); graph window rollup node"),
        ("M:N split, WEIGHTED (non-equal)", "semantics.allocated_sum.weight_column", has_weighted_alloc, "amount × weight_column (Kimball weighting-factor bridge)"),
    ]
    out = ["", "=" * 78, "COVERAGE REPORT  (stages enabled: structure"
           + (" + semantics" if with_semantics else "") + ")", "=" * 78,
           f"{'scenario':<46}{'needs':<25}covered", "-" * 78]
    for name, needs, ok, _ in rows:
        out.append(f"{name:<46}{needs:<25}{'YES' if ok else 'NO'}")
    out.append("-" * 78)
    out.append("covered = the spec CONTAINS the construct (presence check against THIS spec instance);")
    out.append("it is NOT a correctness claim — correctness is verified separately by the DATA CHECK")
    out.append("(--check-data, grain/dedup/FK/M:N/periodicity) and by the PRISM eval.")
    out.append("=" * 78)
    return "\n".join(out)


def main():
    # A2-F5, the producer half. This process's stdout is a PIPE under `hill_climb._run` (and so
    # under `loop.py`'s tee), which makes it block-buffered while its stderr stays unbuffered — so
    # a traceback lands ABOVE the output it followed, and above the `$ generate_models.py …` marker
    # that introduced the whole block. That mis-ordering is the measured cause of the three
    # archived console PROLOGUES and of S3's 22-of-49 empty gate stubs; `capture_iteration` now
    # rescues those cases (X6), but the right fix is not to create them. No byte changes, only its
    # arrival time. Guarded: a caller that redirected stdout to a buffer has nothing to reconfigure.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=os.path.join(PLAYBOOK, "specs", "cymbal_v6x.yaml"))
    ap.add_argument("--out", default=None, help="output dir (default: generated/<legs>)")
    ap.add_argument("--skip-semantics", action="store_true")
    ap.add_argument("--check-types", action="store_true",
                    help="after emitting, cross-check declared column types against live BigQuery "
                         "INFORMATION_SCHEMA (needs ADC / the gc wrapper; real datasets only)")
    ap.add_argument("--check-compile", action="store_true",
                    help="after emitting, dry-run the generated graph DDL + LookML derived SQL "
                         "against live BigQuery to catch emission bugs (needs ADC / the gc wrapper)")
    ap.add_argument("--check-data", action="store_true",
                    help="after emitting, profile the base tables to verify the spec's semantic "
                         "claims (grain/dedup, FK integrity, M:N degree, semi-additive periodicity)")
    ap.add_argument("--check-all", action="store_true",
                    help="run --check-types, --check-compile and --check-data together")
    args = ap.parse_args()

    with open(args.spec) as fh:
        spec = yaml.safe_load(fh)

    # Validate the field contract BEFORE anything reads it (see specs/SPEC_REFERENCE.md). Raises
    # SpecError on hard errors (unknown measure type, missing required key, bad table ref);
    # prints non-fatal warnings (unexpected/ignored keys).
    for w in validate_spec(spec):
        print(f"WARNING: {w}", file=sys.stderr)

    # ---- Bridge: 2-layer INPUT -> the generator's internal working keys --------------------------
    # The YAML has two layers (PLAYBOOK.md §2): what KIND of modeling work each part is. They map
    # onto the two build STAGES 1:1 (layers == stages now):
    #   layer1_structure (grains + relationships + columns) -> schema + columns   (structure stage; always on)
    #   layer2_semantics (dedup + m2n + measures + unpivot) -> semantics          (+semantics stage; --skip-semantics)
    l1 = spec["layer1_structure"]
    l2 = spec.get("layer2_semantics") or {}

    # Merge the EXPLICIT entity / bridge / snapshot blocks into the one `tables` dict the emitters
    # consume. Order (entities -> bridges -> snapshots) preserves node/edge emission order. Bridges &
    # snapshots get a synthesized `primary_key`; snapshots also carry their `singular_label` (nodes).
    tables = dict(l1["tables"])                                     # entities: {primary_key, singular_label}
    for b, info in (l1.get("bridges") or {}).items():
        tables[b] = {"primary_key": list(info["between"].values())}
    for s, info in (l1.get("snapshots") or {}).items():
        tables[s] = {"primary_key": [info["entity_key"], *_as_list(info["period"])],
                     "singular_label": info["singular_label"]}
    spec["schema"] = {"tables": tables, "relationships": l1["relationships"]}

    # Classification comes straight from the explicit blocks (no inference).
    patterns = read_patterns(l1)

    # m2n: derive entity_key/other from the bridge's `between` so the emitters get the full dict
    # ({entity, entity_key, other, allocation}) without the spec having to repeat those keys.
    m2n = {}
    for b, info in (l2.get("m2n") or {}).items():
        between = (l1.get("bridges") or {}).get(b, {}).get("between") or {}
        entity = info.get("entity")
        other = next((tbl for tbl in between if tbl != entity), None)
        m2n[b] = {**info, "entity_key": between.get(entity), "other": other}

    spec["columns"] = l1.get("columns", {})   # Layer-1 dimension exposure: {col: type | {type, hidden}}
    spec["semantics"] = {
        "dedup": l2.get("dedup", {}),
        "m2n": m2n,
        # ALL measures — one block (business-vs-rule-derivable is a per-measure comment, not a split).
        "measures": list(l2.get("measures", [])),
    }
    spec["unpivot"] = l2.get("unpivot", {})   # Layer-2 semantics: wide-column -> long (composition) surfaces
    spec.setdefault("defaults", {})           # optional top-level format knobs (read by gen_lookml)

    with_semantics = not args.skip_semantics

    legs = "structure" + ("_semantics" if with_semantics else "")
    out = args.out or os.path.join(PLAYBOOK, "generated", legs)
    # gap 28 (W5, 2026-08-05). `--out` is `gen_dir` from the run config, and run_config's own
    # contract is that gen_dir is SCRATCH ("the run folder is immutable evidence; /tmp is the
    # scratch", run_config.validate) — the copy under `runs/<run>/<step>/generated/` is made by
    # capture_iteration.py afterwards, from the /tmp original. So nothing is ever declared
    # allowed here: a `--out` under runs/ is a misconfiguration that would overwrite a captured
    # step's [D] evidence. Checked before the makedirs, so a refusal leaves no tree behind.
    _AP.guard(out, "generate_models --out")
    os.makedirs(os.path.join(out, "lookml", "views"), exist_ok=True)

    graph_ddl = gen_graph(spec, patterns, with_semantics)
    with open(os.path.join(out, "graph.sql"), "w") as fh:
        fh.write(graph_ddl)
    lookml = gen_lookml(spec, patterns, with_semantics)
    for rel, content in lookml.items():
        path = os.path.join(out, "lookml", rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(content)

    print(f"declared: bridges={list(patterns['bridges'])}  snapshots={list(patterns['snapshots'])}")
    print(f"wrote graph.sql + {len(lookml)} LookML files -> {out}")
    print(coverage_report(spec, patterns, with_semantics))

    # Opt-in live-BQ reconciliation checks (each runs under the `gc` wrapper). Aggregate exit
    # codes so ANY check's ERROR fails the process; the default (no flag) path stays offline.
    codes = []
    if args.check_types or args.check_all:
        codes.append(check_types(spec))
    if args.check_compile or args.check_all:
        codes.append(check_compile(spec, patterns, with_semantics))
    if args.check_data or args.check_all:
        codes.append(check_data(spec, patterns))
    if codes:
        sys.exit(max(codes))


if __name__ == "__main__":
    main()
