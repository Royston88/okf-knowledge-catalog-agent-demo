# `pull.ts` is retired — deleted in the Phase 5 commit

It had two jobs and both are gone.

**Reconstruction is obsolete.** It pulled into `.staging/`, ran `fromStaging`
over each file and wrote the result into `catalog/`. The differ does not need
that, because it compares **forward**: `expected` is built from the bundle by
the very function the push uses, and is matched against a live `getEntry`. A
reverse mapping is lossy, and a reverse-mapped diff is blind to exactly the
fields the reverse mapping does not know about.

**Refresh belongs to the mirrored tier**, which is field-scoped and cannot touch
an owned field — see `okf-review/mirror.py`.

**Deleting it is the point, not a tidy-up.** It was the last code path that
could write into `okf-bundle/`, and while it existed rule 3 ("pull never writes
an owned field") was a convention enforced by everyone remembering the note in
DESIGN §5: *"push from `okf-bundle/`, not from a pulled tree"*. Now it is
structural — there is no code that writes the bundle from the catalog.

What made that convention dangerous rather than merely untidy was measured in
Phase 3. A pristine `kcmd pull` of our own concepts returns:

```yaml
type: dataplex-types.global.generic     # OVERWRITES the OKF type `Grain Rule`
x-kcmd:
  aspects:
    royston-dev-8253.us.okf:
      okf_type: Grain Rule              # the source's vocabulary, DEMOTED
```

…with an **empty body** (defect 2) and the entry renamed into the KB source's
`<group>/<project>/<location>/<path>` form. One `pull` over `okf-bundle/` would
have destroyed the OKF layer of every concept it touched.

## If you need to inspect a raw pull by hand

`fromStaging()` in `okf.ts` is KEPT and still works. Pull into a scratch
directory with the kcmd CLI directly and read the result there — never into
`okf-bundle/`:

```bash
mkdir -p /tmp/pull-ws && cp okf-kb-workspace/catalog.yaml /tmp/pull-ws/
cd /tmp/pull-ws && node ../../kcmd/build/ts/tool/tool/main.js pull
```

## To answer "did the catalog change"

```bash
bun kcmd/demo/okf/drift.ts          # 0 = no drift, 1 = drift, 2 = tool error
```
