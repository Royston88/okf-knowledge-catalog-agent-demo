// The push planner: pull -> compare -> stage only what differs.
//
// Shared by both push scripts so `drift` and `push` cannot disagree about what
// constitutes a difference — they call the same comparison. `drift` is the
// planner with the apply step omitted.
//
// This satisfies the second of `sync.ts`'s two TODOs ("Track what has changed
// and do minimal update") and kcmd spec §3.3's fail-fast, both from OUTSIDE the
// tool: we control `.staging/`, so "skip the unchanged" is just not staging
// them, and kcmd stays unmodified — which keeps the Phase 3 interop claim
// intact.
//
// WHAT IT IS AND IS NOT FOR. The original argument was that a no-op push must
// be a genuine no-op or the server timestamps degrade to a sound negative test.
// MEASURED, that argument does not hold as stated: Dataplex's per-aspect
// `updateTime` is already content-addressed — 14 `modifyEntry` calls with
// byte-identical data moved 0 of 241 aspect timestamps. What a full re-push
// DOES move is the ENTRY-level `updateTime`, on 14 of 14. So the planner buys:
//
//   - an exact entry-level signal, not only an exact per-aspect one;
//   - fail-fast: nothing is written until the comparison has run, so a
//     third-party edit is seen BEFORE it is overwritten;
//   - no pointless writes to a live catalog;
//   - a `--force` flag that finally means something. It is declared at
//     sync.ts:227 and read nowhere; here it is read, on our side of the line.
//
// The read is already paid for. `sync.ts:297` issues a `lookupEntry` per entry
// to decide create-vs-modify and then discards the result without comparing it.
// We are using a fetch that already happens, earlier, and for its content.

import { buildPlan } from './drift';
import { ChannelFinding, ConceptPlan, conflicts } from './plan';

export interface Plan {
  /**
   * Whether the plan is authoritative. `false` under `OKF_NO_PLAN`, in which
   * case `stage` is empty and MEANS NOTHING — callers must stage everything.
   * An explicit flag rather than `stage.size > 0`, because "the plan says
   * nothing needs staging" and "there is no plan" are opposite instructions and
   * an empty set cannot tell them apart. Getting that backwards would make a
   * fully-converged catalog trigger a full re-push, silently.
   */
  enabled: boolean;
  /** bundle-relative paths (no `.md`) that must be staged. */
  stage: Set<string>;
  plans: ConceptPlan[];
  conflicts: ChannelFinding[];
  skipped: number;
}

/**
 * Decide what to stage for one track.
 *
 * CONSERVATIVE BY CONSTRUCTION, because the risk this introduces is the repo's
 * signature failure: a false no-change verdict silently drops a real change. So
 * `needsPush` starts true and is only cleared by a complete, successful,
 * structural match; a read failure, an absent entry, an unrecognised shape and
 * an unparsed concept all stage. `OKF_NO_PLAN=1` disables planning entirely and
 * stages everything, which is the escape hatch if the comparison is ever
 * doubted.
 */
export async function planPush(track: 'A' | 'B', force: boolean): Promise<Plan> {
  if (process.env.OKF_NO_PLAN) {
    console.log('OKF_NO_PLAN set — staging everything, no comparison');
    return { enabled: false, stage: new Set(), plans: [], conflicts: [], skipped: 0 };
  }
  const { plans, readFailures } = await buildPlan({ tracks: [track] });
  const stage = new Set(plans.filter((p) => p.needsPush).map((p) => p.rel));
  const conf = conflicts(plans);

  console.log(`planner: ${plans.length} concept(s) on Track ${track}; ` +
              `${stage.size} differ, ${plans.length - stage.size} identical` +
              (readFailures.length ? `; ${readFailures.length} unreadable (staged)` : ''));

  if (conf.length && !force) {
    for (const f of conf) {
      console.error(`CONFLICT  ${f.concept}  ${f.channel}  [${f.updateTime}]\n` +
                    `          ${f.detail}`);
    }
    throw new Error(
      `${conf.length} owned channel(s) were written by something other than this ` +
      `push since the last recorded sweep. ABORTING THE WHOLE PUSH — a partial ` +
      `projection is worse than none. Inspect with \`drift.ts\`, then re-run with ` +
      `--force to overwrite deliberately.`);
  }
  if (conf.length) {
    console.warn(`--force: overwriting ${conf.length} third-party edit(s)`);
  }
  return { enabled: true, stage, plans, conflicts: conf, skipped: plans.length - stage.size };
}
