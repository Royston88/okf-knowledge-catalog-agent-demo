# OKF ⇄ Knowledge Catalog — the bundle is the source of truth

An **OKF v0.2 bundle in git is the system of record** for what a BigQuery
dataset means. Dataplex Knowledge Catalog is a *projection* of it: a push makes
the catalog match the bundle, and a differ reports when the two disagree.

That is the inversion this branch exists to test. The tool underneath —
[`kcmd`](kcmd/) — was built for the opposite direction, and the interesting part
of the result is *why* it was, and what had to change.

**58 concepts · 190 cross-concept links · 82 catalog links · two projection
tracks · a forward differ that exits 0 when the catalog still matches.**

## One substrate, several consumers

This branch adds a **substrate** — a bundle in git, a catalog that provably
matches it, and the machinery that keeps the two in agreement. It does not
replace the agent work that consumes them. Three tracks share the repo:

| track | what it does | consumes | this document |
|---|---|---|---|
| **the projector** | makes the catalog match the bundle, and reports when it stops matching | — it *produces* both | **is about this** |
| [`bq-kc-agent/`](bq-kc-agent/) | natural language → BigQuery SQL, via the **catalog** path | the catalog the projector writes | see [its own README](bq-kc-agent/README.md) |
| [`okf-eval/`](okf-eval/) | not an agent — the **rig** that scores one arm against another | both paths, to compare them | [ARCHITECTURE §2](docs/ARCHITECTURE.md) |

The seam matters because the tracks are easy to mistake for rivals.
`okf-eval/run_arms.py` is a measurement harness with a deliberately minimal
instruction; `bq-kc-agent/` is the product agent. A third consumer reading SQL
off the bundle path directly would sit alongside them, not replace either.

Everything below this line is the projector.

## Where to start

Five documents, split by **kind** rather than by topic, so each has one job.
**Read them in this order** — each assumes the one before it.

| # | document | what it is for | read it when |
|---|---|---|---|
| 1 | **[docs/DESIGN.md](docs/DESIGN.md)** | **Start here.** What exists, why it is shaped this way, and what was wrong with the tooling underneath: the model, the three ownership tiers, the differ, the direction of authority, the eight kcmd defects, the verification commands, the known gaps. | always |
| 2 | [docs/RESULTS.md](docs/RESULTS.md) | The conclusions. Does this work, is it worth using, and which claims are measured **false**. §7 corrects three that did not survive scrutiny. | deciding whether to adopt any of this |
| 3 | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | The as-built diagrams, what each hop costs you, and the Phase 8 evaluation harness. A companion to DESIGN, not a second home for the reasoning. | you want the picture rather than the prose |
| 4 | [docs/HANDOFF.md](docs/HANDOFF.md) | Operational state: environment, credentials, the exact commands, what is done, what is next, and any blocker in symptom → ruled-out → prime-suspect → ways-forward form. | you are about to **run** something |
| 5 | [docs/MEASUREMENTS.md](docs/MEASUREMENTS.md) | The append-only evidence log. Every "measured" claim in the other four cites it. Long, and not meant to be read front to back. | you want to check a number |

There is no separate forward plan: what remains open is **DESIGN §12, Known
gaps**.

## The shape of it

```
spec.yaml ──> gen_okf.py ─────> okf-bundle/references/**   (44 concepts)
          └─> reference_agent ─> okf-bundle/tables|datasets/** (14 concepts)
                                        │
                          mirror.py     │  the tier-A cache, computed from BigQuery
                          postauthor.py │  absolute links, status, back-links
                          canonicalize  │  canonical frontmatter, always last
                                        ▼
                                 okf-bundle/   ← git = the source of truth
                                        │
                     toOkfStaging()     │  project into a kcmd-native tree
                                        ▼
                              .staging/bundle/   disposable, gitignored
                                   │      ▲
              push only what differs│      │ expected vs actual — the differ
                                   ▼      │   and the push planner
                        Dataplex Knowledge Catalog
```

**kcmd never sees `okf-bundle/`.** It reads and writes only the staged tree, so
the bundle stays tool-agnostic — it carries no Dataplex vocabulary, and a second
projector could consume the same bundle without disturbing the first.

Two tracks, split by one property the bundle already carries. A concept with a
top-level `resource:` names an asset Dataplex has already ingested, so it belongs
**on** that entry (**Track A**, 4 aspects on 14 `@bigquery` entries). Everything
else needs an entry of its own (**Track B**, 44 concepts + 7 directory entries in
our own EntryGroup).

## Layout

The same walk again, as directories — top to bottom is stage 1 to stage 5.

| stage | path | what you run | what it is |
|---|---|---|---|
| in | [`kc-capture/`](kc-capture/) | — | a frozen capture of Knowledge Catalog — `kc_snapshot.json`, `profile/`, `relationships.json`, hash-manifested by `capture_manifest.json`. Reproducible **input** to authoring, never a source of truth |
| 1 | [`okf-emitter/`](okf-emitter/) | [`gen_okf.py`](okf-emitter/gen_okf.py) | the deterministic producer — `references/joins/**` and `references/metrics/**`, from [`spec.yaml`](okf-emitter/spec.yaml) |
| 1b | [`okf-author/`](okf-author/) | [`author_bundle.py`](okf-author/author_bundle.py) | `reference_agent` over BigQuery **+** the capture — the 13 table and 1 dataset concepts. The one non-deterministic stage |
| 2 | [`okf-review/`](okf-review/) | [`mirror.py`](okf-review/mirror.py) → [`postauthor.py`](okf-review/postauthor.py) → [`canonicalize.py`](okf-review/canonicalize.py) | the three passes over the whole bundle, in that order: the tier-A cache from BigQuery; absolute links, status and back-links; canonical frontmatter last |
| 3 | [`okf-review/`](okf-review/) | [`conformance.py`](okf-review/conformance.py), [`check_doc_links.py`](okf-review/check_doc_links.py), and `--check` on the three above | assert the bundle is final. All exit non-zero on failure, so CI can gate on them |
| — | [`okf-bundle/`](okf-bundle/) | — | **the source of truth.** Clean OKF v0.2, tool-agnostic, in git. Every stage above writes it; every stage below only reads it |
| 4 | [`okf-kb-workspace/`](okf-kb-workspace/), [`bq-okf-workspace/`](bq-okf-workspace/) | `catalog.yaml` in each | the two push manifests (Track B, Track A). No copy of the bundle lives here |
| 4–5 | [`kcmd/`](kcmd/) | [`demo/okf/push.ts`](kcmd/demo/okf/push.ts), [`push-track-a.ts`](kcmd/demo/okf/push-track-a.ts), [`drift.ts`](kcmd/demo/okf/drift.ts) | the vendored fork that projects and differs. `src/` is patched (8 defects, upstreamable); `demo/okf/` is ours; `docs/` is Google's and is quoted in DESIGN §9 |
| out | [`_state/`](_state/) | — | tracked evidence: Measurement G, the live-entry probe, the drift baseline |
| out | [`okf-eval/`](okf-eval/) | [`run_arms.py`](okf-eval/run_arms.py) | the Phase 8 evaluation harness (Arm K vs Arm D) — reads the catalog back |

The rest of `okf-review/` is **one-off evidence, not pipeline**: `count_entrygroup.py`
and `count_links.py` (what actually landed, following pagination), `probe_entries.py`
and `probe_glossary.py` (questions only a live catalog can answer), `measure_g.py`
(does curated content survive a re-scan), `signoff.py` and `join_triage.yaml`.

`docs/` sits outside the sequence — it is the as-built documentation, see above.

## Running it

The same five stages, as commands. Everything runs **from this directory**.
Steps marked **○** need no credentials; the rest need the prelude in
**[docs/HANDOFF.md](docs/HANDOFF.md) §2.7** — three different identities are in
play and getting it wrong fails in ways that look like missing IAM.

**1 · Emit** ○ — `references/joins/**` and `references/metrics/**`, from the
spec that also produces the property graph and the LookML model.

```bash
python okf-emitter/gen_okf.py --spec okf-emitter/spec.yaml --out okf-bundle
```

**1b · Author** — the other 14 concepts, the tables and datasets.
`reference_agent` reads BigQuery through `KCBigQuerySource`, which merges in the
frozen `kc-capture/` so the author can see what a catalog scan produced. The
model is served at location **`global`** — it is 404 in `us-central1`.

```bash
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_PROJECT=royston-dev-8253 GOOGLE_CLOUD_LOCATION=global

OKF_KC_DIR=kc-capture python okf-author/author_bundle.py \
    --dataset royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy \
    --out okf-bundle --model gemini-3.5-flash
```

**This is the one stage that does not reproduce.** Stage 1 is deterministic by
construction — same spec in, byte-identical concepts out — but 1b re-authors
prose against a model, so a re-run gives you *a* bundle, not *the* bundle in
git, and it overwrites the committed 14 concepts in place. Run it to see the
authoring work; `git checkout okf-bundle/tables okf-bundle/datasets` to get the
evidenced text back. Everything downstream is reproducible either way.

Expect intermittent `429 RESOURCE_EXHAUSTED`. The original run lost
`tables/transactions` that way; back-fill a single concept rather than re-running
the lot, and check all 13 table concepts exist before trusting a run:

```bash
OKF_KC_DIR=kc-capture python okf-author/author_bundle.py \
    --dataset royston-dev-8253.cymbal_bank_v6z_scaffold_demo_copy \
    --out okf-bundle --concept tables/transactions
```

Either way the canonicaliser in stage 2 is **required** afterwards —
`reference_agent` writes non-canonical frontmatter every time it authors.

**2 · Three passes over the whole bundle, and the order matters.** `mirror.py`
reads BigQuery; the other two are offline.

```bash
python okf-review/mirror.py --write        # tier-A cache, from BigQuery
python okf-review/postauthor.py --write    # absolute links, status, back-links
python okf-review/canonicalize.py --write okf-bundle   # always last
```

`canonicalize` is last because every other producer writes non-canonical
frontmatter.

**3 · Assert the bundle is final** ○ — each pass above has a check twin that
writes nothing and exits non-zero, which is the form CI runs. (`mirror --check`
is the exception: it compares against live BigQuery, so CI gets `--selftest`.)

```bash
python okf-review/conformance.py                 # OKF v0.2 §11 + link-form counts
python okf-review/canonicalize.py --check okf-bundle
python okf-review/postauthor.py --check
python okf-review/mirror.py --selftest
python okf-review/check_doc_links.py             # the docs' cross-references
kcmd/node_modules/.bin/bun kcmd/demo/okf/ownership.test.ts   # 38 assertions
kcmd/node_modules/.bin/bun kcmd/demo/okf/drift.test.ts       # 27 assertions
```

**4 · Project** — one command per track. Staging into `.staging/bundle/` happens
inside each push; there is no separate step and no second copy of the bundle on
disk.

```bash
(cd okf-kb-workspace  && ../kcmd/node_modules/.bin/bun ../kcmd/demo/okf/push.ts)
(cd bq-okf-workspace  && ../kcmd/node_modules/.bin/bun ../kcmd/demo/okf/push-track-a.ts)
```

Both pushes are **planners**: they compare first and stage only what differs, so
a second run writes nothing at all. If something other than our last push wrote
to a channel the bundle owns, the push **aborts** rather than overwriting it.

**5 · Differ** — the same comparison as the push planner, without the writing.

```bash
kcmd/node_modules/.bin/bun kcmd/demo/okf/drift.ts    # 0 = no drift, 1 = drift, 2 = error
```

## Scope

This branch is the **mechanism proof** — can an OKF bundle be the source of
truth, with kcmd projecting it into Knowledge Catalog and an agent reading it
back? Enrichment *quality* is deliberately out of scope.

The upstream demo's Cloud Run sync service and its ADK agent application were
**never exercised here** — every run was manual, single-writer, and driven from
the shim. So nothing measured on this branch says anything about either of them,
and no result here should be read as covering them. They are present and
untouched; DESIGN §8.4 argues that the push planner has taken over the sync
service's job, which is an argument to weigh rather than a change already made.

**The finding that should shape expectations:** retrieval, not content, is the
binding constraint. Across 75 runs the score tracked how often the agent *asked*
for metadata, not what the metadata said. Everything here is necessary and none
of it is sufficient — see RESULTS §4.
