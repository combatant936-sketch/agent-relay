
import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"


# 1. Register Alice
alice_response = requests.post(
    f"{BASE_URL}/agents",
    json={"name": "alice"},
)

alice_response.raise_for_status()
alice = alice_response.json()

print("Alice:", alice)


# 2. Register Bob
bob_response = requests.post(
    f"{BASE_URL}/agents",
    json={"name": "bob"},
)

bob_response.raise_for_status()
bob = bob_response.json()

print("Bob:", bob)


# 3. Alice sends a task to Bob
task_response = requests.post(
    f"{BASE_URL}/tasks",
    headers={
        "Authorization": f"Bearer {alice['token']}"
    },
    json={
        "to": bob["agent_id"],
        "input": "hello world",
    },
)

task_response.raise_for_status()
task = task_response.json()

print("Task:", task)


# 4. Bob claims the task
claim_response = requests.post(
    f"{BASE_URL}/tasks/claim",
    headers={
        "Authorization": f"Bearer {bob['token']}"
    },
    json={
        "wait_seconds": 5
    },
)

claim_response.raise_for_status()
claim = claim_response.json()

print("Claim:", claim)


# 5. Bob completes the task
complete_response = requests.post(
    f"{BASE_URL}/tasks/{claim['task_id']}/complete",
    headers={
        "Authorization": f"Bearer {bob['token']}"
    },
    json={
        "claim_token": claim["claim_token"],
        "output": "HELLO WORLD",
    },
)

complete_response.raise_for_status()

print("Complete:", complete_response.json())


# # 6. Alice reads the result
# result_response = requests.get(
#     f"{BASE_URL}/tasks/{claim['task_id']}",
#     headers={
#         "Authorization": f"Bearer {alice['token']}"
#     },
# )

# result_response.raise_for_status()

# print("Result:", result_response.json())
