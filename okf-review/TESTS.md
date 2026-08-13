# Test design — the projection rule

## The rule, and it is the whole rule

```
the bundle always projects   overview + descriptions + queries
userManaged                  = whether the concept is `verified`
```

Verified content is frozen against the DATA_DOCUMENTATION scan. Unverified
content is still projected, just left unprotected, so the next scan replaces it.
The bundle is always the source; sign-off is what makes the catalog stop
second-guessing it.

One asymmetry, and it is Dataplex's, not a design choice: **`overview` has no
`userManaged` field** — the aspect type is `content`/`links`/`contentType` only.
It needs none, because the scan does not write `overview` at all (measured). So
the flag applies to `descriptions` and `queries`, the two contested aspects.

`userManaged` is stored nowhere — not in the bundle, not in config. It is
computed at push time, which is correct if Knowledge Catalog is one projection
target among several rather than the system of record.

## Layer 1 — platform facts. Established; do NOT re-run.

Properties of Dataplex, already measured, independent of our policy.

| # | fact | evidence |
|---|---|---|
| P1 | `userManaged: true` prevents the scan overwriting an aspect | Measurement G |
| P2 | `userManaged: false` ⇒ the scan overwrites, silently, no error | Measurement G |
| P3 | The scan only touches aspects it **owns**; `overview` and `okf` survive regardless | Measurement G extension |
| P4 | A protected aspect keeps its **original** `job` stamp — a stale stamp is evidence *of* protection | Measurement G |
| P5 | Omitting an aspect from a push is a no-op, not a release — so always write both, with the flag | measured |
| P6 | Writing content never makes the platform infer `userManaged` | Measurement G probe |

## Layer 2 — the projection rule

Offline, no catalog, no scans:

```bash
kcmd/node_modules/.bin/bun kcmd/demo/okf/ownership.test.ts
```

**26 assertions**, covering:

- `userManaged` tracks `verified` on both aspects, including the empty-array case
- content is projected either way — `verified` decides *protection*, not presence
- the body parsers (a column literally called `name` is not eaten; all 8
  `customers` columns; query patterns extracted)
- all 13 tables project both aspects with the expected flag

Live behaviour, verified against the catalog after each push:

| check | state |
|---|---|
| all three aspects present on all 14 entries | **passing** |
| `userManaged == verified` on 13/13 tables | **passing** |
| verified content survives a re-scan byte-identical | **passing** (`accounts`) |
| unverified content is replaced by the scan | **passing** (7 tables) |
| **pull → push is content-neutral** | **PASSING** — Track A 14/14, Track B 39/39 |

## Round trip — FIXED, both directions

`kcmd`'s transport was never the problem: the staged file it produces carries
`descriptions`, `queries`, `overview` and `userManaged` intact. Our
`fromStaging` was discarding four frontmatter fields. Four fixes:

| field | why it was lost | fix |
|---|---|---|
| `description` | lives in the `descriptions` aspect; on an ingested entry `entry_source.description` is platform-owned | read it from the aspect — **and prefer ours over the platform's**, since the BigQuery *dataset* has its own description and was overwriting the bundle's |
| `tags` | `entry_source.labels` is platform-owned on ingested entries — our tags never landed | carry on the `okf` aspect |
| `title` | `entry_source.displayName` likewise — came back as the native `accounts` | carry on the `okf` aspect |
| `resource` | Dataplex returns the bare `projects/P/datasets/D/tables/T` form | normalise back to the REST URL form the bundle uses |

`title` and `tags` required extending the `okf` aspect type (now 8 fields).
Measured result: **Track A 14/14 faithful on frontmatter *and* body; Track B 39
concepts, `changed=0`.**

The bundle is therefore no longer push-only — an edit made in the catalog can be
pulled back, which is what makes "OKF as version control" real rather than
aspirational.

## Outstanding

**The joins arm of the original Phase 7 was never run.** The plan's arms 3 and 4
— "joins kept (`userManaged: true`) preserved" and "joins deleted, re-created by
the generator" — remain untouched; nothing in this work has modified an entry
link. `join_triage.yaml` holds the verdicts (11 keep, 1 JT2 reject) written
before deletion as the plan requires. The deletion never happened.

## A note on the control

Measurement G used `signoff.py`'s arbitrary every-other-concept split as its
control, which was sound while `verified` was inert. It no longer is: the same
flag now decides what the platform shows. G's result stands (taken before the
coupling existed) but cannot be reproduced as designed. Any re-run needs a
separate, experiment-only marker — `x-experiment`, on the precedent OKF sets
with `x-kcmd` — that the projector ignores.
