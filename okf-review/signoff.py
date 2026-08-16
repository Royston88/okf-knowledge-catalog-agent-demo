#!/usr/bin/env python3
"""Phase 6 sign-off: flag half the bundle `verified`, leave half unflagged.

WHY HALF. The flag has to be the ONLY variable. If every concept were flagged,
Phase 7 could not distinguish "the trust flag protected this content" from
"nothing overwrites anything here anyway". The unflagged half is the control.

THE SPLIT is deterministic and balanced ACROSS PROVENANCE CLASSES: concepts are
sorted by path within each `generated.by` class and every other one is flagged.
Balancing matters — flagging one whole class would confound the flag with the
producer, so a Phase 7 difference could be read as "agent-authored content is
treated differently" rather than "the flag worked".

WHAT THE FLAG CLAIMS. Our aspect schema defines `human:<id>` as human-reviewed.
The review this records is a real pass over the canonical diff and the
warehouse, and it found real things (the dedup conflict was empty, the profile
distinct count is off by one, one join fails JT2). It is NOT a deep per-concept
audit of all 53 bodies. Depth is stated in docs/MEASUREMENTS.md; do not read the flag
as more than "reviewed at Phase 6 depth".

  signoff.py --apply        the original half/half split (Phase 7 control)
  signoff.py --asset-backed sign off every ASSET-BACKED concept (Track A)
  signoff.py --status       report without changing anything
  signoff.py --clear        remove every `verified` key
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from canonicalize import canonicalize, split_frontmatter  # noqa: E402

BUNDLE = pathlib.Path(__file__).resolve().parent.parent / "okf-bundle"
ACTOR = "human:kenly@google.com"
AT = "2026-08-13T00:00:00+00:00"  # fixed, not wall-clock, so the bundle stays diffable


def concepts() -> list[tuple[pathlib.Path, dict, str]]:
    out = []
    for p in sorted(BUNDLE.rglob("*.md")):
        if p.name == "index.md":
            continue
        fm, body = split_frontmatter(p.read_text())
        if fm is None:
            continue
        out.append((p, fm, body))
    return out


def plan() -> dict[pathlib.Path, bool]:
    by_class: dict[str, list[pathlib.Path]] = {}
    for p, fm, _ in concepts():
        cls = (fm.get("generated") or {}).get("by", "unknown")
        by_class.setdefault(cls, []).append(p)
    decision: dict[pathlib.Path, bool] = {}
    for cls, paths in by_class.items():
        for i, p in enumerate(sorted(paths)):
            decision[p] = i % 2 == 0
    return decision


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--apply", action="store_true")
    g.add_argument("--asset-backed", action="store_true",
                   help="flag every concept with a top-level `resource:` — the 14 "
                        "Track A concepts, i.e. everything that projects "
                        "descriptions/queries onto an ingested @bigquery entry. "
                        "Leaves the joins and metrics untouched.")
    g.add_argument("--status", action="store_true")
    g.add_argument("--clear", action="store_true")
    a = ap.parse_args()

    if a.asset_backed:
        # Asset-backed == has a top-level `resource:`; the same discriminator the
        # projector uses to split Track A from Track B.
        decision = {p: bool(fm.get("resource")) for p, fm, _ in concepts()}
    else:
        decision = plan()
    if a.status:
        from collections import Counter
        per = Counter()
        for p, fm, _ in concepts():
            cls = (fm.get("generated") or {}).get("by", "unknown")
            per[(cls, "flagged" if decision[p] else "control")] += 1
            per[(cls, "has_verified_now")] += 1 if fm.get("verified") else 0
        for (cls, k), v in sorted(per.items()):
            print(f"{cls:38s} {k:18s} {v}")
        total = len(decision)
        print(f"\ntotal {total}, planned flagged {sum(decision.values())}, "
              f"control {total - sum(decision.values())}")
        return 0

    changed = 0
    for p, fm, body in concepts():
        before = dict(fm)
        if a.clear:
            fm.pop("verified", None)
        elif decision.get(p):
            fm["verified"] = [{"by": ACTOR, "at": AT}]
        elif not a.asset_backed:
            fm.pop("verified", None)   # half/half mode owns both sides of the split
        if fm != before:
            changed += 1
        p.write_text(canonicalize(f"---\n{yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)}---\n\n{body.strip()}\n"))
    print(f"{'cleared' if a.clear else 'applied'}: {changed} file(s) changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
