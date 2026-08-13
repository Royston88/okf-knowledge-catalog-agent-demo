# Proposal — representing `spec.yaml` in OKF v0.2, and how kcmd should project it

Consolidates what was measured across Phases 1–8 and the follow-ups. Every
"measured" claim below has evidence in `MEASUREMENTS.md`. Nothing here is
implemented yet except where marked **done**.

---

## Part A — `spec.yaml` → OKF v0.2

### A.0 Coverage today

`generate_models.py` (LookML + graph) reads **all 11** spec constructs.
`gen_okf.py` reads 7 and emits concepts for **2**.

| construct | n | today | proposed |
|---|---|---|---|
| `tables` + `columns` | 10 + 68 | `BigQuery Table` × 13 (authored by `reference_agent`) | unchanged — columns stay `# Schema` rows |
| `relationships` + `bridges` | 11 + 2 | **`Join` × 13** | unchanged |
| `measures` | 26 | **`Metric` × 26** | unchanged |
| `dedup` | 1 | prose inside Join/Metric bodies | **`Grain Rule`** concept |
| `snapshots` | 1 | prose | **`Grain Rule`** concept |
| `accumulating` | 1 | **not read** | **`Grain Rule`** concept |
| `m2n` | 2 | prose in the bridge Joins | unchanged — it *is* the bridge join |
| `hierarchies` | 1 | **not read** | **`Hierarchy`** concept |
| `unpivot` | 1 | **not read** | **`Derived Table`** concept |

Result: 13 + 26 + 3 + 1 + 1 = **44 reference concepts**, plus 14 asset-backed =
**58**. Three new types, full coverage, no construct left unrepresented.

### A.1 Why new types are cheap

§4.1: type values are **not centrally registered**; producers SHOULD pick
descriptive values and consumers MUST tolerate unknown types. `Join` and
`Metric` are already outside the spec's example list. `Grain Rule`,
`Hierarchy` and `Derived Table` are equally legitimate.

### A.2 Why these three and not more

The test is **addressability**: a rule that lives only as a sentence inside
another document cannot be retrieved, linked, verified or signed off
independently. `dedup`, `snapshots` and `accumulating` are each a table-level
correctness rule with its own lifecycle — exactly what a concept is for.
`m2n` is not, because the bridge Join already *is* that concept.

Keep them under `references/grain/<table>.md`, matching the existing
`references/joins/` and `references/metrics/` convention (§6.3) and preserving
the producer boundary: `gen_okf.py` owns `references/**`, `reference_agent`
owns `tables/**`.

### A.3 `Attested Computation` — the right end state, not now

§10.4 is explicit that `Metric` and `Attested Computation` are complementary,
not alternatives: a Metric holds the meaning and *links to* a computation that
holds sanctioned SQL plus an attester. Two reasons to defer:

- **22 of 26 measures have no liftable SQL.** Only the 4 window/PoP measures
  emit LookML `derived_table` blocks that are executable modulo one constant;
  the other 22 are measure expressions needing Looker's compiler and the
  explore join graph. Deriving standalone SQL for them is new work *and* a
  second definition free to drift from the LookML one.
- **The attester runs consumer-side.** Our harness runs none, so it would be
  inert today.

When it is built: one `Attested Computation` per measure, `runtime: bigquery`,
`Metric` links to it. Note §10.6 — `verified` and attestation are different
guarantees, and we currently have only the first.

### A.4 Also missing from the bundle

- **`log.md`** (§9) — absent. Cheap, and it is where the bundle's own history
  belongs.
- **`stale_after`** — 0/53 concepts. The spec's freshness signal is unused.
- **`status`** — only ever `stable`.

---

## Part B — how kcmd should interface with Knowledge Catalog

### B.1 Two tracks, split by asset-backing — **done**

A concept with a top-level `resource:` names an ingested asset and belongs
**on** that entry; everything else needs an entry of its own. This is what
stopped the catalog showing two objects per table (28 search hits → 14).

| | Track A — asset-backed (14) | Track B — abstract (44) |
|---|---|---|
| where | the ingested `@bigquery` entries | `okf_cymbal_v6z`, entry type `generic` |
| why generic | measured: no native `join`/`metric`/`measure`/`dimension` entry type exists | |

### B.2 Aspects, and who owns them — **done**

| aspect | written | ownership |
|---|---|---|
| `okf` (custom) | always | ours — no scan touches a custom type |
| `overview` | always | ours — the scan does not write it; the aspect type has **no** `userManaged` field |
| `descriptions` | always | **contested** — `userManaged = verified` |
| `queries` | always | **contested** — `userManaged = verified` |

`userManaged` is stored nowhere. It is **computed from `verified` at push
time**, which is correct if Knowledge Catalog is one projection target rather
than the system of record. Contested aspects are always written with the
computed flag, so writing `false` *is* the release — no separate release path,
because omitting an aspect is a no-op rather than a release.

Two gotchas worth keeping: every aspect under `publishing` must also appear
under `snapshot`, and `getEntry`'s aspect filter takes **full resource names**,
not the dotted alias (the alias 400s, and an empty aspect map on a failed
response reads as "nothing there").

### B.3 Links — the discovery layer, **to build**

Measured, all three types:

| link | target | direction | traversable via `lookup_entry_links`? |
|---|---|---|---|
| `related` | any entry | **undirected** — both refs `UNSPECIFIED` | **yes** |
| `definition` | **glossary term only** | directed, `path=Schema.<col>` | **yes** |
| `schema-join` | table ↔ table | undirected | yes, but scan-owned |

**Emit `related` from each table entry to its Join / Metric / Grain Rule
concepts.** This is the fix for the discovery gap that cost q4: the knowledge
existed in a concept the agent could have fetched by name, and it fetched a
different document.

**Do not emit `schema-join`** — the scan owns it, and v7 measured it is not
consumed as a join hint.

**Emit `definition` links only for genuinely shared vocabulary** — `segment`,
`customer_id`, `account_id`. Reuse is decided by *meaning*, not by column-name
collision: `amount` ×4 and `balance` ×2 are traps.

kcmd already has every primitive: `createEntryLink`, `createGlossary`,
`createGlossaryTerm`, `toServiceGlossaryTerm`, `sources/glossary.ts`, the
`definition`/`related` aliases, and `entryLinks` in both manifest configs.

### B.4 What the consuming agent needs

Reach differs sharply by consumer, and this is the part most easily got wrong:

| channel | prebuilt dataplex toolbox | custom ADK agent | BQ CA API |
|---|---|---|---|
| `overview` / `descriptions` | yes (`lookup_context`; `lookup_entry` only at `view=ALL`) | yes | no — CA reads **BigQuery's own** descriptions |
| `definition` → glossary term | yes (`lookup_context`, inline as `terms:`) | yes | **yes** |
| `related` → concept | **no link tool** | **yes** — `lookup_entry_links` | no |

So for a custom ADK agent, three things:

1. A **`lookup_entry_links` function tool** — the traversal the toolbox lacks.
2. **Force `view=ALL`** on `lookup_entry`. Its default `FULL` returns
   non-required aspects as *keys only*, so `overview`, `descriptions` and
   `queries` are all withheld — 3,619 chars vs 13,302. A
   `before_tool_callback` is deterministic where a prompt instruction is not.
3. Prefer **`lookup_context`** — it is the one call that returns the whole
   projection resolved, glossary terms included.

### B.5 The finding that should shape expectations

Across 75 Arm-D runs, score tracked the **retrieval rate**, not the content:
Arm K 11/15 correct with `lookup-entry` called 14/15; the D family 6–8/15 with
it called 1–5/15. On the two questions only the catalog can settle, calling it
gave 2 correct of 6 against 1 of 24 without.

Three successive content improvements — `overview`, then
`descriptions`/`queries`, then forcing `view=ALL` — moved the D family by two
points. **The bottleneck is that the agent does not ask.** Everything in Part B
is necessary and none of it is sufficient; the tool surface has to make
retrieval the path of least resistance.

---

## Implementation order

1. **`related` links** table → its concepts, plus the `lookup_entry_links` tool.
   Highest measured value; fixes the gap that cost q4.
2. **`Grain Rule` / `Hierarchy` / `Derived Table` concepts** — closes spec
   coverage. After (1), so they are reachable when they land.
3. **Prose "Related concepts" summary in `overview`** — the fallback for
   consumers with no link tool.
4. **Glossary terms** for shared vocabulary — the only channel reaching all
   three consumers.
5. **`log.md`, `stale_after`** — cheap spec conformance.
6. **`Attested Computation`** — once a consumer-side attester exists.
