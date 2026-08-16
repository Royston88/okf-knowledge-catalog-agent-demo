# RESULTS — OKF as a source of truth for Knowledge Catalog

What was asked: **can an OKF bundle be the source of truth, with `kcmd`
projecting it into Knowledge Catalog and an agent reading it back?** Enrichment
*quality* was out of scope.

**Short answer: yes, the mechanism works. The cost is almost entirely tooling,
and several of the load-bearing claims people would want to make about it are
false.**

> **This file argues; [MEASUREMENTS.md](MEASUREMENTS.md) evidences.** Every claim
> below links to the entry that establishes it, and quotes only the one figure
> that carries the argument. That division is deliberate and the two files must
> not be merged: MEASUREMENTS is **append-only** — corrected by later entries,
> never edited, which is what makes it usable as a record — while this file is
> **revised in place**, as §7 shows. Measured across the branch, MEASUREMENTS
> deletes 1% of what it inserts and this file 8%.

---

## 1. Does the machinery work? — A, B, G

**Yes, end to end.** 44 concepts plus 7 synthesised directory entries project
into a Dataplex EntryGroup carrying the `okf` signal aspect and their bodies as
`overview` (Track B); four aspects attach to all 14 ingested `@bigquery` entries
(Track A); the catalog can be shown to still match the bundle on demand; and an
agent reading the bundle over MCP answers questions the live catalog cannot.

Two things do **not** survive the projection
([Measurement A](MEASUREMENTS.md#measurement-a-clean-okf-round-trip-loss)):

- **Duplicate tags** — Dataplex stores tags as a label *map*, and a map cannot
  hold a duplicate key.
- **The body**, until fork defect 2 was fixed — see §3.

*(The third, the `index.md` navigation layer, is closed. See §6.)*

**[Measurement B](MEASUREMENTS.md#phase-2-rich-kc-capture) is the finding most
likely to matter to someone else's pipeline.** Two capture runs over
byte-identical data produced identical DATA_PROFILE statistics but **12 joins
where there had been 18** — a third gone, two direction-flipped, and *every*
date→calendar join lost. The deterministic half of a Knowledge Catalog capture
is exactly deterministic; the LLM-backed half is not, and its instability is
large enough that a pipeline trusting a single relationship scan gets a
different semantic model each run.

And reproducible is not the same as correct: **the profile reports 1,201 distinct
`account_id` where there are
1,200**([evidence](MEASUREMENTS.md#the-dedup-disagreement-dissolves-and-the-profile-is-off-by-one)).
That error propagated into an agent-authored concept and through two sessions of
review, because 1,201 is plausible. Do not key rules on `distinct_ratio`. It is
also why the mirrored tier computes its numbers from BigQuery and not from the
catalog's profile (§7).

**[Measurement G](MEASUREMENTS.md#phase-7-measurement-g-curated-content-survives-iff-usermanaged-is-set):
curated content survives a re-scan if and only if `userManaged: true` is set** —
and survival is *completely uncorrelated* with the OKF `verified` flag. Two
further facts make this sharp:

- **Writing curated content does not set `userManaged`.** The write is accepted,
  nothing warns, and the text is destroyed by the next scan. Silent data loss.
- A protected aspect keeps its **original** job stamp, which is how you detect
  that the scan skipped it rather than that it never ran.

---

## 2. Is OKF-as-source-of-truth worth using? — C, D, F

**[Measurement D](MEASUREMENTS.md#measurement-d-the-extended-trust-tier-survives-projection-pass)
is the strongest positive.** The OKF v0.2 trust tier — `verified`, `status`,
`stale_after`, none of which the shipped aspect schema carries — survives
projection intact, including record-array cardinality and order, non-default
`status` values, and, importantly, **absence-as-absence**: the unverified tier
does not come back as an empty array, so "no key = unverified" is a usable
distinction rather than an ambiguity.

**And the aspect write is a full replace, not a merge** — a field deleted from
the bundle is deleted from the catalog. That is exactly what "source of truth"
has to mean, and it is the whole argument for keeping the bundle authoritative.
The corollary is worth stating with it: **the projection cannot be used to
*augment* an entry incrementally.** Anything not in the bundle at push time is
gone.

**[Measurement C](MEASUREMENTS.md#measurement-c-round-trip-fidelity-byte-unstable-semantically-clean):
the round trip is byte-unstable and semantically clean.** Not one file survives
byte-identical; every difference is Python-vs-JS YAML style. Semantically it is
clean.

**[Measurement F](MEASUREMENTS.md#measurement-f-is-the-projection-diff-reviewable-yes-but-only-with-a-tool-that-did-not-exist):
the diff is reviewable — conditionally.** Raw, it is **100% noise**.
Canonicalised, it is **one** file, and that one is a genuine loss. But the
canonicaliser did not exist and had to be built, its style is a *choice* between
two producers that disagree, and it is a **required post-authoring step**.
Reviewability is a property of the tooling around OKF, not of OKF — which is why
it is counted as a cost in §3 and not as a win here.

---

## 3. What it cost: the tooling, not the model

Every real obstacle was a defect in the projection layer. **None was Knowledge
Catalog refusing to store something, and none was OKF being the wrong shape.**

**Eight kcmd defects**
([1–5](MEASUREMENTS.md#five-kcmd-defects-fixed-in-kcmdsrc-each-verified),
[6](MEASUREMENTS.md#spec-coverage-closed-three-new-concept-types-and-a-sixth-kcmd-defect),
[7–8](MEASUREMENTS.md#the-return-leg-a-forward-differ-and-the-premise-it-was-built-on-turns-out-to-be-wrong)),
and they are not all the same kind of thing:

| | defect | why it matters |
|---|---|---|
| **1** | the documents layout indexes on a name nothing derives, so `push` reported success over an **empty index** | the original blocker. **Unreachable from kcmd's own workflow** — it only bites a hand-authored bundle |
| **2** | the overview alias is asymmetric, so **pull returns every concept empty** | breaks kcmd's *own* primary verb. Lead with this one upstream |
| **3** | `--validate-only` is not a dry run — it **creates every entry it "validates"** | plain bug |
| **4** | link reconciliation runs unguarded, **deleting every link the bundle does not describe** | also unreachable from kcmd's own workflow, and destructive when it does fire |
| **5** | `package.json` `exports` points at a path the fork does not build | plain bug |
| **6** | `lookupEntryLinks` returns only the first page | **reachable at ten links**, and 2 of 13 table entries already cross it ([count](MEASUREMENTS.md#the-invariants-re-established-on-the-real-catalog-after-the-layout-okf-switch)) |
| **7** | `_fixEntry` discards every aspect's `createTime`, `updateTime` and `aspectSource` | **not really a bug** — see below |
| **8** | `getEntry` can ask for `BASIC` or `CUSTOM` and has **no way to ask for `ALL`**, so a client can never observe an aspect it did not already expect | same |

**7 and 8 are consequences of §7's finding**, not oversights: a tool whose
comparison layer was never built has no reason to keep the evidence for
comparison, or to be able to see what it did not predict.

**Two costs that are ours, not kcmd's, and belong in this column:**

- **The review surface had to be built.** Out of the box the diff is 100% noise;
  it only became reviewable because a canonicaliser was written for it, and that
  canonicaliser is a *required* step after every authoring pass rather than a
  tidy-up. Counting it as a win for OKF would be counting our own tooling as the
  format's property.
- **Our own shim carried six defects**, one of them destructive: `gen_okf.py`
  **deleted `verified` on every run**, silently removing the human sign-off from
  20 concepts, latent for two days
  ([evidence](MEASUREMENTS.md#closing-the-two-spec-gaps-okf-names-and-a-destructive-emitter-defect-found-doing-it)).

**The pattern worth naming: this codebase's failure mode is the silent plausible
success.** A push that wrote nothing, a pull that returned nothing, a
validate-only that wrote everything, a reconciliation that deleted a scan's
relationship layer, a paginated lookup that saw a third of the data, an emitter
that deleted the sign-off — every one reported success. Not one threw.

And it is not a solved problem. While writing defect 6 up, the first version of
the script that counts links **did not paginate either**, and reported 47 where
there are 58. Every one of these was caught only by counting something.

---

## 4. Does it help an agent? — Phase 8

**Arm K (OKF bundle over kcmd MCP) 11/15. Arm D (live Knowledge Catalog) 7/15**
([full runs](MEASUREMENTS.md#phase-8-arm-k-okf-bundle-via-kcmd-mcp-vs-arm-d-knowledge-catalog-live)).
The plan predicted Arm D would win and warned that its win would not be evidence
about OKF. It lost instead, and *that* is not straightforward evidence for OKF
either.

The decisive question is q2 — total balance across a double-loaded table.
**Arm K 3/3, Arm D 0/3.** The bundle body states the hazard and supplies the
pattern; the generated `descriptions` aspect does not.

But the mechanism is not "better metadata". **7 of Arm D's 15 runs never
consulted the catalog at all**, despite having semantic search, while **14 of
Arm K's 15 called `lookup-entry` — and the single run that did not was its
single failure on that question.** Correct answers correlate with **retrieval**,
not with the arm.

**Three later interventions sharpened this and none of them moved the score.**
The concept bodies were projected onto the native `@bigquery` entries — the exact
text that wins Arm K q2 — and Arm D scored **unchanged**
([why](MEASUREMENTS.md#track-ab-de-duplication-and-the-confound-it-exposed-in-phase-8)):
its tool does not return the text, because `lookup_entry` defaults to
`view=FULL` and FULL returns required aspects plus only the **keys** of
non-required ones. `overview` is non-required, so roughly three quarters of the
payload is withheld. Then the projector took ownership of `descriptions` and
`queries` too, with `userManaged: true` and verified to survive a re-scan
([result](MEASUREMENTS.md#kcmd-now-owns-descriptions-and-queries-what-that-bought-and-what-it-did-not)):
no movement.

**Forcing the view confirms the diagnosis**
([Arm Dall](MEASUREMENTS.md#forcing-viewall-arm-dall-and-the-two-failures-it-separates)).
A fourth arm forces `view=ALL` on every call via a `before_tool_callback` —
deterministic, not a prompt request. **q2 goes 0/3 → 2/3, and both successes are
exactly the runs that called the tool; the failure never called it.**

That splits the problem into three independent failure points, each needing a
different fix:

1. **Published** — the knowledge must be on the entry (Track A).
2. **Returned** — the default read path must not withhold it (the view).
3. **Requested** — the agent must actually call the tool (tool-surface design).

Pooled over 75 D-family runs, the pattern is unambiguous:

```
score tracks the RETRIEVAL rate, not the content
  Arm K      11/15 correct,  lookup called 14/15
  D family  6-8/15 correct,  lookup called 1-5/15

on q1+q2, the questions only the catalog can settle:
  called lookup_entry:      2 correct /  6   (33%)
  did NOT call:             1 correct / 24   ( 4%)
```

**Retrieval, not content, is the dominant failure — and it is the one thing OKF
cannot address.** Three consecutive improvements to what the catalog holds and
how it is read produced no measurable gain, because the agent does not ask in 24
of 30 attempts on the questions that need it.

**q4 was 0/3 on both arms, and the reason is not what it first looked like**
([retraction](MEASUREMENTS.md#how-does-an-agent-get-from-a-table-to-its-joinmetric-concepts-today-barely)).
The hazard *is* curated, with numerator and denominator. Arm K called
`lookup-entry` on all three reps and never fetched it; no response in any run
mentions a metric concept. The knowledge was present, addressable, and
unreached. **The ceiling is not what someone curated — it is what is reachable
from where the agent starts.**

That failure is the one thing since addressed on the bundle side rather than the
catalog side: 58 generated back-links now connect each table concept to the
concepts about it. **Its effect on the score is unmeasured** — see §6.

---

## 5. The honest bottom line

**Use OKF as a source of truth if you want the bundle to win.** The full-replace
semantics, the surviving trust tier, and the reviewable canonical diff genuinely
deliver "the file is authoritative, the catalog is a projection." That is a real
capability and it was blocked by tooling, never by Knowledge Catalog.

**And "the bundle wins" is best scoped, not absolute**
([the tier model](MEASUREMENTS.md#ownership-gated-on-verified-the-three-tier-projection-model)).
OKF-native (`okf`) and uncontested platform-native (`overview`) aspects are
always bundle-owned; *contested* ones (`descriptions`, `queries` — the ones a
scan also writes) are owned **only where a human has signed off**. Claiming a
contested aspect means freezing it, and freezing unreviewed generated content is
worse than letting the platform keep refreshing it. Gating on `verified` also
closes coverage gaps for free: released tables get their undocumented columns
filled by the scan.

**Do not claim any of the following. All three are measured false:**

1. *"The OKF trust flag protects content from the pipeline."* **Not by itself.**
   Knowledge Catalog does not couple them at all — Measurement G destroyed a
   `verified` concept that had `userManaged: false`. The projector now *makes*
   the coupling, so the flag confers protection **as a matter of our projection
   policy, not platform behaviour**. Anyone reading the bundle without that
   projector should not assume it.
2. *"OKF round-trips cleanly."* Not byte-wise, not without a canonicaliser you
   build yourself, and not at all for duplicate tags.
3. *"Putting knowledge in the catalog makes an agent use it."* Arm D skipped the
   catalog in half its runs — and when the identical bodies were projected onto
   the very entries it queries, its score did not move. **Availability,
   retrieval and legibility are three different problems.**

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
- **A real concurrent scan.** The *mechanism* is built and verified against a
  synthetic out-of-band edit (§7); what has not happened is a live
  DATA_DOCUMENTATION run since the differ landed.
- **The effect of the `# Related concepts` back-links on the score.** They are
  aimed squarely at the reachability failure §4 identifies, and **no eval has
  been re-run since they landed.** This is the most valuable open measurement in
  the repo.
- **Phase 8 at any statistical weight.** n=3, one model, 5 questions; tool use
  varied between identical repeats.

**Closed since first writing:** ~~the `index.md` gap~~ — it was
**documents-layout only**. `OkfLayout` synthesises a directory entry per folder
and regenerates the listings itself, so switching the staged tree to
`layout: okf` closed it with kcmd's own code
([7 index entries, live](MEASUREMENTS.md#interop-proved-an-unmodified-kcmd-pushes-the-whole-bundle)).
Recording it as a gap in the *system* was wrong; it was a gap in the layout we
happened to be using.

---

## 7. Corrected — three claims that did not survive

Investigated further and retracted. Kept here rather than edited away, because
two of them were quoted forward into a plan.

**"kcmd is remote-authoritative by design" — false.** Its own `concept.md` tenet
says the code artifacts "should be amenable to **serving as authoring and
management source of truth**", and `spec.md` specifies fail-fast conflict
handling with a force override, a `.catalog.state` checksum file, and deletion
intent. **None of it is implemented** — zero occurrences of
checksum/state/etag in `kcmd/src`, two conflict TODOs, and `force` plumbed from
the CLI into a field nothing reads. kcmd aims where we aim; it is
remote-authoritative because the version-control half of its own spec was never
built. That is a missing layer, not a philosophical difference, and it changes
the gap from something to work around into something to build.

**"v0.1's stash beats us on inspecting everything in the catalog" — no longer
true**
([the mirrored tier](MEASUREMENTS.md#the-mirrored-tier-distributional-facts-a-bundle-only-reader-could-not-get)).
The trade was real: the stash carried every aspect while we carried four
channels. The mirror now gives that coverage in **OKF-native, addressable form**
— a `# Schema` table, a `# Data characteristics` section — where every value is
readable and individually diffable rather than buried in a serialized entry.
Coverage *and* legibility.

**"Multi-writer conflict is untested" — the mechanism now exists and works**
([the differ](MEASUREMENTS.md#the-return-leg-a-forward-differ-and-the-premise-it-was-built-on-turns-out-to-be-wrong)).
The DATA_DOCUMENTATION scan *is* the concurrent editor, and the differ makes it
observable for the first time. Verified end to end against an out-of-band write:
the right concept, the right channel, attributed to a third party from the
server's own clock, the push **aborted** rather than overwriting, and `--force`
repaired it.

The reason it reports two verdicts rather than one: for an **unverified**
concept a moved `descriptions` timestamp is the system working as designed —
the scan is supposed to refresh it — while for a **verified** one it is an
ownership failure. Same signal, opposite meaning, decided by nothing but the
flag. Conflate them and every routine scan shows up red, people stop reading the
report, and a genuine failure is ignored along with the noise.

This rests on a measurement nobody expected: **Dataplex's per-aspect
`updateTime` is content-addressed by the server** — identical writes moved the
entry-level timestamp on all 14 entries and the aspect-level timestamp on **0 of
241**. So "which channel changed, and was it us" is answerable from a value
neither we nor kcmd can write. That is strictly better evidence than the
client-side checksums kcmd's own spec proposes, and it is why this repo has no
content hash.

**One thing got worse, and it is worth saying plainly.** Running an *unmodified*
kcmd against a workspace that has links is **destructive to the link layer** —
one pristine push deleted the probe link, because an undeclared `entryLinks:`
makes the reconciler's lookup unfiltered. The interop claim is scoped to
**entries and aspects**.
