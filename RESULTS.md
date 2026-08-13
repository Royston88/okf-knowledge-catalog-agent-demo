# RESULTS — OKF as a source of truth for Knowledge Catalog

What was asked: **can an OKF bundle be the source of truth, with `kcmd`
projecting it into Knowledge Catalog and an agent reading it back?** Enrichment
*quality* was out of scope. Evidence and raw numbers are in `MEASUREMENTS.md`;
this is the synthesis.

**Short answer: yes, the mechanism works. The cost is almost entirely tooling,
and two of the load-bearing claims people would want to make about it are
false.**

---

## 1. Does the machinery work? — A, B, G

**Yes, end to end.** 53 concepts project into a Dataplex EntryGroup carrying the
`okf` signal aspect and their bodies as `overview` (Track B); the same signal
layer attaches to all 14 ingested `@bigquery` entries (Track A); a pull returns
53/53 with bodies byte-identical to the bundle; and an agent reading the bundle
over MCP answers questions the live catalog cannot.

Three things do **not** survive the round trip, all named precisely in
Measurement A:

- **The `index.md` navigation layer** — 6 files, no frontmatter, no entry name,
  no entry. The bundle's structure has no representation in the catalog.
- **Duplicate tags** — Dataplex stores tags as a label *map*, and a map cannot
  hold a duplicate key.
- **The body, until a fork bug was worked around** — see §3.

**Measurement B is the finding most likely to matter to someone else's
pipeline.** Two capture runs over byte-identical data produced identical
DATA_PROFILE statistics (136/136) but **12 joins where there had been 18** — a
third gone, two direction-flipped, and *every* date→calendar join lost. The
deterministic half of a Knowledge Catalog capture is exactly deterministic; the
LLM-backed half is not, and its instability is large enough that a pipeline
trusting a single relationship scan gets a different semantic model each run.

And reproducible is not the same as correct: **the profile reports 1,201
distinct `account_id` where there are 1,200.** That error propagated into an
agent-authored concept and through two sessions of review, because 1,201 is
plausible. Do not key rules on `distinct_ratio`.

**Measurement G: curated content survives a re-scan if and only if
`userManaged: true` is set** — and survival is *completely uncorrelated* with
the OKF `verified` flag. Two further facts make this sharp:

- **Writing curated content does not set `userManaged`.** The write is accepted,
  nothing warns, and the text is destroyed by the next scan. Silent data loss.
- A protected aspect keeps its **original** job stamp, which is how you detect
  that the scan skipped it rather than that it never ran.

---

## 2. Is OKF-as-source-of-truth worth using? — C, D, F

**Measurement D is the strongest positive.** The OKF v0.2 trust tier —
`verified`, `status`, `stale_after`, none of which the shipped aspect schema
carries — survives projection and pull intact, including record-array
cardinality and order, non-default `status` values, and, importantly,
**absence-as-absence**: the unverified tier does not come back as an empty
array, so "no key = unverified" is a usable distinction rather than an
ambiguity. And **the aspect write is a full replace, not a merge** — a field
deleted from the bundle is deleted from the catalog. That is exactly what
"source of truth" has to mean.

**Measurement C says the round trip is byte-unstable and semantically clean.**
0 of 53 files survive byte-identical; every difference is Python-vs-JS YAML
style. As data: 52/53 frontmatter and 53/53 bodies identical.

**Measurement F says the diff is reviewable — conditionally.** Raw, it is 53/53
files of pure noise. Canonicalised, it is **1** file, and that one is a genuine
loss. But the canonicaliser did not exist and had to be built, its style is a
*choice* between two producers that disagree, and it is a **required
post-authoring step** because `reference_agent` writes non-canonical frontmatter
every time. Reviewability is a property of the tooling around OKF, not of OKF.

---

## 3. What it cost: the tooling, not the model

Every real obstacle was a defect in the projection layer. None was Knowledge
Catalog refusing to store something, and none was OKF being the wrong shape.

**Two fork defects, both worked around in our shim rather than patched:**

1. **The documents layout indexes on `entry.name`, and nothing derives it.**
   Files without an explicit `catalogEntry.name` are skipped silently, so `push`
   reported *"Successfully pushed catalog entries"* over an empty index. This
   was the Phase 5 blocker, and the suspect recorded against it — a required
   path prefix — was **refuted**: `init()` contains no path logic at all.
2. **The overview aspect alias is asymmetric, so pull loses the body.** The pull
   path aliases `dataplex-types.global.overview` → `overview`, while both
   `DocumentsLayout` *and* the fork's own `OkfLayout` promote the body to and
   from the unaliased key. Push works; pull silently returns every concept
   empty. `standard.ts` is the only layout that handles both forms.

Both are worth reporting upstream. Also found: **`push --validate-only` is not a
dry run** — it creates every entry it "validates".

**The pattern worth naming: this codebase's failure mode is the silent plausible
success.** Defect 1 produced a successful push that wrote nothing. Defect 2
produced a successful pull that returned nothing. The same defect, on the read
path, produced a **scored agent arm** that read an empty catalog and lost 1/5.
Three times, the system reported success and the output looked reasonable.
Nothing failed loudly. Every one was caught only by counting something.

---

## 4. Does it help an agent? — Phase 8

**Arm K (OKF bundle over kcmd MCP) 11/15. Arm D (live Knowledge Catalog) 7/15.**
The plan predicted Arm D would win, and warned its win would not be evidence
about OKF. It lost instead, and *that* is not straightforward evidence for OKF
either.

The decisive question is q2 — total balance across accounts, which requires
de-duplicating a double-loaded table. **Arm K 3/3, Arm D 0/3.** The bundle body
states the hazard and supplies the pattern; the generated `descriptions` aspect
does not.

But the mechanism is not "better metadata":

- **7 of Arm D's 15 runs never consulted the catalog at all**, despite having
  semantic search. It went straight to SQL.
- **14 of Arm K's 15 runs called `lookup-entry`, and the single run that did not
  was its single failure on that question.**

Correct answers correlate with **retrieval**, not with the arm.

**And a later measurement sharpened this further.** Track A was extended to
project the concept bodies onto the native `@bigquery` entries — the exact text
that wins Arm K q2 — and Arm D re-run against that enriched catalog scored
**6/15, unchanged**. Because its tool does not return the text: the dataplex
toolbox's `lookup_entry` defaults to `view=2 (FULL)`, and FULL returns required
aspects plus only the **keys** of non-required ones. `overview` is non-required,
so the body is withheld unless the caller asks for `view=4 (ALL)` — 3,619 chars
versus 18,171.

So the claim that survives is: *Arm K's `lookup-entry` returns the whole concept
and Arm D's returns a summary with the prose stripped out.* The two arms were
never reading comparable content, even once both were pointed at the same text.

**Forcing the view confirms it.** A fourth arm (`Dall`) forces `view=4 (ALL)` on
every `lookup_entry` via an ADK `before_tool_callback` — deterministic, not a
prompt request. **q2 goes 0/3 → 2/3, and both successes are exactly the runs
that called the tool; the failure never called it.** Overall 6/15 → 8/15.

That splits the problem into three independent failure points, each needing a
different fix:

1. **Published** — the knowledge must be on the entry (Track A).
2. **Returned** — the default read path must not withhold it (the view).
3. **Requested** — the agent must actually call the tool (tool-surface design).

Fixing exactly one moved the score by two. q1 stayed **0/3 across every D
variant** with the trace `tools=['execute_sql']` every time: the catalog is
never consulted, so nothing about what it returns can matter. **Retrieval, not
content, is now the dominant failure** — and it is the one thing OKF cannot
address.

**And q4 is a genuine negative: both arms 0/3.** Neither channel carries the
zero-fill-cohort hazard, because nobody curated it into the bundle. A curated
bundle defends only against the hazards someone curated into it, and the ceiling
appeared on the first question outside the curated set.

---

## 5. The honest bottom line

**Use OKF as a source of truth if you want the bundle to win.** The full-replace
semantics, the surviving trust tier, and the reviewable canonical diff genuinely
deliver "the file is authoritative, the catalog is a projection." That is a real
capability and it was blocked by tooling, never by Knowledge Catalog.

**Do not claim any of the following. All three are measured false:**

1. *"The OKF trust flag protects content from the pipeline."* It does not.
   `userManaged` does, and it is orthogonal to `verified` (Measurement G).
2. *"OKF round-trips cleanly."* Not byte-wise, not without a canonicaliser you
   build yourself, and not at all for the `index.md` layer or duplicate tags.
3. *"Putting knowledge in the catalog makes an agent use it."* Arm D skipped the
   catalog in half its runs — and when the identical OKF bodies were projected
   onto the very entries it queries, its score did not move, because the
   toolbox's default `lookup_entry` view returns the aspect *keys* and not the
   prose. Availability, retrieval and legibility are three different problems.

**The strongest single argument for the approach** is not any measurement here —
it is that when the projection broke in four different ways, every one was
recoverable by re-pushing the bundle, because the bundle was authoritative and
every consumed channel is live. OKF survives the pipeline by being re-projected,
not by being protected. That is a weaker claim than the trust tier suggests, and
it is the one the evidence supports.

---

## 6. What was not tested

- **Enrichment quality**, explicitly out of scope. Measurement E scored the
  author on 3 hazards in a single non-deterministic run and is not a capability
  measurement.
- **Scale.** 53 concepts, 13 tables, one dataset.
- **Multi-writer conflict.** One bundle, one pusher; full-replace semantics are
  untested against concurrent editors.
- **The `index.md` gap**, left open deliberately — fixing it means either giving
  the files frontmatter or teaching the shim to synthesise directory entries the
  way `OkfLayout` does.
- **Phase 8 at any statistical weight.** n=3, one model, 5 questions; tool use
  varied between identical repeats.
