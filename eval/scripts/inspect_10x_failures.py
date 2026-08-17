"""Categorize failures in Run 8."""

from collections import defaultdict
from prism.server.db import SessionLocal
from prism.server.models.run import Run, Trial
from prism.server.models.assertion import AssertionResult, AssertionSnapshot
from prism.server.models.snapshot import ExampleSnapshot

with SessionLocal() as session:
    run = session.query(Run).filter(Run.id == 8).first()
    trials = session.query(Trial).filter(Trial.run_id == run.id).all()
    
    question_failures = defaultdict(list)
    
    for t in trials:
        a_results = session.query(AssertionResult).filter(AssertionResult.trial_id == t.id).all()
        for ar in a_results:
            if not ar.passed:
                ex_snap = session.query(ExampleSnapshot).filter(ExampleSnapshot.id == t.example_snapshot_id).first()
                q = ex_snap.question if ex_snap else "Unknown"
                a_snap = session.query(AssertionSnapshot).filter(AssertionSnapshot.id == ar.assertion_snapshot_id).first()
                question_failures[q].append({
                    "trial_id": t.id,
                    "type": str(a_snap.type if a_snap else "unknown"),
                    "score": ar.score,
                    "reason": ar.reasoning or ar.error_message,
                    "answer": t.output_text[:120] if t.output_text else "None",
                })
                
    print(f"Total Unique Questions with Failures: {len(question_failures)}\n")
    for q, fails in sorted(question_failures.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"Question: '{q}' ({len(fails)} failures / 10 runs)")
        for f in fails[:2]:
            print(f" - [{f['type']}] Score: {f['score']} | Ans: {f['answer']}")
            print(f"   Reason: {f['reason']}")
        print("-" * 60)
