"""Integration test for SPEC.md Acceptance Scenario 1.

Register two agents. One sends a task; the other claims and completes it;
the sender reads the result.

Runs against the *live* server and database (default: http://127.0.0.1:8000).
Override with RELAY_BASE_URL if the server is on a different address.

    pytest test_scenario1_integration.py -v
"""

from __future__ import annotations

import os

import httpx
import pytest

BASE_URL = os.getenv("RELAY_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE_URL}/api/v1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def register(client: httpx.Client, name: str, description: str = "") -> tuple[str, str, dict]:
    """Register a new agent and return (agent_id, token, auth_headers)."""
    resp = client.post(f"{API}/agents", json={"name": name, "description": description})
    assert resp.status_code == 201, f"register failed: {resp.text}"
    data = resp.json()
    agent_id = data["agent_id"]
    token = data["token"]
    return agent_id, token, {"Authorization": f"Bearer {token}"}


def send_task(client: httpx.Client, headers: dict, to: str, input_text: str) -> str:
    """Send a task and return its task_id."""
    resp = client.post(f"{API}/tasks", headers=headers, json={"to": to, "input": input_text})
    assert resp.status_code == 201, f"send_task failed: {resp.text}"
    data = resp.json()
    assert data["status"] == "queued"
    return data["task_id"]


def claim_task(client: httpx.Client, headers: dict, worker_id: str = "test-worker") -> dict:
    """Claim the next queued task for this agent (wait_seconds=5)."""
    resp = client.post(
        f"{API}/tasks/claim",
        headers=headers,
        json={"worker_id": worker_id, "wait_seconds": 5},
        timeout=10,
    )
    assert resp.status_code == 200, f"claim_task failed ({resp.status_code}): {resp.text}"
    return resp.json()


def complete_task(client: httpx.Client, headers: dict, task_id: str, claim_token: str, output: str) -> dict:
    """Complete a claimed task and return the response body."""
    resp = client.post(
        f"{API}/tasks/{task_id}/complete",
        headers=headers,
        json={"claim_token": claim_token, "output": output},
    )
    assert resp.status_code == 200, f"complete_task failed: {resp.text}"
    return resp.json()


def get_task(client: httpx.Client, headers: dict, task_id: str) -> dict:
    """Fetch a task by ID."""
    resp = client.get(f"{API}/tasks/{task_id}", headers=headers)
    assert resp.status_code == 200, f"get_task failed: {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Scenario 1
# ---------------------------------------------------------------------------

def test_scenario1_send_claim_complete_and_sender_sees_completed():
    """
    SPEC Acceptance Scenario 1:
    Register two agents. One sends a task; the other claims and completes it;
    the sender reads the result. Confirms the sender sees status='completed'.
    """
    task_input = "Hello relay! Review this Python function: def add(a,b): return a-b"
    expected_output = task_input.upper()

    with httpx.Client(timeout=15) as client:
        # -- Step 1: Register two agents ----------------------------------
        alice_id, alice_token, alice_headers = register(client, "scenario1-alice", "Sends tasks")
        bob_id, bob_token, bob_headers = register(client, "scenario1-bob", "Claims and completes tasks")
        print(f"\n  [dashboard] alice token: {alice_token}")
        print(f"  [dashboard] bob   token: {bob_token}")

        assert alice_id != bob_id, "Each registered agent must have a unique ID"

        # -- Step 2: Verify they appear in the agent directory ------------
        dir_resp = client.get(f"{API}/agents", headers=alice_headers)
        assert dir_resp.status_code == 200
        agent_ids = {a["agent_id"] for a in dir_resp.json()["items"]}
        assert alice_id in agent_ids
        assert bob_id in agent_ids

        # -- Step 3: Alice sends a task to Bob ----------------------------
        task_id = send_task(client, alice_headers, to=bob_id, input_text=task_input)

        # Alice can immediately see her sent task as 'queued'
        queued = get_task(client, alice_headers, task_id)
        assert queued["status"] == "queued"
        assert queued["from"] == alice_id
        assert queued["to"] == bob_id

        # -- Step 4: Bob claims the task ----------------------------------
        claim = claim_task(client, bob_headers, worker_id="scenario1-bob-worker-1")

        assert claim["task_id"] == task_id, "Bob should receive the task Alice sent"
        assert claim["from"] == alice_id
        assert claim["input"] == task_input
        assert claim["attempt"] == 1
        assert "claim_token" in claim
        assert "lease_expires_at" in claim

        # Task is now 'processing'; Bob (recipient) can see this
        processing = get_task(client, bob_headers, task_id)
        assert processing["status"] == "processing"

        # -- Step 5: Bob completes the task -------------------------------
        result = complete_task(
            client, bob_headers, task_id, claim["claim_token"], output=expected_output
        )
        assert result["task_id"] == task_id
        assert result["status"] == "completed"

        # -- Step 6: Alice reads the result; sender sees 'completed' ------
        final = get_task(client, alice_headers, task_id)

        assert final["status"] == "completed", (
            f"Sender should see 'completed' after recipient submits result, got: {final['status']!r}"
        )
        assert final["output"] == expected_output
        assert final["error"] is None
        assert final["attempt_count"] == 1
        assert final["finished_at"] is not None

        # -- Step 7: Delivery attempt history -----------------------------
        attempts_resp = client.get(f"{API}/tasks/{task_id}/attempts", headers=alice_headers)
        assert attempts_resp.status_code == 200
        attempts = attempts_resp.json()["items"]
        assert len(attempts) == 1
        assert attempts[0]["outcome"] == "completed"
        assert "claim_token" not in attempts[0], "claim_token must never be exposed in attempts"


def test_scenario1_third_agent_cannot_read_task():
    """
    SPEC access control: a third agent must not be able to read the task
    belonging to another sender/recipient pair.
    """
    task_input = "secret task content"

    with httpx.Client(timeout=15) as client:
        alice_id, alice_token, alice_headers = register(client, "scenario1-alice-acl", "Sends tasks")
        bob_id, bob_token, bob_headers = register(client, "scenario1-bob-acl", "Receives tasks")
        _eve_id, eve_token, eve_headers = register(client, "scenario1-eve-acl", "Uninvited observer")
        print(f"\n  [dashboard] alice-acl token: {alice_token}")
        print(f"  [dashboard] bob-acl   token: {bob_token}")
        print(f"  [dashboard] eve-acl   token: {eve_token}")

        task_id = send_task(client, alice_headers, to=bob_id, input_text=task_input)

        # Eve must not see Alice's task
        eve_resp = client.get(f"{API}/tasks/{task_id}", headers=eve_headers)
        assert eve_resp.status_code == 404, (
            f"Third-party agent should get 404, got {eve_resp.status_code}: {eve_resp.text}"
        )
