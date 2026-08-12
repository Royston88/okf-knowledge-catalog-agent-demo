"""Local LLM-as-judge for `sql_accuracy`."""

from google import genai
from google.genai import types
from pydantic import BaseModel
import json

class _Verdict(BaseModel):
    score: int  # 1 (completely wrong/missing) to 5 (perfect/equivalent)
    explanation: str

def extract_sql(agent_data):
    if not agent_data or "turns" not in agent_data:
        return None
    for turn in agent_data["turns"]:
        for event in turn.get("events", []):
            content = event.get("content") or {}
            parts = content.get("parts") or []
            for part in parts:
                if "function_call" in part:
                    fcall = part["function_call"]
                    if fcall.get("name") == "execute_sql":
                        args = fcall.get("args") or {}
                        return args.get("sql_query")
    return None

def evaluate(instance):
    golden_sql = instance.get("golden_sql")
    agent_data = instance.get("agent_data")
    
    if not golden_sql:
        return {"score": 5, "explanation": "No golden SQL provided for this case. Skipping check."}
        
    executed_sql = extract_sql(agent_data)
    
    if not executed_sql:
        return {
            "score": 1, 
            "explanation": "Agent did not execute any SQL query via the execute_sql tool."
        }
        
    rubric = (
        "Compare the executed SQL query against the Golden SQL query. "
        "Assess if they are semantically equivalent and would return the same result "
        "given the same schema. "
        "Grade on a scale of 1-5:\n"
        "5: Semantically identical or equivalent (e.g., minor alias differences, same logic).\n"
        "3-4: Mostly correct but has minor issues (e.g. missing de-duplication, wrong join column but similar logic).\n"
        "1-2: Incorrect or completely different logic (e.g. queried wrong tables, wrong aggregations).\n"
    )
    
    prompt = (
        f"You are an expert database administrator and QA evaluator. {rubric}\n"
        f"Golden SQL:\n```sql\n{golden_sql}\n```\n\n"
        f"Executed SQL:\n```sql\n{executed_sql}\n```\n"
    )
    
    try:
        client = genai.Client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",  # Using a reliable model
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=_Verdict,
            ),
        )
        verdict = response.parsed
        if verdict is None:
            return {"score": 0, "explanation": response.text or "Model returned empty response."}
        return {"score": max(1, min(5, verdict.score)), "explanation": verdict.explanation}
    except Exception as e:
        return {"score": 0, "explanation": f"Error running LLM judge: {e}"}
