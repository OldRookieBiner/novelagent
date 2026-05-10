#!/usr/bin/env python3
"""
Test script to reproduce the workflow SSE issue.
This simulates the "开始规划" button click and monitors the SSE stream.
"""
import asyncio
import httpx
import json
import sys

API_BASE = "http://localhost:8000"

async def test_workflow_run(project_id: int):
    """Test the workflow/run endpoint and capture all events."""

    # First, login to get a session token
    async with httpx.AsyncClient() as client:
        # Login
        login_resp = await client.post(
            f"{API_BASE}/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        if login_resp.status_code != 200:
            print(f"Login failed: {login_resp.status_code}")
            return

        token = login_resp.json().get("access_token")
        print(f"Logged in, token: {token[:20]}...")

        # Call workflow/run
        headers = {
            "Authorization": f"Basic {token}:",
            "Accept": "text/event-stream",
        }

        print(f"\nCalling POST /api/projects/{project_id}/workflow/run")
        print("=" * 60)

        events = []
        error_events = []

        async with client.stream(
            "POST",
            f"{API_BASE}/api/projects/{project_id}/workflow/run",
            headers=headers,
            timeout=300.0,
        ) as response:
            print(f"Response status: {response.status_code}")

            if response.status_code != 200:
                body = await response.aread()
                print(f"Error response: {body.decode()}")
                return

            async for line in response.aiter_lines():
                if not line:
                    continue

                print(f"RAW: {line}")

                if line.startswith("event:"):
                    event_type = line[6:].strip()
                elif line.startswith("data:"):
                    data_str = line[5:].strip()
                    try:
                        data = json.loads(data_str)
                        events.append({"event": event_type, "data": data})

                        if event_type == "error":
                            error_events.append(data)
                            print(f"!!! ERROR EVENT: {data}")
                        elif event_type == "done":
                            print(f"!!! DONE EVENT: {data}")
                        elif event_type == "waiting":
                            print(f"!!! WAITING EVENT: {data}")
                    except json.JSONDecodeError:
                        events.append({"event": event_type, "data": data_str})

        print("\n" + "=" * 60)
        print(f"Total events: {len(events)}")
        print(f"Error events: {len(error_events)}")

        # Print event types
        event_types = {}
        for e in events:
            t = e["event"]
            event_types[t] = event_types.get(t, 0) + 1

        print(f"Event types: {event_types}")

        if error_events:
            print("\nERROR DETAILS:")
            for err in error_events:
                print(f"  - {err}")

if __name__ == "__main__":
    project_id = int(sys.argv[1]) if len(sys.argv) > 1 else 70
    asyncio.run(test_workflow_run(project_id))
