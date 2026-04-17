# Cloud.ru AI Agents — Usage Examples

These examples use the `CloudruAiAgentsClient` Python class directly. For shell use, prefer `scripts/ai_agents.py` — it wraps the same calls with higher-level flags and validation.

## Setup

```python
from cloudru_client import CloudruAiAgentsClient

client = CloudruAiAgentsClient(key_id="...", key_secret="...")  # auto-refreshes bearer on 401
project_id = "..."
```

## 1. Browse marketplace

```python
resp = client.list_marketplace_agents(project_id, limit=5, search="excel")
cards = resp.json()["data"]
for card in cards:
    print(card["id"], card["name"], "mcp:", card.get("suitableCatalogMcpServersIds"))
```

## 2. Install MCP from marketplace card

```python
card = client.get_marketplace_mcp_server(project_id, "<card-uuid>").json()["predefinedMcpServer"]

body = {
    "name": "my-mcp",
    "description": card.get("description", ""),
    "instanceTypeId": "<instance-type-uuid>",
    "imageSource": {"marketplaceMcpServerId": card["id"]},
    "exposedPorts": card.get("exposedPorts") or [],
}
resp = client.create_mcp_server(project_id, body)
resp.raise_for_status()
mcp_id = resp.json()["mcpServerId"]              # NOTE: "mcpServerId", not "id"
```

## 3. Poll until RUNNING

```python
import time

for _ in range(40):
    data = client.get_mcp_server(project_id, mcp_id).json()["mcpServer"]  # envelope
    status = data["status"]
    if status == "MCP_SERVER_STATUS_RUNNING":
        break
    if status in {"MCP_SERVER_STATUS_FAILED", "MCP_SERVER_STATUS_IMAGE_UNAVAILABLE"}:
        raise RuntimeError(f"MCP failed: {data['statusReason']}")
    time.sleep(15)
```

## 4. Create agent linked to MCPs with scaling + system prompt

```python
body = {
    "name": "research-agent",
    "description": "Helpful researcher",
    "instanceTypeId": "<instance-type-uuid>",
    "agentType": "AGENT_TYPE_CUSTOM",
    "mcpServers": [{"mcpServerId": mcp_id}],     # array, even for one MCP
    "options": {
        "prompt": {"systemPrompt": "You are a researcher. Cite sources."},
        "llm": {
            "foundationModels": {"modelName": "zai-org/GLM-4.7"},
            "modelParameters": {"temperature": 0.3, "maxTokens": 4096},
        },
        "scaling": {
            "minScale": 0, "maxScale": 2, "keepAliveMinutes": 5,
            "scalingRules": {"rps": {"value": 5}},
            "_meta": {"scalingRulesType": "rps"},       # REQUIRED when scaling present
        },
    },
}
resp = client.create_agent(project_id, body)
resp.raise_for_status()
agent_id = resp.json()["agentId"]

# fetch publicUrl
agent = client.get_agent(project_id, agent_id).json()["agent"]
print("publicUrl:", agent["publicUrl"])
```

## 5. Attach a schedule trigger

```python
trigger_body = {
    "name": "weekly-digest",
    "options": {
        "providerOptions": {
            "schedule": {
                "config": {"cronExpression": "0 10 * * 2", "timezone": "Europe/Moscow"},
                "events": {
                    "scheduleTriggered": {
                        "eventLabel": "scheduleTriggered",
                        "isEnabled": True,
                        "messageRenderTemplate": "Weekly digest: {{textMessage}}",
                        "messageVariables": [{"variableLabel": "textMessage",
                                              "description": "Текст сообщения"}],
                    },
                },
            }
        }
    },
}
client.create_agent_trigger(project_id, agent_id, trigger_body).raise_for_status()
```

## 6. A2A chat with a running agent

```python
# Discover capabilities
card = client.a2a_agent_card(project_id, agent_id).json()

# Send a message
rpc_body = {
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
        "message": {
            "role": "user",
            "parts": [{"kind": "text", "text": "Summarize today's news."}],
        }
    },
}
resp = client.a2a_call(project_id, agent_id, rpc_body)
task = resp.json()["result"]
print("task:", task["id"], "status:", task["status"])

# Poll task
for _ in range(30):
    poll = {"jsonrpc": "2.0", "id": "2", "method": "tasks/get",
            "params": {"id": task["id"]}}
    t = client.a2a_call(project_id, agent_id, poll).json()["result"]
    if t["status"]["state"] in {"completed", "failed", "canceled"}:
        for part in t.get("artifacts", [{}])[0].get("parts", []):
            if part.get("kind") == "text":
                print(part["text"])
        break
    time.sleep(2)
```

## 7. EvoClaw: replace workers atomically

```python
workers = {
    "agents": [
        {"name": "researcher",
         "workingDirectory": "/tmp/research",
         "systemPrompt": "You are a researcher.",
         "llmOptions": {"foundationModels": {"modelName": "zai-org/GLM-4.7"}},
         "sandboxMode": "SANDBOX_MODE_DOCKER"},
        {"name": "writer",
         "workingDirectory": "/tmp/writing",
         "systemPrompt": "You are a writer.",
         "llmOptions": {"foundationModels": {"modelName": "zai-org/GLM-4.7"}},
         "sandboxMode": "SANDBOX_MODE_DOCKER"},
    ]
}
# PUT replaces the full list — merge yourself before sending
client.set_evo_claw_workers(project_id, claw_id, workers).raise_for_status()
```

## 8. Error handling with Recommendation/HelpLink

```python
resp = client.create_agent(project_id, {})
if not resp.is_success:
    data = resp.json()
    print(f"HTTP {resp.status_code}: {data.get('message')}")
    for detail in data.get("details", []):
        if "Recommendation" in detail:
            print("Fix:", detail["Recommendation"])
        if "HelpLink" in detail:
            print("See:", detail["HelpLink"])
```
