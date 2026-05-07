"""Test the deployed REWE Marketing Agent via REST API."""
import json
import requests
import google.auth
import google.auth.transport.requests

creds, project = google.auth.default()
auth_req = google.auth.transport.requests.Request()
creds.refresh(auth_req)
token = creds.token

BASE = "https://us-east1-aiplatform.googleapis.com/v1"
ENGINE = "projects/710258046947/locations/us-east1/reasoningEngines/932596966586580992"
HEADERS = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# 1. Create session
print("=== Creating session ===")
resp = requests.post(
    f"{BASE}/{ENGINE}:query",
    headers=HEADERS,
    json={"class_method": "create_session", "input": {"user_id": "test_grilling"}},
)
session_data = resp.json().get("output", {})
session_id = session_data.get("id", "") if isinstance(session_data, dict) else str(session_data)
print(f"Session ID: {session_id}")

# 2. Use streamQuery SSE endpoint
print("\n=== Sending query via streamQuery (SSE) ===")
resp = requests.post(
    f"{BASE}/{ENGINE}:streamQuery",
    headers=HEADERS,
    json={
        "class_method": "streaming_agent_run_with_events",
        "input": {
            "user_id": "test_grilling",
            "session_id": session_id,
            "message": "Hi! I'm customer CUST001. Write me a blog post about summer grilling tips.",
        },
    },
    stream=True,
    timeout=180,
)
print(f"Status: {resp.status_code}")

full_text = []
for line in resp.iter_lines(decode_unicode=True):
    if not line or not line.startswith("data:"):
        continue
    data_str = line[len("data:"):].strip()
    if data_str == "[DONE]":
        break
    try:
        event = json.loads(data_str)
        # Extract text from various event shapes
        output = event.get("output", event)
        if isinstance(output, dict):
            content = output.get("content", {})
            parts = content.get("parts", []) if isinstance(content, dict) else []
            for part in parts:
                if isinstance(part, dict) and "text" in part:
                    full_text.append(part["text"])
                    print(part["text"][:200], end="", flush=True)
    except json.JSONDecodeError:
        pass

if not full_text:
    print("\n[No text extracted from SSE stream. Raw last lines:]")
    # Print raw response for debugging
    print(resp.text[:3000] if hasattr(resp, 'text') else "No text available")

print(f"\n\n=== Done. Total text length: {sum(len(t) for t in full_text)} chars ===")
