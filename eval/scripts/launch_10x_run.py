"""Trigger 10x evaluation run for knowledge_catalog_agent."""

from prism.server.config import settings
from prism.server.db import SessionLocal
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.clients.gen_ai_client import GenAIClient

with SessionLocal() as session:
    suite_repo = SuiteRepository(session)
    example_repo = ExampleRepository(session)
    snapshot_service = SnapshotService(session, suite_repo, example_repo)
    client = GeminiDataAnalyticsClient(project="projects/local/locations/local")
    
    import os
    project = settings.gcp_genai_project or os.environ.get("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id")
    location = settings.gcp_genai_location or "us-central1"
    gen_ai_client = GenAIClient(project=project, location=location)
    
    service = ExecutionService(
        session=session,
        snapshot_service=snapshot_service,
        client=client,
        gen_ai_client=gen_ai_client,
    )
    
    # agent_id: 3 (knowledge_catalog_agent)
    # test_suite_id: 2 (core_10x)
    print("Creating Run for Agent ID 3 (knowledge_catalog_agent) against Suite ID 2 (core_10x)...")
    run = service.create_run(agent_id=3, test_suite_id=2, concurrency=4)
    print(f"Run successfully created! Run ID: {run.id}, Status: {run.status}, Concurrency: {run.concurrency}")
    print(f"Total Trials generated: {len(run.trials)}")
