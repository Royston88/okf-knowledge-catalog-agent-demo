#!/usr/bin/env python3
"""OKF v0.2 conformance check (SPEC.md §11), plus the content invariants
this project added. Run: python okf-review/conformance.py
"""
import pathlib, re, sys, yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent / "okf-bundle"
RESERVED = {"index.md", "log.md"}
fails, warns, checked = [], [], 0

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
        # §11.3 + §8: index files contain NO frontmatter, except a bundle-root
        # index.md which MAY carry `okf_version`.
        fm, body = split(p)
        if fm is not None and not (p.parent == ROOT and set(fm) <= {"okf_version"}):
            fails.append(f"§8  {rel}: reserved file carries frontmatter {sorted(fm)}")
        if not re.search(r"^#\s+\S", body, re.M):
            warns.append(f"§8  {rel}: no section heading")
        if not re.search(r"^\s*[*-]\s*\[.+?\]\(.+?\)", body, re.M):
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
    # §6.1 cross-links must resolve on disk
    for m in re.finditer(r"\]\((?!https?://)([^)#]+\.md)\)", body):
        if not (p.parent / m.group(1)).resolve().exists():
            fails.append(f"§6.1 {rel}: dead link -> {m.group(1)}")

print(f"checked {checked} concept files + {len(list(ROOT.rglob('index.md')))} index files")
for w in warns: print("  WARN", w)
for f in fails: print("  FAIL", f)
print(f"\n{'CONFORMANT' if not fails else 'NOT CONFORMANT'} — {len(fails)} failure(s), {len(warns)} warning(s)")
sys.exit(1 if fails else 0)
