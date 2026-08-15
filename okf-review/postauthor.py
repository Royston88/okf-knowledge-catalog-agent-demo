#!/usr/bin/env python3
r"""The pass that runs AFTER both producers and BEFORE `canonicalize.py`.

The bundle has two producers and neither can do these three jobs:

  * `okf-emitter/gen_okf.py` owns `references/**` and sees only `spec.yaml`.
  * `reference_agent` (upstream, outside this repo) owns `tables/**` and
    `datasets/**` and sees only BigQuery.

Everything here is bundle-WIDE or cross-concept, so it belongs in a third pass
in the same slot as `canonicalize.py` — and, like that tool, it is idempotent
and has a `--check` mode so CI can assert the bundle is already in its final
form.

THE THREE JOBS

1. **Absolute links (§6.1).** OKF recommends the bundle-relative `/tables/x.md`
   form because it is "stable when documents are moved within their
   subdirectory". Measured before this pass: 87 relative, 103 bare same-dir,
   **0 absolute**. `gen_okf` now emits the absolute form natively; this
   migrates the agent-authored concepts, which it re-authors in the bare form
   every time it runs.

2. **Explicit `status` (§5.4).** 44/58 carried it. Absent means `stable`, so
   the bundle's meaning was already right — but a reader should not have to
   know the spec's default to know the lifecycle state, and an explicit value
   makes a future move to `draft` or `deprecated` a visible diff rather than an
   appearing key.

3. **`# Related concepts` back-links — the one that fixes a MEASURED failure.**
   The 44 reference concepts link to the tables they describe; **no table
   concept links back**. `### Key Relationships` in `accounts.md` names only
   other tables. So a reader starting at `tables/accounts.md` has no path to
   `metrics/accounts__avg_txns_per_account` — which is exactly Phase 8's q4:
   the agent fetched the `accounts` concept on all three reps while the answer
   sat one lookup away in a document it never thought to ask for.

   `related` EntryLinks closed that hole on the CATALOG path. Arm K — the arm
   that scored 11/15 — reads the bundle over MCP with no catalog access at all,
   so for it the hole is still open. This closes it on the path the winning arm
   actually uses, and it needs no catalog access to do so.

   OKF §6.1 makes this spec-native rather than a convention of ours: concepts
   link with standard markdown links, and links are **directed** — "a link from
   concept A to concept B asserts a relationship... consumers typically treat
   all links as directed edges". concept→table and table→concept are therefore
   two distinct assertions, so the back-link is new information, not
   duplication. (Dataplex `related` is undirected and collapses the two into
   one link — the bundle carries strictly more structure than the catalog can
   express.)

ONE DERIVATION, THREE RENDERINGS. `desired_related_links()` here and the
`wanted` map in `kcmd/demo/okf/link-concepts.ts` are the same derivation over
the same source — the reference concepts' own body links. They are duplicated
across two languages, in the same way `canonicalize.py` duplicates
`reference_agent`'s key order, and guarded the same way: `ownership.test.ts`
asserts the TS derivation agrees with the `# Related concepts` sections this
tool writes, so a divergence fails offline instead of silently halving the
link layer.

USAGE
  postauthor.py --check [BUNDLE]     exit 1 if anything is not already applied
  postauthor.py --write [BUNDLE]     apply in place
"""

from __future__ import annotations

import argparse
import pathlib
import posixpath
import re
import sys

import yaml

RESERVED = {"index.md", "log.md"}
RELATED_HEADING = "# Related concepts"
# Rendered from `desired_related_links`, so hand edits are overwritten. Said in
# the file rather than only here, because the file is what a reader sees.
RELATED_PREAMBLE = (
    "_Generated from the concepts that reference this table — see "
    "`okf-review/postauthor.py`._"
)
# Grouping and order of the `# Related concepts` section. Anything whose type is
# not listed falls into a trailing "Other" group rather than being dropped.
TYPE_GROUPS = ("Grain Rule", "Join", "Metric", "Hierarchy", "Derived Table")
TYPE_PLURAL = {
    "Grain Rule": "Grain rules",
    "Join": "Joins",
    "Metric": "Metrics",
    "Hierarchy": "Hierarchies",
    "Derived Table": "Derived tables",
}

# A markdown link to another concept. Excludes external URLs and pure anchors.
LINK = re.compile(r"\]\((?!https?://|#)([^)\s]+?\.md)\)")
# The same table reference the TS reconciler greps for, in every form the
# bundle uses: `/tables/x.md`, `../../tables/x.md`, `tables/x.md`.
TABLE_REF = re.compile(r"\]\((?:\.{1,2}/)*/?tables/([a-z0-9_]+)\.md\)", re.I)


def split(text: str) -> tuple[dict | None, str]:
    if not text.startswith("---\n"):
        return None, text
    try:
        end = text.index("\n---\n", 3)
    except ValueError:
        return None, text
    return yaml.safe_load(text[4:end]) or {}, text[end + 5:]


def concepts(bundle: pathlib.Path) -> list[pathlib.Path]:
    return [p for p in sorted(bundle.rglob("*.md")) if p.name not in RESERVED]


def to_absolute(body: str, reldir: str) -> str:
    """Every cross-concept link, in the §6.1 recommended bundle-absolute form."""
    def sub(m: re.Match) -> str:
        target = m.group(1)
        if target.startswith("/"):
            return m.group(0)
        return "](/" + posixpath.normpath(posixpath.join(reldir, target)).lstrip("/") + ")"
    return LINK.sub(sub, body)


def desired_related_links(bundle: pathlib.Path) -> dict[str, set[str]]:
    """table name -> the reference concepts that reference it.

    Taken from each reference concept's own body links rather than from `tags`:
    tags carry non-table words too ("join", "one-to-many"), while the links are
    the concept's actual, explicit references. This is the map `link-concepts.ts`
    projects as `related` EntryLinks and the map rendered below as back-links —
    one derivation, three renderings.
    """
    wanted: dict[str, set[str]] = {}
    refs = bundle / "references"
    for p in sorted(refs.rglob("*.md")) if refs.exists() else []:
        if p.name in RESERVED:
            continue
        fm, body = split(p.read_text(encoding="utf-8"))
        if fm is None:
            continue
        rel = p.relative_to(bundle).as_posix()[: -len(".md")]
        for m in TABLE_REF.finditer(body):
            wanted.setdefault(m.group(1), set()).add(rel)
    return wanted


def render_related(bundle: pathlib.Path, rels: set[str]) -> str:
    """The `# Related concepts` section body for one table."""
    by_type: dict[str, list[tuple[str, str, str]]] = {}
    for rel in sorted(rels):
        fm, _ = split((bundle / f"{rel}.md").read_text(encoding="utf-8"))
        fm = fm or {}
        by_type.setdefault(str(fm.get("type") or "Other"), []).append(
            (str(fm.get("title") or posixpath.basename(rel)),
             f"/{rel}.md",
             str(fm.get("description") or "").strip())
        )
    order = [t for t in TYPE_GROUPS if t in by_type]
    order += [t for t in sorted(by_type) if t not in TYPE_GROUPS]
    lines = [RELATED_HEADING, "", RELATED_PREAMBLE, ""]
    for t in order:
        lines.append(f"## {TYPE_PLURAL.get(t, t)}")
        for title, href, desc in sorted(by_type[t]):
            lines.append(f"* [{title}]({href})" + (f" - {desc}" if desc else ""))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def strip_related(body: str) -> str:
    """Remove an existing `# Related concepts` section, so the pass is idempotent."""
    out, skipping = [], False
    for line in body.split("\n"):
        if line.strip() == RELATED_HEADING:
            skipping = True
            continue
        if skipping:
            # A section ends at the next top-level heading; `##` subheadings
            # inside it are ours.
            if re.match(r"^#(?!#)\s", line):
                skipping = False
            else:
                continue
        out.append(line)
    return "\n".join(out)


def place_related(body: str, section: str) -> str:
    """Insert before the first top-level heading, else append.

    In a table concept that puts it after the intro and `### Key Relationships`
    and before `# Schema` — where a reader looking for "what else is there"
    arrives before wading through 22,000 characters of query patterns, and
    where it cannot be truncated away by a consumer that reads only the head.
    """
    body = strip_related(body).rstrip() + "\n"
    lines = body.split("\n")
    for i, line in enumerate(lines):
        if re.match(r"^#(?!#)\s", line):
            head = "\n".join(lines[:i]).rstrip()
            tail = "\n".join(lines[i:]).strip()
            return f"{head}\n\n{section}\n{tail}\n"
    return f"{body.rstrip()}\n\n{section}"


def process(bundle: pathlib.Path) -> tuple[dict[pathlib.Path, str], dict[str, int]]:
    """Return {path: new text} for every file that is not already final."""
    wanted = desired_related_links(bundle)
    changes: dict[pathlib.Path, str] = {}
    stats = {"links": 0, "status": 0, "related": 0, "files": 0,
             "tables_linked": len(wanted),
             "refs": sum(len(v) for v in wanted.values())}

    for p in concepts(bundle):
        src = p.read_text(encoding="utf-8")
        fm, body = split(src)
        if fm is None:
            continue
        rel = p.relative_to(bundle).as_posix()
        reldir = posixpath.dirname(rel)

        new_body = to_absolute(body, reldir)
        stats["links"] += sum(
            1 for m in LINK.finditer(body) if not m.group(1).startswith("/"))

        # §5.4: absent status means `stable`, so writing it preserves meaning.
        new_fm = dict(fm)
        if not new_fm.get("status"):
            new_fm["status"] = "stable"
            stats["status"] += 1

        stem = p.stem
        if reldir == "tables" and stem in wanted:
            new_body = place_related(new_body, render_related(bundle, wanted[stem]))
            stats["related"] += 1

        out = ("---\n"
               + yaml.safe_dump(new_fm, sort_keys=False, width=100,
                                allow_unicode=True).rstrip()
               + "\n---\n\n" + new_body.strip() + "\n")
        if out != src:
            changes[p] = out
            stats["files"] += 1
    return changes, stats


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    ap.add_argument("bundle", nargs="?", type=pathlib.Path,
                    default=pathlib.Path(__file__).resolve().parent.parent / "okf-bundle")
    args = ap.parse_args()

    changes, stats = process(args.bundle)
    print(f"relative/bare links rewritten to absolute   {stats['links']}")
    print(f"`status` made explicit                      {stats['status']}")
    print(f"`# Related concepts` sections rendered      {stats['related']}")
    print(f"  from {stats['refs']} concept->table reference(s) "
          f"across {stats['tables_linked']} table(s)")
    if args.write:
        for p, text in changes.items():
            p.write_text(text, encoding="utf-8")
        print(f"\nrewrote {len(changes)} file(s)")
        return 0
    for p in sorted(changes):
        print(f"  not final: {p}")
    print(f"\n{len(changes)} file(s) not in post-authored form")
    return 1 if changes else 0


if __name__ == "__main__":
    sys.exit(main())
