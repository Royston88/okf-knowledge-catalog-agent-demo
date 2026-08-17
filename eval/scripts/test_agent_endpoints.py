"""Tests both local Agent 1 and Agent 2 via Prism's _ask_question_local logic."""

from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient

client = GeminiDataAnalyticsClient(project="projects/local/locations/local")

print("--- Testing Agent 1: okf_bundle_agent (Port 8000) ---")
resp1 = client.ask_question(
    agent_id="projects/local/locations/local/dataAgents/okf_bundle_agent",
    question="How many customers do we have in total?",
)
print("Agent 1 Total Duration:", resp1.duration.total_duration if resp1.duration else None)
print("Agent 1 Error:", resp1.error_message)
print("Agent 1 Messages count:", len(resp1.response))
for msg in resp1.response:
    sys_msg = msg.get("system_message", {})
    if "text" in sys_msg:
        print(" [Text]:", sys_msg["text"].get("parts"))
    if "data" in sys_msg:
        print(" [Data]:", sys_msg["data"])

print("\n--- Testing Agent 2: knowledge_catalog_agent (Port 8001) ---")
resp2 = client.ask_question(
    agent_id="projects/local/locations/local/dataAgents/knowledge_catalog_agent",
    question="How many customers do we have in total?",
)
print("Agent 2 Total Duration:", resp2.duration.total_duration if resp2.duration else None)
print("Agent 2 Error:", resp2.error_message)
print("Agent 2 Messages count:", len(resp2.response))
for msg in resp2.response:
    sys_msg = msg.get("system_message", {})
    if "text" in sys_msg:
        print(" [Text]:", sys_msg["text"].get("parts"))
    if "data" in sys_msg:
        print(" [Data]:", sys_msg["data"])
