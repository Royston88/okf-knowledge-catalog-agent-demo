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

**Eight defects now, and the last two are a different kind.** 1–6 are plain
bugs. **7** — `_fixEntry` rebuilt every aspect as `{aspectType, data}` and threw
away `createTime`, `updateTime` and `aspectSource`, none of which the `Aspect`
interface declared — and **8** — `getEntry` could express `BASIC` and `CUSTOM`
and had no way to ask for `ALL`, so a client restricted to it can never observe
an aspect it did not already expect — are not really bugs. They are consequences
of §7's finding: a tool that never got its comparison layer built has no reason
to keep the evidence for comparison, or to be able to see what it did not
predict. Both are fixed and both are small.

Two of the six also turn out to be **unreachable from kcmd's own workflow** (1
and 4) and only bite a hand-authored bundle, while 2 breaks kcmd's *own* primary
verb. Splitting them that way matters for what to lead with upstream. And
defect 6's page boundary is not the theoretical concern it looked like: it is
reachable at **ten** links, and 2 of 13 table entries already cross it.

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

Two further interventions followed — the projector took ownership of
`descriptions` and `queries` as well (66 column descriptions, 37 query
patterns, `userManaged: true`, verified to survive a re-scan) — and the agent
score did not move. Pooled over 75 D-family runs the pattern is unambiguous:

```
score tracks the RETRIEVAL rate, not the content
  Arm K      11/15 correct,  lookup called 14/15
  D family  6-8/15 correct,  lookup called 1-5/15

on q1+q2, the questions only the catalog can settle:
  called lookup_entry:      2 correct /  6   (33%)
  did NOT call:             1 correct / 24   ( 4%)
```

**Retrieval, not content, is the dominant failure** — and it is the one thing
OKF cannot address. Three consecutive improvements to what the catalog holds
and how it is read produced no measurable agent gain, because the agent does not
ask in 24 of 30 attempts on the questions that need it.

**q4 was 0/3 on both arms, and the reason is not what it first looked like.**
The hazard *is* curated — `metrics/accounts__avg_txns_per_account` says
"including accounts with zero transactions" and gives numerator and
denominator. Arm K called `lookup-entry` on all three reps and never fetched
it; no response in any run mentions a metric concept. The knowledge was
present, addressable, and unreached. **The ceiling is not what someone
curated — it is what is reachable from where the agent starts.**

---

## 5. The honest bottom line

**Use OKF as a source of truth if you want the bundle to win.** The full-replace
semantics, the surviving trust tier, and the reviewable canonical diff genuinely
deliver "the file is authoritative, the catalog is a projection." That is a real
capability and it was blocked by tooling, never by Knowledge Catalog.

**And "the bundle wins" is best scoped, not absolute.** Aspects divide into
three tiers: OKF-native (`okf`) and uncontested platform-native (`overview`) are
always bundle-owned, while *contested* platform-native aspects (`descriptions`,
`queries` — the ones a scan also writes) are owned **only where a human has
signed off**. Claiming a contested aspect means freezing it, and freezing
unreviewed generated content is worse than letting the platform keep refreshing
it. Gating on `verified` also closes coverage gaps for free: released tables get
their undocumented columns filled by the scan.

**Do not claim any of the following. All three are measured false:**

1. *"The OKF trust flag protects content from the pipeline."* **Not by itself.**
   Knowledge Catalog does not couple them at all — Measurement G showed a
   `verified` concept with `userManaged: false` destroyed by a re-scan. The
   projector now *makes* the coupling, computing `userManaged` from `verified`
   at push time, so the flag does confer protection **as a matter of our
   projection policy, not platform behaviour**. Anyone reading the bundle
   without that projector should not assume it.
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
- **Scale.** 58 concepts, 13 tables, one dataset.
- **A real concurrent scan.** ~~Multi-writer conflict. One bundle, one pusher;
  full-replace semantics are untested against concurrent editors.~~ **Partly
  closed** — see §7. The *mechanism* is built and verified against a synthetic
  out-of-band edit; what has not happened is a live DATA_DOCUMENTATION run since
  the differ landed.
- ~~**The `index.md` gap**~~ **Closed.** It was **documents-layout only**:
  `OkfLayout` already synthesises a directory entry per folder and regenerates
  the listings in `finalize()`. Switching the staged tree to `layout: okf` closed
  it using kcmd's own code — 7 index entries, live. Recording it as a gap in the
  system was wrong; it was a gap in the layout we happened to be using.
- **The effect of the `# Related concepts` back-links on the score.** They are
  aimed squarely at the reachability failure §4 identifies, and **no eval has
  been re-run since they landed.**
- **Phase 8 at any statistical weight.** n=3, one model, 5 questions; tool use
  varied between identical repeats.

---

## 7. Multi-writer, drift, and the direction of authority — corrected

Three claims in the sections above were investigated further and did not
survive. They are corrected here rather than edited away, because two of them
were quoted forward into a plan.

**"kcmd is remote-authoritative by design" — false.** Its own `concept.md` tenet
says the code artifacts "should be amenable to **serving as authoring and
management source of truth**", and `spec.md` §3.3 specifies fail-fast conflict
handling with a force override, §3.7 a `.catalog.state` checksum file, §3.8
deletion intent. **None of it is implemented** — zero occurrences of
checksum/state/etag in `kcmd/src`, two conflict TODOs, and `force` plumbed from
the CLI into an options field that nothing reads. kcmd aims where we aim; it is
remote-authoritative because the version-control half of its own spec was never
built. That is a missing layer, not a philosophical difference, and it changes
the gap from something to work around into something to build.

**"v0.1's stash beats us on inspecting everything in the catalog" — no longer
true.** The trade was real: the stash carried every aspect while we carried four
channels. The mirrored tier gives the stash's coverage in **OKF-native,
addressable form** — a `# Schema` table, a `# Data characteristics` section —
where every value is readable and individually diffable rather than buried in a
serialized entry. We get v0.1's coverage and our own legibility.

**"Multi-writer conflict is untested" — the mechanism now exists and works.**
The DATA_DOCUMENTATION scan *is* the concurrent editor, and `drift.ts` makes it
observable for the first time. Verified end to end against an out-of-band
`modifyEntry`: the right concept, the right channel, attributed to a third party
from the server's own clock, the push **aborted** rather than overwriting, and
`--force` repaired it.

The nuance the report encodes, and the reason it is two verdicts rather than
one: for an **unverified** concept a moved `descriptions` timestamp is the system
working as designed — `userManaged: false`, the scan is supposed to refresh it —
while for a **verified** one it is an ownership failure. Same signal, opposite
meaning, decided by nothing but the flag.

This rests on a measurement that was not expected: **Dataplex's per-aspect
`updateTime` is content-addressed by the server.** 14 `modifyEntry` calls
carrying byte-identical data moved the entry-level timestamp on all 14 and the
aspect-level timestamp on **0 of 241**. So "which channel changed, and was it
us" is answerable from a value neither we nor kcmd can write — `toServiceEntry`
never sends it. That is strictly better evidence than the client-side checksums
kcmd's own spec proposes, and it is why this repo has no content hash.

**One thing got worse, and it is worth saying plainly.** Running an *unmodified*
kcmd against a workspace that has links is **destructive to the link layer** —
measured: one pristine push deleted the probe link, because an undeclared
`entryLinks:` makes the reconciler's lookup unfiltered. The interop claim in §1
is scoped to **entries and aspects**.
