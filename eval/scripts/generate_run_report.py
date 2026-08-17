"""Generates a complete diagnostic report for Run ID 6."""

import json
from prism.server.db import SessionLocal
from prism.server.models.run import Run, Trial
from prism.server.models.assertion import AssertionResult, AssertionSnapshot
from prism.server.models.agent import Agent
from prism.server.models.snapshot import ExampleSnapshot

with SessionLocal() as session:
    run = session.query(Run).filter(Run.id == 6).first()
    if not run:
        print("Run ID 6 not found!")
        exit(1)
        
    agent = session.query(Agent).filter(Agent.id == run.agent_id).first()
    trials = session.query(Trial).filter(Trial.run_id == run.id).order_by(Trial.id.asc()).all()
    
    total_trials = len(trials)
    completed_trials = sum(1 for t in trials if t.status.value in ("COMPLETED", "FAILED", "ERROR"))
    
    passed_trials = 0
    failed_trials = 0
    
    trial_records = []
    
    for idx, t in enumerate(trials, 1):
        ex_snap = session.query(ExampleSnapshot).filter(ExampleSnapshot.id == t.example_snapshot_id).first()
        question = ex_snap.question if ex_snap else "Unknown question"
        logical_id = ex_snap.logical_id if ex_snap else f"q_{idx}"
        
        a_results = session.query(AssertionResult).filter(AssertionResult.trial_id == t.id).all()
        all_passed = True if a_results else False
        assert_summaries = []
        for ar in a_results:
            a_snap = session.query(AssertionSnapshot).filter(AssertionSnapshot.id == ar.assertion_snapshot_id).first()
            a_type = a_snap.type if a_snap else "unknown"
            if not ar.passed:
                all_passed = False
            assert_summaries.append({
                "type": str(a_type),
                "passed": ar.passed,
                "score": ar.score,
                "reasoning": ar.reasoning,
                "error": ar.error_message,
            })
            
        if all_passed and a_results:
            passed_trials += 1
        else:
            failed_trials += 1
            
        final_answer = t.output_text or ""
        generated_sql = []
        if t.trace_results:
            for item in t.trace_results:
                sys_msg = item.get("system_message", {})
                if "data" in sys_msg:
                    sql = sys_msg["data"].get("generated_sql")
                    if sql:
                        generated_sql.append(sql)
                        
        trial_records.append({
            "trial_id": t.id,
            "logical_id": logical_id,
            "question": question,
            "status": str(t.status.value),
            "all_passed": all_passed,
            "final_answer": final_answer.strip()[:300],
            "generated_sql": generated_sql,
            "assertions": assert_summaries,
        })

    print(f"==================================================")
    print(f"RUN EVALUATION REPORT (Run ID: {run.id})")
    print(f"==================================================")
    print(f"Agent: {agent.name if agent else 'Unknown'} (ID: {run.agent_id})")
    print(f"Run Status: {run.status.value}")
    print(f"Total Trials: {total_trials}")
    print(f"Completed Trials: {completed_trials}")
    print(f"Trials Passed: {passed_trials}/{total_trials} ({passed_trials/total_trials*100:.1f}%)")
    print(f"Trials Failed: {failed_trials}/{total_trials}")
    print(f"==================================================\n")
    
    print("--- Detailed Breakdown by Question ---")
    for tr in trial_records:
        icon = "✅ PASS" if tr["all_passed"] else "❌ FAIL"
        print(f"\n{icon} [{tr['logical_id']}] {tr['question']}")
        print(f"   Status: {tr['status']}")
        if tr['generated_sql']:
            print(f"   SQL: {tr['generated_sql'][0]}")
        print(f"   Answer: {tr['final_answer']}")
        for a in tr["assertions"]:
            a_icon = "  ✓" if a["passed"] else "  ✗"
            print(f"   {a_icon} [{a['type']}] Score: {a['score']} - {a['reasoning'] or a['error']}")
