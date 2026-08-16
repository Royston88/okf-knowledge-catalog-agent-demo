#!/usr/bin/env python3
"""Every citation from RESULTS.md into MEASUREMENTS.md must resolve.

WHY THIS IS A CHECK AND NOT A CONVENTION. The two documents are split by
LIFECYCLE, not by topic: MEASUREMENTS is append-only (measured across the
branch, it deletes 1% of what it inserts) while RESULTS is revised in place (8%).
That split only earns itself if RESULTS *cites* the evidence rather than
restating it — and before this existed it cited MEASUREMENTS exactly once in 317
lines, so the stated relationship was a convention nobody was keeping.

Citations are by GitHub heading anchor, which makes every `##` heading in
MEASUREMENTS part of an interface. Rename one and a link in the synthesis breaks
silently — the failure mode this repo is shaped around. So: count them, and fail
if any stops resolving.

    python okf-review/check_doc_links.py
"""
import pathlib
import re
import sys

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"


def slug(heading: str) -> str:
    """GitHub's heading-to-anchor rule, near enough for our headings."""
    s = heading.strip().lower()
    s = re.sub(r"[`*_\[\]()]", "", s)
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s+", "-", s.strip())


def strip_code(text: str) -> str:
    """Drop fenced blocks and inline code spans before looking for links.

    These documents QUOTE link syntax as subject matter — `[accounts](../../
    tables/accounts.md)` appears in prose as an example of the relative form the
    bundle migrated away from. That is a quotation, not a link, and flagging it
    would train the reader to ignore this check's output, which is the one thing
    a check must never do.
    """
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def main() -> int:
    fails = []
    total = 0
    for src in sorted(DOCS.glob("*.md")):
        text = strip_code(src.read_text(encoding="utf-8"))
        for target, anchor in re.findall(r"\]\(([A-Za-z0-9_.-]+\.md)#([^)]+)\)", text):
            total += 1
            tgt = DOCS / target
            if not tgt.exists():
                fails.append(f"{src.name}: target missing -> {target}")
                continue
            anchors = {slug(l[3:]) for l in tgt.read_text(encoding="utf-8").splitlines()
                       if l.startswith("## ") or l.startswith("### ")}
            if anchor not in anchors:
                fails.append(f"{src.name}: dead anchor -> {target}#{anchor}")
        # A plain file-to-file link must resolve too.
        for target in re.findall(r"\]\((?!https?://|#)([A-Za-z0-9_./-]+\.md)\)", text):
            if not (src.parent / target).resolve().exists():
                fails.append(f"{src.name}: dead link -> {target}")

    print(f"cross-document citations checked: {total}")
    for f in fails:
        print(f"  FAIL {f}")
    print(f"\n{'OK' if not fails else f'{len(fails)} BROKEN'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
