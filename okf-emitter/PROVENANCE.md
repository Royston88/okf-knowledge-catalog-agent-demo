# Provenance of `okf-emitter/`

Both files here are **copies**. Nothing in `bi_modeling_playbook/` was edited —
that generator emits the graph and LookML stacks runs 004-009 depend on, and this
work must not perturb it.

## Sources

| File here | Copied from | sha256 |
|---|---|---|
| `generate_models.py` | `bi_modeling_playbook/engine/generate_models.py` | `c40b1d61fb673d78c08aa1faa4ddeb128aa72d1744d410fe1246d1841f80d8ce` |
| `spec.yaml` | `bi_modeling_playbook/scaffold/runs/coldstart_v6z_009/looker/06_looker_stepF_10x/spec.yaml` | `8b34111dda9766fae6eddb4188809106831406e45c53462795078739909f3939` |

Copied 2026-08-12 on branch `v6z-okf-projector`.

### The generator copy is of the WORKING TREE, not of HEAD

`bi_modeling_playbook/engine/generate_models.py` was **uncommitted-modified** when
copied. Last commit touching it: `ffe555bb4298caf8790875efba0b177e6a41b325`
("engine: a window measure does not need its own explore, and an explore is the
scarce thing"), plus **328 insertions / 67 deletions** of uncommitted work on top
— the "4 explores → 2" consolidation (joined rollups + native PoP).

This matters for anyone reproducing: checking out `ffe555b` will **not** give you
the file copied here.

## Faithful-copy check

The plan gated `gen_okf` on proving the copy behaves identically to the original.

**Attempt 1 — copy vs run 009's archived `generated/`: DIFFERENCES.** Not a copy
fault. The archive was produced by an *older* generator; the delta is exactly the
uncommitted consolidation above (archive has standalone `explore:` statements for
window/unpivot views; the current generator folds them into the root explore as
`join:` blocks, and does not emit `cs_ddl.sql`). Diffing new code against an old
archive tests generator drift, not copy fidelity — the wrong assertion.

**Attempt 2 — original vs copy, same spec, same flags: IDENTICAL.** 18 files,
`diff -r` empty. This is the correct test and it passes; the copy is byte-identical
to its source, so behavioural identity holds by construction.

```
python bi_modeling_playbook/engine/generate_models.py --spec okf-emitter/spec.yaml --out /tmp/gen_orig
python okf-emitter/generate_models.py                 --spec okf-emitter/spec.yaml --out /tmp/gen_copy
diff -r /tmp/gen_orig /tmp/gen_copy     # empty
```

## Changes made here

- `generate_models.py` — a new `gen_okf()` emitter and its CLI target. **No
  existing function is modified**; `validate_spec` and the shared helpers
  (`pk_cols`, `table_singular`, `col_desc`, …) are used as-is.
- `spec.yaml` — retargeted `project` / `dataset` at the demo copy
  (`royston-dev-8253` / `cymbal_bank_v6z_scaffold_demo_copy`). No other key
  changed; the 13 tables are exactly those of the copy.

## Known drift

This copy will not receive fixes made to the real generator. That is the accepted
cost of isolation for a single run. Upstreaming `gen_okf` into
`bi_modeling_playbook/engine/generate_models.py` is future work, not a standing
obligation — and should start by re-running the faithful-copy check above, since
the working tree will have moved on.
