# Bundle Update Log

The bundle's own history, in the OKF §9 date-grouped form, newest first. Git
holds the byte-level record; this holds the record a *reader of the bundle*
needs, because a bundle is meant to travel without its repository — §1: "no
required tooling… if you can `git clone` a repo, you can ship it", and a
consumer that received only `okf-bundle/` has no `git log` to consult.

Scope is the bundle. Changes to the projector, the emitter or the review tools
are recorded here only where they changed the bundle's contents.

## 2026-08-15

* **Update**: every cross-concept link migrated to the §6.1 **absolute
  (bundle-relative)** form — 190 links, from 87 relative and 103 bare same-dir,
  0 absolute before. That form is "stable when documents are moved within their
  subdirectory". Rendered by [gen_okf.py](/references/index.md)'s emitter for
  `references/**` and by `okf-review/postauthor.py` for the agent-authored
  concepts.
* **Update**: a generated `# Related concepts` section added to all 13 table
  concepts, listing the Grain Rule, Join and Metric concepts that reference
  them — 58 back-links. Until now no table concept linked to any reference
  concept, so a reader starting at [accounts](/tables/accounts.md) had no path
  to [avg_txns_per_account](/references/metrics/accounts__avg_txns_per_account.md).
  That gap is Phase 8's measured q4 failure. §6.1 treats links as directed, so
  the back-link is a new assertion rather than a duplicate of the forward one.
* **Update**: `status` written explicitly on all 58 concepts (44 before).
  Absent means `stable` under §5.4, so no meaning changed — but a reader should
  not need the spec's default to know the lifecycle state, and a future move to
  `draft` is now a visible diff rather than an appearing key.
* **Update**: `generated.at` is content-accurate. It was a batch run stamp — 39
  of 44 emitter concepts shared `2026-08-12T00:00:00+00:00` — so equal
  timestamps did not imply equal content and a body edit did not move one. The
  emitter now compares each rendered concept against the file on disk and
  carries the old timestamp forward when nothing meaningful changed. §5.2 asks
  for "the content's last meaningful change"; this is that.
* **Correction**: re-running the emitter used to **delete** `verified`. It is
  written by sign-off and is not derivable from `spec.yaml`, so a plain re-run
  silently removed the human sign-off from 20 reference concepts. The emitter
  now owns only the keys it derives from the spec and carries every other
  frontmatter key forward.

## 2026-08-14

* **Creation**: three new concept types — `Grain Rule` (3), `Hierarchy` (1),
  `Derived Table` (1) — taking the bundle from 53 to **58 concepts** and
  covering all 11 `spec.yaml` constructs. The de-duplication rule behind
  Phase 8's q1/q2 became an addressable concept instead of prose repeated
  inside Join bodies.

## 2026-08-13

* **Update**: all 53 SQL blocks in the bundle dry-run validated against
  BigQuery. Three real defects found and fixed; the exercise also retracted an
  "undocumented columns" finding that was a parser bug in the reviewer, not a
  gap in the bundle.
* **Verification**: the twelve joins triaged against the warehouse and half the
  bundle signed off — `verified` now present on 34 of 58 concepts.
* **Correction**: a distributional fact in [accounts](/tables/accounts.md) was
  copied from the Knowledge Catalog data profile, which reports 1,201 distinct
  `account_id` where the warehouse has 1,200. The prose now records both and
  says which is authoritative.

## 2026-08-12

* **Initialization**: the bundle created by two producers — `gen_okf.py` for
  `references/**` (joins, metrics) from the reviewed BI modeling spec, and
  `reference_agent` for [tables](/tables/index.md) and
  [datasets](/datasets/index.md) from BigQuery. 53 concepts.
