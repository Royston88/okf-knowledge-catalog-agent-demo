#!/usr/bin/env python3
r"""Canonically format OKF concept files so a diff means something.

WHY THIS EXISTS (Measurement C). A bundle projected into Knowledge Catalog and
pulled back is *semantically* intact but not one byte of it matches: 0 of 53
files survived byte-identical. Every difference was YAML serializer style — the
bundle is written by Python `yaml.safe_dump` and the round trip re-emits it with
JS `yaml.stringify`, and the two disagree about block-sequence indentation, the
line-wrap column, and whether timestamps get quoted.

That makes `git diff` useless as a review surface, which is exactly what
Measurement F is supposed to evaluate. So normalise both sides first.

THE CANONICAL STYLE — and why it is a choice, not a discovery.

The bundle's two producers do NOT agree, so there was no pre-existing canonical
form to adopt:

  | producer                          | width | allow_unicode |
  |-----------------------------------|-------|---------------|
  | `okf-emitter/gen_okf.py::_fm`     | 100   | False         |
  | `reference_agent` `OKFDocument.serialize` | 80 (default) | True |

Measured over the 53-concept bundle:

  | candidate style          | files reformatted | titles left with `\uXXXX` |
  |--------------------------|-------------------|---------------------------|
  | gen_okf (w=100, escaped) | 11                | 13                        |
  | agent   (w=80,  unicode) | 20                | 0                         |
  | **chosen (w=100, unicode)** | **24**         | **0**                     |

The chosen style costs the most one-time reformatting and is still the right
pick, because Measurement F asks whether the diff is *reviewable by a human*:

  * `allow_unicode=True` — the 13 join concepts are titled `customers → customers
    (referrer)`. Under gen_okf's style a reviewer reads
    `title: "customers → customers (referrer)"`. Escaping buys nothing and
    costs legibility on a quarter of the bundle.
  * `width=100` — a wider wrap means editing one word of a `description` rewraps
    fewer lines, so the diff shows the edit instead of the reflow.

Reformatting is a one-time cost; legibility is permanent. This does not touch
`gen_okf`'s own output, so Phase 4b's recorded "re-emission byte-identical"
property still holds — canonicalisation is a step *after* generation.

  * `yaml.safe_dump(..., sort_keys=False, width=100, allow_unicode=True)`
  * key order = `_PREFERRED_KEY_ORDER`, then any unrecognised keys in the order
    they appeared
      - matches `reference_agent/tools/bundle_tools.py::_reorder_frontmatter`,
        of which gen_okf's order is a subset
  * `---\n<frontmatter>\n---\n\n<body>\n`, body stripped

CONSEQUENCE: `reference_agent` re-authoring a concept writes non-canonical
frontmatter, so `--write` is a required post-authoring step, not an optional
tidy-up.

Frontmatter-less files (the OKF `index.md` directory listings) are passed
through untouched apart from trailing-whitespace normalisation.

USAGE
  canonicalize.py --check PATH...     exit 1 if anything is not canonical
  canonicalize.py --write PATH...     rewrite in place
  canonicalize.py --diff A B          canonicalise both trees into temp dirs and
                                      report the real differences
"""

from __future__ import annotations

import argparse
import datetime as _dt
import difflib
import pathlib
import sys

import yaml

# Mirrors reference_agent.tools.bundle_tools._PREFERRED_KEY_ORDER. Duplicated
# rather than imported so this tool works on a bundle without the agent
# installed; the two are checked against each other by --selftest.
PREFERRED_KEY_ORDER = (
    "type",
    "resource",
    "title",
    "description",
    "tags",
    "status",
    "generated",
    "verified",
    "stale_after",
    "sources",
    "usage_window",
)


def split_frontmatter(text: str) -> tuple[dict | None, str]:
    if not text.startswith("---\n"):
        return None, text
    try:
        end = text.index("\n---\n", 3)
    except ValueError:
        return None, text
    return yaml.safe_load(text[4:end]) or {}, text[end + 5 :]


def _scalarise(o):
    """Dates/times round-trip as strings, not Python objects.

    The bundle quotes its timestamps, so Python reads them back as `str`; the
    JS round trip emits them bare, so Python reads *those* as `datetime`. Both
    must canonicalise to the same quoted string or the diff reports a change
    that is not one.
    """
    if isinstance(o, dict):
        return {k: _scalarise(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_scalarise(v) for v in o]
    if isinstance(o, _dt.datetime):
        s = o.isoformat()
        return s.replace("+00:00", "+00:00")
    if isinstance(o, _dt.date):
        return o.isoformat()
    return o


# Key order INSIDE the record-valued fields. Measured need: after a round trip
# the `sources[]` items come back ordered `id, resource, title` (that is
# `fromStaging`'s `pick` order), while `reference_agent` authored them in
# whatever order the model happened to emit — 11 of the bundle's 14
# agent-authored concepts differ from the round trip on nothing but this.
# Ordering the top-level keys alone leaves that noise in the diff.
NESTED_KEY_ORDER = {
    "sources": ("id", "resource", "title"),
    "generated": ("by", "at"),
    "verified": ("by", "at"),
}


def _order_keys(d: dict, order: tuple[str, ...]) -> dict:
    out = {k: d[k] for k in order if k in d}
    for k, v in d.items():
        out.setdefault(k, v)
    return out


def reorder(fm: dict) -> dict:
    out = {k: fm[k] for k in PREFERRED_KEY_ORDER if k in fm}
    for k, v in fm.items():
        out.setdefault(k, v)
    for key, order in NESTED_KEY_ORDER.items():
        val = out.get(key)
        if isinstance(val, dict):
            out[key] = _order_keys(val, order)
        elif isinstance(val, list):
            out[key] = [_order_keys(v, order) if isinstance(v, dict) else v for v in val]
    return out


def canonicalize(text: str) -> str:
    fm, body = split_frontmatter(text)
    if fm is None:
        return text.rstrip() + "\n"
    dumped = yaml.safe_dump(
        reorder(_scalarise(fm)), sort_keys=False, width=100, allow_unicode=True
    ).rstrip()
    return f"---\n{dumped}\n---\n\n{body.strip()}\n"


def md_files(root: pathlib.Path) -> list[pathlib.Path]:
    if root.is_file():
        return [root]
    return sorted(root.rglob("*.md"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="exit 1 if not canonical")
    g.add_argument("--write", action="store_true", help="rewrite in place")
    g.add_argument("--diff", action="store_true", help="canonical diff of two trees")
    g.add_argument("--selftest", action="store_true",
                   help="verify the key order still matches reference_agent")
    ap.add_argument("paths", nargs="*", type=pathlib.Path)
    args = ap.parse_args()

    if args.selftest:
        from reference_agent.tools.bundle_tools import _PREFERRED_KEY_ORDER as upstream
        if tuple(upstream) != PREFERRED_KEY_ORDER:
            print("DRIFT: reference_agent key order has changed")
            print("  upstream:", upstream)
            print("  here    :", PREFERRED_KEY_ORDER)
            return 1
        print("selftest OK — key order matches reference_agent")
        return 0

    if args.diff:
        if len(args.paths) != 2:
            ap.error("--diff takes exactly two paths")
        a, b = args.paths
        an = {p.relative_to(a): canonicalize(p.read_text()) for p in md_files(a)}
        bn = {p.relative_to(b): canonicalize(p.read_text()) for p in md_files(b)}
        only_a, only_b = sorted(set(an) - set(bn)), sorted(set(bn) - set(an))
        changed = sorted(k for k in set(an) & set(bn) if an[k] != bn[k])
        for k in only_a:
            print(f"only in {a}: {k}")
        for k in only_b:
            print(f"only in {b}: {k}")
        for k in changed:
            print(f"\n=== {k} ===")
            sys.stdout.writelines(
                difflib.unified_diff(an[k].splitlines(True), bn[k].splitlines(True),
                                     fromfile=f"a/{k}", tofile=f"b/{k}")
            )
        print(f"\ncommon={len(set(an) & set(bn))} changed={len(changed)} "
              f"only_a={len(only_a)} only_b={len(only_b)}")
        return 1 if (changed or only_a or only_b) else 0

    dirty = []
    for root in args.paths:
        for p in md_files(root):
            src = p.read_text()
            out = canonicalize(src)
            if out == src:
                continue
            dirty.append(p)
            if args.write:
                p.write_text(out)
    if args.write:
        print(f"rewrote {len(dirty)} file(s)")
        return 0
    for p in dirty:
        print(f"not canonical: {p}")
    print(f"{len(dirty)} file(s) not canonical")
    return 1 if dirty else 0


if __name__ == "__main__":
    raise SystemExit(main())
