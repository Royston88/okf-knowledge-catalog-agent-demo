#!/usr/bin/env python3
"""OKF v0.2 conformance check (SPEC.md §11), plus the content invariants
this project added. Run: python okf-review/conformance.py
"""
import pathlib, re, sys, yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent / "okf-bundle"
RESERVED = {"index.md", "log.md"}
fails, warns, checked = [], [], 0
# §6.1 permits two link forms and RECOMMENDS the absolute one. Counting them
# separately is the guard on the migration to it: `link-concepts.ts` greps the
# bundle for `tables/<name>.md` to derive the 58 `related` EntryLinks, so a
# rewrite the extractor did not learn about would take that layer to zero while
# every other check stayed green — the silent-plausible-success shape this repo
# keeps hitting. A number that must not be zero is cheaper than remembering.
links = {"absolute": 0, "relative": 0, "bare": 0}

def split(p):
    t = p.read_text()
    if not t.startswith("---\n"):
        return None, t
    try:
        end = t.index("\n---\n", 3)
    except ValueError:
        return None, t
    return yaml.safe_load(t[4:end]), t[end+5:]

for p in sorted(ROOT.rglob("*.md")):
    rel = p.relative_to(ROOT)
    if p.name in RESERVED:
        # §11.3: a reserved filename must follow §8 (index.md) or §9 (log.md).
        # They are DIFFERENT structures and were previously checked against §8
        # alone, which asked log.md for bulleted links it has no reason to have.
        fm, body = split(p)
        if fm is not None and not (p.parent == ROOT and set(fm) <= {"okf_version"}):
            fails.append(f"§8  {rel}: reserved file carries frontmatter {sorted(fm)}")
        if not re.search(r"^#\s+\S", body, re.M):
            warns.append(f"§8  {rel}: no section heading")
        if p.name == "log.md":
            # §9: "a flat list of date-grouped entries, newest first. Date
            # headings MUST use ISO 8601 YYYY-MM-DD form."
            dates = re.findall(r"^##\s+(\S+)\s*$", body, re.M)
            if not dates:
                fails.append(f"§9  {rel}: no `## <date>` groups")
            bad = [d for d in dates if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d)]
            if bad:
                fails.append(f"§9  {rel}: date headings not ISO 8601: {bad}")
            if dates != sorted(dates, reverse=True):
                fails.append(f"§9  {rel}: date groups are not newest-first: {dates}")
        elif not re.search(r"^\s*[*-]\s*\[.+?\]\(.+?\)", body, re.M):
            warns.append(f"§8  {rel}: no bulleted links")
        continue
    checked += 1
    fm, body = split(p)
    if fm is None:                                   # §11.1
        fails.append(f"§11.1 {rel}: no parseable YAML frontmatter"); continue
    if not str(fm.get("type", "")).strip():          # §11.2
        fails.append(f"§11.2 {rel}: `type` missing or empty")
    # §5 families, when present, should be well-formed
    if "verified" in fm and not isinstance(fm["verified"], list):
        fails.append(f"§5.2 {rel}: `verified` must be a list")
    for v in fm.get("verified") or []:
        if "by" not in v:
            fails.append(f"§5.2 {rel}: a `verified` entry has no `by`")
    if "generated" in fm and "by" not in (fm["generated"] or {}):
        fails.append(f"§5.2 {rel}: `generated` has no `by`")
    for s in fm.get("sources") or []:
        if "resource" not in s:
            fails.append(f"§5.1 {rel}: a `sources` entry has no `resource`")
    if fm.get("status") and fm["status"] not in ("draft", "stable", "deprecated"):
        fails.append(f"§5.4 {rel}: status {fm['status']!r} not draft|stable|deprecated")
    # §5.5: "An absolute date (YYYY-MM-DD)... An absolute date, not a relative
    # TTL, keeps the staleness decision a plain date comparison." A datetime or
    # a duration here would silently break that comparison for a consumer.
    if "stale_after" in fm:
        sa = fm["stale_after"]
        sa = sa.isoformat() if hasattr(sa, "isoformat") else str(sa)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", sa):
            fails.append(f"§5.5 {rel}: stale_after {sa!r} is not an absolute YYYY-MM-DD date")
    # §6.1 cross-links must resolve on disk. Two forms are legal: absolute
    # (bundle-relative, begins with `/`) and relative. §6.1 recommends absolute
    # and this bundle has migrated to it, so resolve against ROOT for those and
    # against the file's own directory otherwise.
    for m in re.finditer(r"\]\((?!https?://)([^)#]+\.md)\)", body):
        target = m.group(1)
        if target.startswith("/"):
            links["absolute"] += 1
            resolved = ROOT / target.lstrip("/")
        else:
            links["relative" if target.startswith(("./", "../")) else "bare"] += 1
            resolved = p.parent / target
        # §6.1 says a consumer MUST tolerate a broken link — it "may simply
        # represent not-yet-written knowledge". This bundle asserts something
        # stronger about itself: every link it writes resolves. That is what
        # makes the count above a usable guard rather than a statistic.
        if not resolved.resolve().exists():
            fails.append(f"§6.1 {rel}: dead link -> {target}")

print(f"checked {checked} concept files + {len(list(ROOT.rglob('index.md')))} index files")
print(f"cross-concept links: {links['absolute']} absolute (§6.1 recommended), "
      f"{links['relative']} relative, {links['bare']} bare same-dir — all resolve")
if links["relative"] or links["bare"]:
    warns.append("§6.1 some cross-concept links are not in the recommended "
                 "absolute form; run okf-review/postauthor.py --write")
for w in warns: print("  WARN", w)
for f in fails: print("  FAIL", f)
print(f"\n{'CONFORMANT' if not fails else 'NOT CONFORMANT'} — {len(fails)} failure(s), {len(warns)} warning(s)")
sys.exit(1 if fails else 0)
