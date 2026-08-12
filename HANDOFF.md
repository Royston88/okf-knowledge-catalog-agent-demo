# HANDOFF — OKF/kcmd mechanism proof

Written 2026-08-12 at the end of the first working session. Everything needed to
resume cold is here. Read this, then `MEASUREMENTS.md` for results and
`okf-emitter/PROVENANCE.md` for the copied-generator story.

- **Branch:** `v6z-okf-projector` in `okf-knowledge-catalog-agent-demo` (a private
  submodule of `agentic-data-cloud-demo`). 2 commits, `a0ae15a` is HEAD.
- **Approved plan:** `/home/user/.claude/plans/glittery-tumbling-kettle.md`
- **Goal:** prove the mechanism — can an OKF bundle be the source of truth, with
  kcmd projecting it into Knowledge Catalog, and an ADK agent reading it back?
  Enrichment *quality* is out of scope.

---

## 1. Where things stand

| Phase | State |
|---|---|
| 1 — duplicate dataset | **done.** 13/13 tables, row counts exact, Dataplex ingest immediate |
| 2 — rich KC capture + freeze | **done.** 27 scans, 0 failures. **Measurement B taken** |
| 3 — port shim, extend aspect, EntryGroup | **done.** Smoke test 1 **passed** |
| 4b — `gen_okf` deterministic emitter | **done.** Faithful-copy check passed |
| 4a — `reference_agent` authoring | **done. Measurement E taken** (3/3 hazards) |
| 5 — projection | **BLOCKED — see §3.** This is the next task |
| 6, 7, 8 | not started; all downstream of §3 |
| Measurements A, C, D, F, G | **not taken**; all downstream of §3 |

The bundle exists and is committed: `okf-bundle/`, 53 concepts + 6 indexes, two
provenance classes (`generate_models/okf` × 39, `reference_agent/gemini-3.5-flash`
× 14).

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

### 2.4 Toolchain

| Thing | Where |
|---|---|
| venv | pyenv `agentic-data-cloud-demo` (3.12.7); `pyenv version` must show it |
| upstream clone | `/home/user/knowledge-catalog-upstream` @ `374e0bc` (scratch, gitignored, read-only) |
| `reference_agent` | pip-installed editable from `/home/user/knowledge-catalog-upstream/okf` |
| kcmd build | `npm run build:mcp` → `kcmd/build/ts/tool/tool/main.js` |
| bun | vendored at `kcmd/node_modules/.bin/bun` (not on PATH) |

### 2.5 Rules that still bind

- `bi_modeling_playbook/` is **read-only for this work**. Its generator and spec
  are *copied* into `okf-emitter/`.

  > **The plan's verification item "`git status` clean for `bi_modeling_playbook/`"
  > cannot pass and should not be used.** That path was *already* dirty when this
  > session began (`generate_models.py`, `archive/relay_audit.py`,
  > `docs/STRICT_BLIND_ASBUILT.md`, `tests/test_relay_audit.py`), and five more
  > files became dirty *during* the session — `scaffold/run_config.py`,
  > `scaffold/examples/run_config.example.yaml`,
  > `scaffold/tests/test_bundle_assembly.py`, `specs/SPEC_REFERENCE_BLIND.md`,
  > `tuning/hill_climb.py` — with content about PRISM judge-429 concurrency
  > tuning that is unrelated to this work. Nothing in this session writes outside
  > `okf-knowledge-catalog-agent-demo/`, `/tmp`, and the venv, so the likely cause
  > is a parallel session or hand-editing.
  >
  > **The usable check is:** no *new* modification attributable to this work.
  > Concretely — `git diff bi_modeling_playbook/engine/generate_models.py` must
  > contain nothing about OKF, and `okf-emitter/generate_models.py` must stay
  > byte-identical to its source (`sha256` in `okf-emitter/PROVENANCE.md`).
  > Re-check that hash on resume; if it has drifted, the source moved under us and
  > the faithful-copy check needs re-running.
- Never push to Royston's `main` — it is **unprotected**, so an accidental push
  would land. Work stays on `v6z-okf-projector`. Push access is confirmed
  (`kenly-ldk`, `push: true`), so a `git push -u origin v6z-okf-projector` is
  fine when there is something worth sharing.
- The repo is **private**; anything committed inherits that.
- Do not touch `lakehouse_dev_cymbal_bank_demo` or its 3 enriched entries — the
  final verification step is that their `updateTime` is unchanged.

---

## 3. THE BLOCKER — start here

`kcmd push` prints **"Successfully pushed catalog entries"** and creates nothing.
After two real pushes, EntryGroup `okf_cymbal_v6z` contains only its own
auto-created `okf_cymbal_v6z_entry`.

**Isolated to `DocumentsLayout.init()`** in
`kcmd/src/libts/layouts/documents.ts`: it globs **59** files and populates an
index of **0**.

### Ruled out, each by measurement — do not re-litigate

| Hypothesis | Evidence against |
|---|---|
| auth / permissions | `push --validate-only` succeeds; same creds write aspects directly |
| missing catalog location | fixed via `CLOUDSDK_COMPUTE_REGION=us`; error is gone |
| missing Dataplex entry type | fixed in `toStaging` (`type: dataplex-types.global.generic`); still 0 |
| frontmatter-less `index.md` aborting the scan | deleting all 6 leaves `listEntries()` at 0 |
| glob not matching | `glob('**/*.md',{cwd:'catalog'})` returns **59** standalone |
| `init()` never running | `CatalogSnapshot.fromPath` awaits `_layout.init()` (`snapshot.ts:97`), no throw |

### Prime suspect

Royston's README documents the Markdown layout as
`catalog/<namespace>/<project>/<location>/<page>.md`, and `sources/kb.ts:63`
builds local paths as `${namespace}/${project}/${location}/${entryId}`. Upstream's
OKF demo writes **bare** paths (`catalog/tables/accounts.md`). If this fork's
indexer requires the three-segment prefix, every OKF-shaped path fails to index —
which matches the symptom exactly.

### Three ways forward

- **(a) Path-shape adapter — recommended, ~10 lines.** Have `push.ts` stage under
  `catalog/okf_cymbal_v6z/royston-dev-8253/us/<concept path>.md` and `pull.ts`
  strip that prefix on the way back. Cheapest test of the suspect.
- **(b) Instrument `documents.ts` lines 54-90** — print why each globbed path is
  dropped. Definitive, slower, and tells you the real rule rather than a guess.
- **(c) Drop Track B's EntryGroup entirely** and project only onto `@bigquery`
  entries, which smoke test 1 already proved works. Loses abstract concepts
  (joins/metrics as entries) but unblocks everything else immediately.

Reproduce the failure:

```bash
cd okf-kb-workspace
export GOOGLE_APPLICATION_CREDENTIALS=/home/user/.config/gcloud/admin--kenly-lakehouse-dev-1.json
export CLOUDSDK_COMPUTE_REGION=us
rm -rf catalog && mkdir -p catalog && cp -r ../okf-bundle/. catalog/
OKF_KEEP_STAGING=1 OKF_PROJECT=royston-dev-8253 OKF_LOCATION=us OKF_ENTRY_GROUP=okf_cymbal_v6z \
  gc admin--royston-dev-8253 ../kcmd/node_modules/.bin/bun ../kcmd/demo/okf/push.ts
# then inspect .staging/ and run listEntries() against it
```

---

## 4. Remaining work after the blocker

In order. Definitions are in the plan; these are the deltas.

1. **Measurement A — clean-OKF round-trip loss.** `reference_agent` writes files
   with no `x-kcmd`, and `okf.ts` warns such files "load lossily". Project → pull
   → diff against `okf-bundle/`; name what is lost field by field.
2. **Measurement C — round-trip fidelity.** No-op `push` → `pull` → `git diff`.
   Empty is the pass. Classify any churn benign-vs-fidelity-breaking.
3. **Measurement D — extended trust tier survives.** `verified`, `status`,
   `stale_after` through the custom aspect and back. Tests our schema extension.
4. **Track A projection.** The `okf` aspect onto the 13 `@bigquery` entries.
   Smoke test 1 proved the write works; needs a mapper from `tables/<t>.md` to the
   BQ entry name, plus the project-ID-in/project-NUMBER-out key asymmetry.
5. **Phase 6** — Measurement F (is the diff reviewable), `join_triage.yaml`
   against JT1-JT4, sign-off `verified: [{by: human:<id>}]` on ~half the concepts,
   flag off on the rest (that split is the control — do not flag everything).
6. **Phase 7** — re-run the Phase 2 capture; Measurement G. Judge on the
   `<!-- curated:v1 -->` sentinel, **never** prose similarity: Measurement B
   already showed the generator rewrites untouched output.
7. **Phase 8** — ADK agent, Arm K (kcmd MCP over the bundle) vs Arm D (KC MCP
   live). Not a contest; Arm D is expected to win and that is not evidence about
   OKF. Report the search-capability confound.
8. **`RESULTS.md`** — A/B/G answer *does the machinery work*; C/D/F answer *is
   OKF-as-source-of-truth worth using*. State a negative plainly if that is what
   the measurements show.

### Open items carried forward

- **The two producers disagree on dedup direction.** Spec says
  `order_by: load_batch_id` (ascending, first batch wins); the agent wrote
  `ORDER BY load_batch_id DESC` (latest wins). Both are in the bundle. Resolve at
  sign-off, and record which won and why.
- **Generated SQL invents columns.** `c.first_name`, `c.last_name`, `c.email` in
  `payments.md` and `wire_transfers.md`; `customers` has none of them. Recorded,
  **not patched** — patching corrupts Measurement F.
- **`kcmd` `package.json` "exports"** points at `./build/ts/kcmd/index.js`, which
  this fork does not build (real path `./build/ts/tool/libts/index.js`). A bare
  `import 'kcmd'` fails; `demo/okf/config.ts` works around it.

---

## 5. GCP resources created (for cleanup or reuse)

All in `royston-dev-8253`. Nothing else in the project was modified.

| Kind | Name |
|---|---|
| BigQuery dataset | `cymbal_bank_v6z_scaffold_demo_copy` (US, 13 tables) |
| Dataplex EntryGroup | `okf_cymbal_v6z` (location `us`) |
| Dataplex AspectType | `okf` (location `us`) — extended with `verified`/`status`/`stale_after` |
| DataScans (27, `us-central1`) | `kc-prof-v6z-scaffold-copy-*` (13), `kc-doc-v6z-scaffold-copy-*` (13), `kc-rel-v6z-scaffold-copy` (1) |

The Phase 3 smoke-test aspect written to `…/tables/accounts` **was deleted**;
that entry is clean.

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
                       okf-aspect.json (extended)
okf-kb-workspace/      Track B workspace (catalog.yaml written by setup.ts)
MEASUREMENTS.md        running log of B and E, plus the Phase 5 blocker
HANDOFF.md             this file
```
