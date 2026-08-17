"""Imports the 38-question Core Golden Suite and registers the two local agents in Prism."""

import os
from pathlib import Path
import yaml

from prism.common.schemas.assertion import AssertionType
from prism.server.db import SessionLocal
from prism.server.models.agent import Agent
from prism.server.models.assertion import Assertion
from prism.server.models.example import Example
from prism.server.models.suite import TestSuite

PROJECT = os.environ.get("OKF_PROJECT", os.environ.get("GOOGLE_CLOUD_PROJECT", "your-gcp-project-id"))
DATASET = os.environ.get("OKF_BQ_DATASET", os.environ.get("BIGQUERY_DATASET", "your-bigquery-dataset"))

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent
YAML_PATH = REPO_ROOT / "eval" / "core.yaml"


def import_suite_and_agents():
    if not YAML_PATH.exists():
        raise FileNotFoundError(f"Cannot find core.yaml at {YAML_PATH}")

    with open(YAML_PATH, "r") as f:
        data = yaml.safe_load(f)

    questions = data.get("questions", [])
    print(f"Loaded {len(questions)} questions from {YAML_PATH}")

    with SessionLocal() as session:
        # 1. Register Agents
        existing_a1 = session.query(Agent).filter(Agent.name == "okf_bundle_agent").first()
        if not existing_a1:
            a1 = Agent(
                name="okf_bundle_agent",
                project_id="local",
                location="local",
                agent_resource_id="okf_bundle_agent",
                datasource_config={"tables": [f"{PROJECT}.{DATASET}.*"]},
            )
            session.add(a1)
            print("Registered Agent 1: okf_bundle_agent (Port 8000)")
        else:
            print("Agent 1 already exists: okf_bundle_agent")

        existing_a2 = session.query(Agent).filter(Agent.name == "knowledge_catalog_agent").first()
        if not existing_a2:
            a2 = Agent(
                name="knowledge_catalog_agent",
                project_id="local",
                location="local",
                agent_resource_id="knowledge_catalog_agent",
                datasource_config={"tables": [f"{PROJECT}.{DATASET}.*"]},
            )
            session.add(a2)
            print("Registered Agent 2: knowledge_catalog_agent (Port 8001)")
        else:
            print("Agent 2 already exists: knowledge_catalog_agent")

        # 2. Create / Recreate Test Suite
        suite_name = "Core Golden Suite (38 Questions)"
        existing_suite = session.query(TestSuite).filter(TestSuite.name == suite_name).first()
        if existing_suite:
            print(f"Suite '{suite_name}' exists (id={existing_suite.id}), removing old examples to refresh...")
            session.delete(existing_suite)
            session.commit()

        suite = TestSuite(
            name=suite_name,
            description=f"38-question Golden Core Suite evaluating Local OKF vs Dataplex KC on dataset {PROJECT}.{DATASET}",
            tags={"dataset": DATASET, "suite": "core", "version": "v6z"},
        )
        session.add(suite)
        session.flush()

        # 3. Create Examples & Assertions
        for idx, q_item in enumerate(questions, 1):
            q_text = q_item.get("question", "")
            q_text_rendered = q_text.replace("{project}", PROJECT).replace("{dataset}", DATASET)
            tier = q_item.get("tier", "unknown")
            logical_id = f"core_q{idx:02d}_{tier}"

            example = Example(
                test_suite_id=suite.id,
                logical_id=logical_id,
                question=q_text_rendered,
            )
            session.add(example)
            session.flush()

            raw_asserts = q_item.get("asserts", [])
            for raw_a in raw_asserts:
                a_type_str = raw_a.get("type", "")
                if a_type_str == "ai-judge":
                    val = raw_a.get("value", "")
                    # Resolve placeholders
                    val = val.replace("{project}", PROJECT).replace("{dataset}", DATASET)
                    session.add(
                        Assertion(
                            example_id=example.id,
                            type=AssertionType.AI_JUDGE,
                            weight=1.0,
                            params={"value": val},
                        )
                    )
                elif a_type_str == "data-check-row-count":
                    val = raw_a.get("value")
                    tol = raw_a.get("tolerance", 0)
                    session.add(
                        Assertion(
                            example_id=example.id,
                            type=AssertionType.DATA_CHECK_ROW_COUNT,
                            weight=1.0,
                            params={"value": val, "tolerance": tol} if val is not None else {},
                        )
                    )
                elif a_type_str == "data-check-row":
                    cols = raw_a.get("value", {})
                    session.add(
                        Assertion(
                            example_id=example.id,
                            type=AssertionType.DATA_CHECK_ROW,
                            weight=1.0,
                            params={"columns": cols},
                        )
                    )
                elif a_type_str == "text-contains":
                    val = raw_a.get("value", "")
                    session.add(
                        Assertion(
                            example_id=example.id,
                            type=AssertionType.TEXT_CONTAINS,
                            weight=1.0,
                            params={"value": val},
                        )
                    )

        session.commit()
        print(f"Successfully imported Suite '{suite.name}' (id={suite.id}) with {len(questions)} examples!")


if __name__ == "__main__":
    import_suite_and_agents()
