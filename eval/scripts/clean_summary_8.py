"""High-level summary of Run ID 8."""

from collections import defaultdict
from prism.server.db import SessionLocal
from prism.server.models.run import Run, Trial
from prism.server.models.assertion import AssertionResult, AssertionSnapshot
from prism.server.models.agent import Agent
from prism.server.models.snapshot import ExampleSnapshot

with SessionLocal() as session:
    run = session.query(Run).filter(Run.id == 8).first()
    agent = session.query(Agent).filter(Agent.id == run.agent_id).first()
    trials = session.query(Trial).filter(Trial.run_id == run.id).all()
    
    total = len(trials)
    completed = sum(1 for t in trials if t.status.value in ("COMPLETED", "FAILED", "ERROR"))
    in_flight = total - completed
    
    passed_trials = 0
    failed_trials = 0
    total_asserts = 0
    passed_asserts = 0
    
    question_stats = defaultdict(lambda: {"total": 0, "passed": 0})
    
    for t in trials:
        ex_snap = session.query(ExampleSnapshot).filter(ExampleSnapshot.id == t.example_snapshot_id).first()
        question = ex_snap.question if ex_snap else "Unknown question"
        question_stats[question]["total"] += 1
        
        a_results = session.query(AssertionResult).filter(AssertionResult.trial_id == t.id).all()
        all_passed = True if a_results else False
        for ar in a_results:
            total_asserts += 1
            if ar.passed:
                passed_asserts += 1
            else:
                all_passed = False
                
        if all_passed and a_results:
            passed_trials += 1
            question_stats[question]["passed"] += 1
        else:
            failed_trials += 1
            
    print(f"Agent: {agent.name}")
    print(f"Run ID: {run.id}")
    print(f"Status: {run.status.value}")
    print(f"Total Trials: {total}")
    print(f"Completed Trials: {completed} ({in_flight} remaining)")
    print(f"Trials Passed: {passed_trials}/{total} ({passed_trials/total*100:.1f}%)")
    print(f"Total Assertions Evaluated: {total_asserts}")
    print(f"Assertions Passed: {passed_asserts}/{total_asserts} ({passed_asserts/total_asserts*100:.1f}%)" if total_asserts > 0 else "0/0")
    print(f"Distinct Questions: {len(question_stats)}")
    
    # 100% pass questions count vs <100%
    perfect_q = sum(1 for q, stat in question_stats.items() if stat["passed"] == stat["total"])
    print(f"Questions with 10/10 (100%) Pass Rate: {perfect_q} / {len(question_stats)} ({perfect_q/len(question_stats)*100:.1f}%)")
    print(f"Questions with Failures: {len(question_stats) - perfect_q} / {len(question_stats)}")
