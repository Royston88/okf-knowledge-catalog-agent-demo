"""Script to monitor run status and extract detailed evaluation reports."""

from prism.server.db import SessionLocal
from prism.server.models.run import Run, RunStatus, Trial
from prism.server.models.assertion import AssertionResult
from prism.server.models.agent import Agent
from prism.server.models.suite import TestSuite
from prism.server.models.snapshot import ExampleSnapshot, TestSuiteSnapshot

with SessionLocal() as session:
    runs = session.query(Run).order_by(Run.created_at.desc()).all()
    print(f"Total Runs in DB: {len(runs)}\n")
    for r in runs:
        agent = session.query(Agent).filter(Agent.id == r.agent_id).first()
        agent_name = agent.name if agent else f"Agent {r.agent_id}"
        
        trials = session.query(Trial).filter(Trial.run_id == r.id).all()
        total_trials = len(trials)
        completed_trials = sum(1 for t in trials if t.status in ("COMPLETED", "FAILED", "ERROR"))
        pending_trials = sum(1 for t in trials if t.status in ("PENDING", "RUNNING"))
        
        passed_asserts = 0
        total_asserts = 0
        for t in trials:
            a_results = session.query(AssertionResult).filter(AssertionResult.trial_id == t.id).all()
            for ar in a_results:
                total_asserts += 1
                if ar.passed:
                    passed_asserts += 1
                    
        pass_rate = (passed_asserts / total_asserts * 100) if total_asserts > 0 else 0.0
        
        print(f"Run ID: {r.id}")
        print(f"Agent: {agent_name} (ID: {r.agent_id})")
        print(f"Status: {r.status}")
        print(f"Created At: {r.created_at}")
        print(f"Progress: {completed_trials}/{total_trials} trials completed ({pending_trials} pending/running)")
        print(f"Assertion Pass Rate: {passed_asserts}/{total_asserts} ({pass_rate:.1f}%)")
        print("-" * 60)
