"""Test the deployed REWE Marketing Agent via the official Google Cloud SDK.

Uses vertexai.agent_engines.AgentEngine with the streaming_agent_run_with_events
method, which is the async_stream API that works correctly with the gRPC transport.
"""
import asyncio
import json

import vertexai
from vertexai.agent_engines import AgentEngine

# --- Configuration ---
PROJECT_ID = "sa-learning-1"
LOCATION = "us-east1"
ENGINE_ID = "932596966586580992"


async def main():
    # Initialize Vertex AI
    vertexai.init(project=PROJECT_ID, location=LOCATION)

    # Load the deployed Agent Engine by resource name
    print("=== Loading Agent Engine ===")
    agent = AgentEngine(
        f"projects/{PROJECT_ID}/locations/{LOCATION}/reasoningEngines/{ENGINE_ID}"
    )
    print(f"Agent loaded: {agent.resource_name}")

    # 1. Create session
    print("\n=== Creating session ===")
    session = agent.create_session(user_id="test_grilling")
    session_id = session.get("id", "") if isinstance(session, dict) else str(session)
    print(f"Session ID: {session_id}")

    # 2. Stream the agent response.
    #    streaming_agent_run_with_events is an async_stream method — it returns
    #    an async generator that yields parsed event dicts from the gRPC stream.
    print("\n=== Streaming agent response ===")
    full_text = []

    async for event in agent.streaming_agent_run_with_events(
        request_json=json.dumps({
            "user_id": "test_grilling",
            "session_id": session_id,
            "message": {
                "role": "user",
                "parts": [
                    {"text": "Hi! I'm customer CUST001. Write me a blog post about summer grilling tips."}
                ],
            },
        })
    ):
        # Each event is a parsed dict from the SSE stream.
        # Agent text responses are in: events[].content.parts[].text
        if not isinstance(event, dict):
            continue
        for ev in event.get("events", []):
            if not isinstance(ev, dict):
                continue
            content = ev.get("content")
            if not isinstance(content, dict):
                continue
            for part in content.get("parts", []):
                if not isinstance(part, dict):
                    continue
                # Skip tool calls and tool responses
                if part.get("function_call") or part.get("function_response"):
                    continue
                # Skip pure thinking parts (no text content)
                if (part.get("thought") or part.get("thought_signature")) and "text" not in part:
                    continue
                text = part.get("text", "")
                if text.strip():
                    full_text.append(text)
                    print(text[:300], end="", flush=True)

    print(f"\n\n=== Done. Total text length: {sum(len(t) for t in full_text)} chars ===")


if __name__ == "__main__":
    asyncio.run(main())
