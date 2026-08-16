# OKF ⇄ Knowledge Catalog — the bundle is the source of truth

An **OKF v0.2 bundle in git is the system of record** for what a BigQuery
dataset means. Dataplex Knowledge Catalog is a *projection* of it: a push makes
the catalog match the bundle, and a differ reports when the two disagree.

That is the inversion this branch exists to test. The tool underneath —
[`kcmd`](kcmd/) — was built for the opposite direction, and the interesting part
of the result is *why* it was, and what had to change.

**58 concepts · 190 cross-concept links · 82 catalog links · two projection
tracks · a forward differ that exits 0 when the catalog still matches.**

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

| path | what it is |
|---|---|
| `okf-bundle/` | **the source of truth.** Clean OKF v0.2, tool-agnostic, in git |
| `docs/` | the as-built documentation — see above |
| `okf-emitter/`, `okf-author/` | the two producers that write the bundle |
| `okf-review/` | conformance, canonicalisation, the post-authoring pass, the tier-A mirror, and the count-what-landed checks. All have `--check` so CI can assert the bundle is final |
| `okf-agent/` | the Phase 8 evaluation harness (Arm K vs Arm D) |
| `kc-capture/` | a frozen, hash-manifested capture of Knowledge Catalog — reproducible **input** to authoring, never a source of truth |
| `_state/` | tracked evidence: Measurement G, the live-entry probe, the drift baseline |
| `okf-kb-workspace/`, `bq-okf-workspace/` | the two push manifests (Track B, Track A) |
| `kcmd/` | the vendored fork. `src/` is patched (8 defects, upstreamable); `demo/okf/` is ours; `docs/` is Google's and is quoted in DESIGN §9 |

## Running it

Everything runs **from this directory**. The offline checks need no credentials:

```bash
python okf-review/conformance.py                 # OKF v0.2 §11 + link-form counts
python okf-review/canonicalize.py --check okf-bundle
python okf-review/postauthor.py --check
python okf-review/mirror.py --selftest
kcmd/node_modules/.bin/bun kcmd/demo/okf/ownership.test.ts   # 38 assertions
kcmd/node_modules/.bin/bun kcmd/demo/okf/drift.test.ts       # 27 assertions
```

Anything that touches the catalog needs the credential prelude in
**[docs/HANDOFF.md](docs/HANDOFF.md) §2.7** — three different identities are in
play and getting it wrong fails in ways that look like missing IAM. Then:

```bash
(cd okf-kb-workspace  && ../kcmd/node_modules/.bin/bun ../kcmd/demo/okf/push.ts)
(cd bq-okf-workspace  && ../kcmd/node_modules/.bin/bun ../kcmd/demo/okf/push-track-a.ts)
kcmd/node_modules/.bin/bun kcmd/demo/okf/drift.ts    # 0 = no drift, 1 = drift, 2 = error
```

Both pushes are **planners**: they compare first and stage only what differs, so
a second run writes nothing at all. If something other than our last push wrote
to a channel the bundle owns, the push **aborts** rather than overwriting it.

## Scope

This branch is the **mechanism proof** — can an OKF bundle be the source of
truth, with kcmd projecting it into Knowledge Catalog and an agent reading it
back? Enrichment *quality* is deliberately out of scope.

The upstream demo's Cloud Run sync service and its ADK agent application were
never exercised here and have been removed from this branch, so what remains is
the projector and the evidence for it. They are in git history and on `main`.

**The finding that should shape expectations:** retrieval, not content, is the
binding constraint. Across 75 runs the score tracked how often the agent *asked*
for metadata, not what the metadata said. Everything here is necessary and none
of it is sufficient — see RESULTS §4.
