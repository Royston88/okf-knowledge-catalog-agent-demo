# Test design — after the `verified` ⇄ `userManaged` coupling

The original Measurement G crossed `userManaged` with `verified` as **independent**
variables. They are no longer independent: the projector computes one from the
other, so three of that 2×2's four cells are now unreachable. This redesigns the
tests around what is actually true.

## The ownership rule under test

```
owned(concept) ==  verified is non-empty
               AND status not in {draft, deprecated}
               AND every real column is documented      <- hard gate, refuses if not

owned      -> descriptions + queries written with userManaged: true   (frozen)
not owned  -> the claim is RELEASED (userManaged: false); the scan resumes
always     -> okf + overview written regardless                       (uncontested)
```

`userManaged` is stored nowhere. It is derived at push time — correct if
Knowledge Catalog is one projection target rather than the system of record.

---

## Layer 1 — platform facts. Established; do NOT re-run.

These are properties of Dataplex, already measured, and independent of our
policy. Re-running them costs scans and proves nothing new.

| # | fact | evidence |
|---|---|---|
| P1 | `userManaged: true` prevents the DATA_DOCUMENTATION scan overwriting an aspect | Measurement G |
| P2 | `userManaged: false` ⇒ the scan overwrites, silently, no error | Measurement G |
| P3 | The scan only touches aspects it **owns**; `overview` and `okf` survive regardless of the flag | Measurement G extension |
| P4 | A protected aspect keeps its **original** `job` stamp — a stale stamp is evidence *of* protection, not of a skipped scan | Measurement G |
| P5 | Omitting an aspect from a push is a **no-op**, not a release | measured while building the release path |
| P6 | Writing curated content does **not** set `userManaged` — the platform never infers it | Measurement G probe |

## Layer 2 — policy tests. These are the redesign.

The unit under test is now **the projector**, not the platform. Each test is a
state transition or an invariant.

### T1 — Claim. `unverified → verified` takes ownership.
Add `verified` to an unverified concept → push → assert `userManaged: true`,
content equals the bundle → re-run that table's scan → assert byte-identical.
**Fails if** the projector does not claim, or the scan overwrites anyway.

### T2 — Release. `verified → unverified` hands it back.
Remove `verified` → push → assert `userManaged: false` and content untouched →
re-run the scan → assert scan-generated content returns.
**Fails if** the claim goes stale (which it did, before the release path existed
— see P5). This is the test that catches the whole class of "we stopped claiming
but never told the catalog".

### T3 — Idempotence. Pushing an unchanged bundle changes nothing.
Push twice → assert no ownership flapping and no content delta. Guards against a
release/claim loop where each push undoes the last.

### T4 — Round-trip safety. `pull → push` must be ownership- **and** content-neutral.
**Currently FAILS, and the coupling makes it worse.** `verified` does survive a
Track A pull, so ownership is preserved — but `description` does not, so a
pull→push writes an *empty* description into an aspect it has frozen. Owned
tables are exactly the ones this damages.
Fix before this can pass: recover `description` from the `descriptions` aspect in
`fromStaging`, symmetrically to how the body is already recovered from
`overview` (Measurement A.1).

### T5 — Completeness gate. An incomplete concept cannot be claimed.
Remove one column row from a verified concept's `# Schema` table → push must
**fail loudly**, naming the column. Also: documenting a column that does not
exist must fail.
**Why it exists:** claiming freezes the aspect, so an owned-but-incomplete
concept blanks a column permanently. Implemented as a hard gate against the
entry's own `schema` aspect — ground truth, not the bundle's word.

### T6 — Status gate. `draft` and `deprecated` do not own.
Set `status: draft` on a verified concept → push → assert released. Same for
`deprecated`. A draft should not take over the UI merely because someone signed
it; a deprecated concept should not hold the description hostage.

### T7 — Joins. **Outstanding from the original Phase 7 and still not run.**
The plan's arms 3 and 4 — "joins kept (`userManaged: true`) preserved" and
"joins deleted, re-created by the generator" — were never executed. Nothing in
this work has touched an entry link. `join_triage.yaml` records the verdicts
(11 keep, 1 JT2 reject) and `user_managed_set: false` for all 12, written before
deletion as the plan requires; the deletion never happened.
This is the natural analogue of T1/T2 one level down, at the `schema-join`
EntryLink rather than the aspect, and it should follow the same
claim/release/rescan shape.

---

## Status

| test | state | evidence |
|---|---|---|
| T1 Claim | **satisfied** | 6 verified tables took `userManaged: true` with bundle content; a re-scan of `accounts` left description, all 7 fields and all 3 queries byte-identical |
| T2 Release | **satisfied** | 7 unverified tables released; their scans re-run; scan-generated content returned. `userManaged` matches `okf.verified` on 13/13 |
| T3 Idempotence | **partial** | a second push reported `released 0` and changed nothing. Not yet asserted mechanically |
| T4 Round-trip safety | **FAILING** | `verified` survives a pull; `description` does not. Needs the `fromStaging` fix first |
| T5 Completeness gate | **satisfied** | `ownership.test.ts`, offline, incl. missing-column and phantom-column cases |
| T6 Status gate | **satisfied** | `ownership.test.ts`, offline, incl. case-insensitivity |
| T7 Joins | **not started** | nothing in this work has touched an entry link |

Run the offline suite with:

```bash
kcmd/node_modules/.bin/bun kcmd/demo/okf/ownership.test.ts
```

20 assertions, no catalog access, no scans. It also carries a regression test for
the header-detection bug that ate every column literally called `name`.

The live tests (T1–T4, T7) need pushes and scans and are not yet a harness; T1
and T2 are satisfied by the transitions performed during this work rather than
by a re-runnable script.

---

## The control, and why `verified` can no longer be it

Phase 7's control population was `signoff.py`'s deterministic every-other-concept
split. That was sound while `verified` was **inert** — the population was
*deliberately arbitrary* so a survival difference could be attributed to the flag
rather than the producer.

It is unusable now. `verified` is an authorisation signal that decides what the
platform shows users, so an arbitrary split would be choosing, at random, whose
descriptions are curated. A control wants to be uncorrelated with merit; an
authorisation wants to be exactly correlated.

**Resolution: a separate, experiment-only marker.**

```yaml
x-experiment:
  run: phase7-r2
  arm: control | treatment
```

- `x-` prefixed, matching the precedent OKF sets for `x-kcmd`: consumers ignore
  unknown keys, so the file stays spec-valid.
- **The projector must ignore it entirely.** It carries no ownership meaning; a
  test asserting that is worth having, because the failure mode is an experiment
  marker quietly changing production behaviour.
- `verified` reverts to meaning only what it says. The six currently-owned tables
  should be genuinely reviewed, or unflagged.

## Confound to declare on any Phase 7 re-run

Measurement G's result stands — it was taken *before* gating existed, with the
flag inert and a clean control. But it can no longer be reproduced as designed:
flagging a concept now changes ownership, which changes what the scan may
overwrite. Any re-run measures the policy, not the platform, and must say so.
