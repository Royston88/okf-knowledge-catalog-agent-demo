"""Inspect trials with empty responses in Run 6."""

import json
from prism.server.db import SessionLocal
from prism.server.models.run import Run, Trial
from prism.server.models.snapshot import ExampleSnapshot

with SessionLocal() as session:
    run = session.query(Run).filter(Run.id == 6).first()
    trials = session.query(Trial).filter(Trial.run_id == run.id).all()
    
    for t in trials:
        if not t.output_text or t.output_text.strip() == "":
            ex_snap = session.query(ExampleSnapshot).filter(ExampleSnapshot.id == t.example_snapshot_id).first()
            print(f"==================================================")
            print(f"Trial ID: {t.id}")
            print(f"Question: {ex_snap.question if ex_snap else 'Unknown'}")
            print(f"Logical ID: {ex_snap.logical_id if ex_snap else 'Unknown'}")
            print(f"Status: {t.status}")
            print(f"Started At: {t.started_at}")
            print(f"Completed At: {t.completed_at}")
            print(f"Duration MS: {t.duration_ms}")
            print(f"Error Message: {t.error_message}")
            print(f"Error Traceback: {t.error_traceback}")
            print(f"Failed Stage: {t.failed_stage}")
            print(f"Retry Count: {t.retry_count}")
            print(f"Trace Results Count: {len(t.trace_results) if t.trace_results else 0}")
            print(f"Trace Results: {json.dumps(t.trace_results, indent=2) if t.trace_results else 'None'}")
            print(f"==================================================\n")
