# HANDOFF — OKF/kcmd mechanism proof

Updated 2026-08-13 at the end of the second session. Everything needed to resume
cold is here. Read this, then `MEASUREMENTS.md` for results and
`okf-emitter/PROVENANCE.md` for the copied-generator story.

- **Branch:** `v6z-okf-projector` in `okf-knowledge-catalog-agent-demo` (a private
  submodule of `agentic-data-cloud-demo`). HEAD `6234a52`.
- **Approved plan:** `/home/user/.claude/plans/glittery-tumbling-kettle.md`
- **Goal:** prove the mechanism — can an OKF bundle be the source of truth, with
  kcmd projecting it into Knowledge Catalog, and an ADK agent reading it back?
  Enrichment *quality* is out of scope.

---

## 0. If you are a scheduled/autonomous run, start here

The human is disconnected and cannot answer questions. Do not block on them.

1. Work the **first unfinished item in §4**. One item per run, done properly,
   beats three done badly.
2. Record the result in `MEASUREMENTS.md`, tick it off in §1 and §4, and
   **commit** — including negative or partial results. A recorded negative is a
   result. Never end a run with an uncommitted working tree.
3. If you get blocked, write the blocker into §3 in the established style
   (symptom → hypotheses ruled out *by measurement* → prime suspect → ways
   forward) and commit that. Then stop; do not thrash.
4. Make reasonable calls on ambiguity and **write down the call you made** rather
   than deferring the whole item.

An hourly cron (`23 * * * *`, durable, auto-expires 7 days from 2026-08-13) is
registered to do exactly this. It only fires while a Claude session is alive and
idle on this workstation — it is a convenience, not a guarantee. The durable
state is git: this branch's commits are the real handoff.

---

## 1. Where things stand

| Phase | State |
|---|---|
| 1 — duplicate dataset | **done.** 13/13 tables, row counts exact, Dataplex ingest immediate |
| 2 — rich KC capture + freeze | **done.** 27 scans, 0 failures. **Measurement B taken** |
| 3 — port shim, extend aspect, EntryGroup | **done.** Smoke test 1 **passed** |
| 4b — `gen_okf` deterministic emitter | **done.** Faithful-copy check passed |
| 4a — `reference_agent` authoring | **done. Measurement E taken** (3/3 hazards) |
| 5 — projection (Track B) | **done.** Blocker resolved; 53 concepts live |
| Measurement A — round-trip loss | **taken.** 3 losses named |
| Measurement C — round-trip fidelity | **taken.** Byte-unstable, semantically clean |
| Measurement D — extended trust tier | **taken. PASS**, all tiers |
| Track A — `okf` aspect onto `@bigquery` entries | **not started** — next task, see §4.1 |
| 6, 7, 8 | not started |
| Measurements F, G | not taken |

The bundle is committed: `okf-bundle/`, 53 concepts + 6 indexes, two provenance
classes (`generate_models/okf` × 39, `reference_agent/gemini-3.5-flash` × 14).

**Track B is live.** EntryGroup `okf_cymbal_v6z` holds 54 entries: 13 `tables/`,
1 `datasets/`, 39 `references/` (13 joins + 26 metrics), plus the auto-created
`okf_cymbal_v6z_entry`. Each concept carries the `okf` signal aspect, the
`generic` aspect, and its markdown body as `overview`.

---

## 2. Environment — the non-obvious parts

These cost real time to discover. Reproduce them exactly.

### 2.1 Credentials: the `gc` wrapper is NOT enough for Python

There is **no** `~/.config/gcloud/admin--royston-dev-8253.json`, so the `gc`
wrapper sets no `GOOGLE_APPLICATION_CREDENTIALS` and Python clients fall back to
ambient ADC = `kenly@google.com`, which has **no roles** on `royston-dev-8253`
(403 `bigquery.jobs.create`).

`admin--kenly-lakehouse-dev-1.json` holds **`admin@kenly.altostrat.com`** user
credentials, and that principal is **`roles/owner` on `royston-dev-8253`**. ADC
files are tied to the principal, not the project, so:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/home/user/.config/gcloud/admin--kenly-lakehouse-dev-1.json
export GOOGLE_CLOUD_QUOTA_PROJECT=royston-dev-8253
```

Verified working for BigQuery jobs, `DataScanServiceClient` and
`CatalogServiceClient` against `royston-dev-8253`. **No IAM was changed and no
service account was created** — keep it that way.

### 2.2 kcmd CLI needs a location it cannot find

`ApiContext.default()` runs `gcloud -q config get-value compute/region`, unset on
this profile → *"Unable to retrieve project, location, or token."*

```bash
export CLOUDSDK_COMPUTE_REGION=us     # per-invocation; mutates no gcloud config
```

The kcmd subprocess also prints `Your active configuration is:
[student-01--qwiklabs-…]`. That is `ApiContext.default()` shelling out to gcloud
and reading the globally active config; it is **noise**, not a routing bug —
identity comes from the ADC file above and the target from `catalog.yaml`'s
`scope:`. Every entry it wrote landed in `royston-dev-8253`, verified by
`list_entries`.

### 2.3 Vertex model availability

`gemini-3.5-flash` is **404 in `us-central1`** (so is `gemini-flash-latest`). It
**is** served at location `global`:

```bash
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_PROJECT=royston-dev-8253
export GOOGLE_CLOUD_LOCATION=global
```

Expect intermittent `429 RESOURCE_EXHAUSTED`; the full 14-concept run lost
`tables/transactions` to one and needed a single-concept backfill. Retry with
backoff, then verify all 13 tables exist before trusting a run.

### 2.4 `push --validate-only` is NOT a dry run in this fork

It **creates entries** and then reports success. Do not reach for it as a safe
probe. (The previous session used it as an auth check; the conclusion held, but
it was writing to the catalog the whole time.)

### 2.5 The venv follows the directory, not the shell

`pyenv` selects the venv from `.python-version` in the *current* directory. A
`cd /tmp/... && python ...` silently gets system Python and dies on
`ModuleNotFoundError: No module named 'yaml'`. Run Python from inside the repo
and pass absolute paths, rather than `cd`-ing to the scratch tree.

### 2.6 Toolchain

| Thing | Where |
|---|---|
| venv | pyenv `agentic-data-cloud-demo` (3.12.7); `pyenv version` must show it |
| upstream clone | `/home/user/knowledge-catalog-upstream` @ `374e0bc` (scratch, gitignored, read-only) |
| `reference_agent` | pip-installed editable from `/home/user/knowledge-catalog-upstream/okf` |
| kcmd build | `npm run build:mcp` → `kcmd/build/ts/tool/tool/main.js` |
| bun | vendored at `kcmd/node_modules/.bin/bun` (not on PATH) |

The demo shim (`kcmd/demo/okf/*.ts`) is run **directly by bun** and needs no
rebuild. Only changes to `kcmd/src/` require `npm run build:mcp`. Nothing in
this work has modified `kcmd/src/` — see §2.8.

### 2.7 Working push / pull incantation

```bash
cd okf-kb-workspace
export GOOGLE_APPLICATION_CREDENTIALS=/home/user/.config/gcloud/admin--kenly-lakehouse-dev-1.json
export CLOUDSDK_COMPUTE_REGION=us
rm -rf catalog .staging && mkdir -p catalog && cp -r ../okf-bundle/. catalog/
OKF_PROJECT=royston-dev-8253 OKF_LOCATION=us OKF_ENTRY_GROUP=okf_cymbal_v6z \
  ../kcmd/node_modules/.bin/bun ../kcmd/demo/okf/push.ts
```

`pull.ts` takes the same env. It writes back under
`catalog/<entryGroup>/<project>/<location>/…` (the `KnowledgeBaseSource.localName`
convention), **not** the bundle's bare paths — so pull into a scratch workspace
and compare, rather than pulling over `catalog/`. Set `OKF_KEEP_STAGING=1` to
retain `.staging/` for inspection.

### 2.8 Rules that still bind

- `bi_modeling_playbook/` is **read-only for this work**. Its generator and spec
  are *copied* into `okf-emitter/`.

  > **The plan's verification item "`git status` clean for `bi_modeling_playbook/`"
  > cannot pass and should not be used.** That path was *already* dirty when this
  > work began, and more files became dirty during it, with content about PRISM
  > judge-429 concurrency tuning that is unrelated to this work. Nothing here
  > writes outside `okf-knowledge-catalog-agent-demo/`, `/tmp` and the venv, so
  > the cause is a parallel session or hand-editing.
  >
  > **The usable check is:** no *new* modification attributable to this work.
  > **Re-verified 2026-08-13 and passing:**
  > `git diff bi_modeling_playbook/engine/generate_models.py | grep -ci okf` → **0**,
  > and `okf-emitter/generate_models.py`, its source, and the hash recorded in
  > `okf-emitter/PROVENANCE.md` are all
  > `c40b1d61fb673d78c08aa1faa4ddeb128aa72d1744d410fe1246d1841f80d8ce`.
  > Re-run both on resume.
- **The fork's `kcmd/src/` is untouched and should stay that way.** Every fix so
  far has landed in `kcmd/demo/okf/` (our shim). Two genuine fork defects were
  found and worked around rather than patched — see §3. If you do patch `src/`,
  say so loudly in the commit and remember it needs `npm run build:mcp`.
- Never push to Royston's `main` — it is **unprotected**, so an accidental push
  would land. Work stays on `v6z-okf-projector`. Push access is confirmed
  (`kenly-ldk`, `push: true`), so `git push -u origin v6z-okf-projector` is fine
  when there is something worth sharing.
- The repo is **private**; anything committed inherits that.
- Do not touch `lakehouse_dev_cymbal_bank_demo` or its 3 enriched entries — the
  final verification step is that their `updateTime` is unchanged.

---

## 3. Fork defects found (worked around, not patched)

Both are upstream bugs in Royston's fork, both are worth reporting to him, and
neither is a property of OKF. Full evidence in `MEASUREMENTS.md`.

**(1) The documents layout indexes on `entry.name` and nothing derives it.**
`DocumentsLayout.init()` does `if (entry && entry.name) index.set(…)`, while
`parseMarkdown` builds the entry as `metadata.catalogEntry ?? {}` and never
derives a name from the file path. Any file without an explicit
`catalogEntry.name` is silently skipped, and `push` then reports success over an
empty index. **This was the Phase 5 blocker.** Worked around by having `push.ts`
stamp a path-derived id — the same derivation the fork's own
`OkfLayout.deriveEntryName` uses.

> The blocker's recorded prime suspect — that the indexer required a
> `catalog/<namespace>/<project>/<location>/` path prefix — is **refuted**.
> `init()` contains no path logic whatsoever. That prefix is a pull-side
> `localName` convention, and `serviceName` already strips it only when present.

**(2) The overview aspect alias is asymmetric, so pull loses the body.**
`ResourceAlias` maps `dataplex-types.global.overview` → the short alias
`overview`, and `toLocalEntry` applies it to every aspect key on the way in. But
`DocumentsLayout` — *and `OkfLayout`* — promote the markdown body to/from the
**unaliased** constant. Push works, pull silently returns every concept with an
empty body. `standard.ts` is the only layout that handles both forms. Worked
around in `fromStaging`.

**No current blocker.** §4.1 is the next task.

---

## 4. Remaining work

In order. Definitions are in the plan; these are the deltas.

### 4.1 Track A projection — NEXT

The `okf` aspect onto the 13 `@bigquery` entries. Smoke test 1 (Phase 3) already
proved the write is accepted and reads back intact, and Measurement D proved the
extended fields survive. What is missing is the mapper and the run:

- map `tables/<t>.md` → the `@bigquery` entry name for that table in
  `cymbal_bank_v6z_scaffold_demo_copy`;
- handle the **project-ID-in / project-NUMBER-out** key asymmetry (write
  `royston-dev-8253.us.okf`, read back `404799090046.us.okf`) — `fromStaging`
  already has the suffix-matching helper to copy;
- these are *ingested* entries, so `manifest.source.ingestedEntries` is true and
  no synthetic index entries may be created (see `OkfLayout.init`).

Note this is the projection that actually matters for the agent story: Track B's
EntryGroup holds abstract concepts, but an analyst's tooling looks at the
BigQuery entries.

### 4.2 Phase 6 — review and sign-off

Measurement F (is the diff reviewable), `join_triage.yaml` against JT1–JT4,
sign-off `verified: [{by: human:<id>}]` on ~half the concepts, flag off on the
rest (that split is the control — **do not flag everything**).

> **Measurement C changes how F must be run.** A raw `git diff` of a pulled
> bundle is ~100% YAML-serializer churn (0/53 files byte-identical, all
> semantically clean bar one). Canonically format the bundle first — re-emit
> through the same writer after each pull, or pin a shared YAML style — or F
> will be measuring noise. The mechanics of that formatter are unbuilt.

### 4.3 Phase 7 — re-scan and Measurement G

Re-run the Phase 2 capture; judge on the `<!-- curated:v1 -->` sentinel,
**never** prose similarity: Measurement B already showed the generator rewrites
untouched output. Measurement B's drift floor (a third of joins vanished and two
flipped direction between two runs over identical data) is what G must clear —
a changed link is **not** evidence the trust flag failed.

### 4.4 Phase 8 — the ADK agent

Arm K (kcmd MCP over the bundle) vs Arm D (KC MCP live). Not a contest; Arm D is
expected to win and that is not evidence about OKF. Report the search-capability
confound.

### 4.5 `RESULTS.md`

A/B/G answer *does the machinery work*; C/D/F answer *is OKF-as-source-of-truth
worth using*. State a negative plainly if that is what the measurements show.

Material already in hand for it:

- The mechanism **works**: 53 concepts project, the signal layer lands, the
  extended v0.2 trust tier survives, and the aspect write is a **full replace**
  so the bundle genuinely wins.
- The cost is **tooling, not model**: two fork defects had to be worked around
  before anything landed at all, and the round trip is not byte-stable.
- Two things do **not** survive: the `index.md` navigation layer (no
  frontmatter → no entry) and duplicate tags (Dataplex stores tags as a label
  *map*).

### Open items carried forward

- **The two producers disagree on dedup direction.** Spec says
  `order_by: load_batch_id` (ascending, first batch wins); the agent wrote
  `ORDER BY load_batch_id DESC` (latest wins). Both are in the bundle. Resolve at
  sign-off, and record which won and why.
- **Generated SQL invents columns.** `c.first_name`, `c.last_name`, `c.email` in
  `payments.md` and `wire_transfers.md`; `customers` has none of them. Recorded,
  **not patched** — patching corrupts Measurement F.
- **The `index.md` layer has no projection.** Either give the 6 files
  frontmatter, or teach the shim to synthesize directory entries the way
  `OkfLayout` does. Decide at Phase 6; it affects what F reviews.
- **`kcmd` `package.json` "exports"** points at `./build/ts/kcmd/index.js`, which
  this fork does not build (real path `./build/ts/tool/libts/index.js`). A bare
  `import 'kcmd'` fails; `demo/okf/config.ts` works around it.

---

## 5. GCP resources created (for cleanup or reuse)

All in `royston-dev-8253`. Nothing else in the project was modified.

| Kind | Name |
|---|---|
| BigQuery dataset | `cymbal_bank_v6z_scaffold_demo_copy` (US, 13 tables) |
| Dataplex EntryGroup | `okf_cymbal_v6z` (location `us`) — **now holds 54 entries** |
| Dataplex AspectType | `okf` (location `us`) — extended with `verified`/`status`/`stale_after` |
| DataScans (27, `us-central1`) | `kc-prof-v6z-scaffold-copy-*` (13), `kc-doc-v6z-scaffold-copy-*` (13), `kc-rel-v6z-scaffold-copy` (1) |

The Phase 3 smoke-test aspect written to `…/tables/accounts` **was deleted**;
that entry is clean. The Measurement D trust-tier injections were **reverted** by
re-pushing the clean bundle, and the revert was verified against the live
entries.

---

## 6. File map on the branch

```
okf-bundle/            THE SOURCE OF TRUTH — 53 concepts, 6 indexes
  datasets/ tables/      14 concepts, generated.by reference_agent/gemini-3.5-flash
  references/joins/      13 concepts, generated.by generate_models/okf
  references/metrics/    26 concepts, generated.by generate_models/okf
kc-capture/            frozen rich KC snapshot (profile/, insights/, relationships.json)
okf-emitter/           copied generator + spec + gen_okf.py + PROVENANCE.md
okf-author/            author_bundle.py — KCBigQuerySource (profile -> the author)
kcmd/demo/okf/         ported shim: okf.ts, config.ts, push.ts, pull.ts, setup.ts,
                       okf-aspect.json (extended). ALL our fixes live here.
kcmd/src/              the fork, UNMODIFIED. Two known defects, see §3.
okf-kb-workspace/      Track B workspace (catalog.yaml written by setup.ts)
MEASUREMENTS.md        B, E, A, C, D, the Phase 5 resolution, the original blocker
HANDOFF.md             this file
```
