"""Smoke test both Agent 1 (Local OKF) and Agent 2 (Dataplex KC)."""

import asyncio
from google.genai import types
from google.adk.runners import InMemoryRunner

from app.agent_okf import root_agent as okf_agent
from app.agent_kc import root_agent as kc_agent


async def test_agent(agent, name: str, question: str):
    print(f"\n==========================================")
    print(f"Testing {name}: '{question}'")
    print(f"==========================================")
    runner = InMemoryRunner(agent=agent, app_name="smoke_test")
    session = await runner.session_service.create_session(app_name="smoke_test", user_id="smoke_user")
    
    text = ""
    tool_calls = []
    try:
        async for event in runner.run_async(
            user_id="smoke_user",
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=question)]),
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if getattr(part, "function_call", None):
                        print(f"  [Tool Call] {part.function_call.name}({part.function_call.args})")
                        tool_calls.append(part.function_call.name)
                    if getattr(part, "function_response", None):
                        print(f"  [Tool Response] {part.function_response.name}")
                    if getattr(part, "text", None):
                        text += part.text
        print(f"Final Answer:\n{text.strip()}")
        print(f"Total tool calls: {len(tool_calls)}")
    except Exception as e:
        print(f"Error testing {name}: {e}")


async def main():
    q = "How many customers do we have in total?"
    print("--- 1. Testing Agent 1 (Local OKF) ---")
    await test_agent(okf_agent, "Agent 1 (Local OKF)", q)

    print("\n--- 2. Testing Agent 2 (Dataplex KC) ---")
    await test_agent(kc_agent, "Agent 2 (Dataplex KC)", q)


if __name__ == "__main__":
    asyncio.run(main())
