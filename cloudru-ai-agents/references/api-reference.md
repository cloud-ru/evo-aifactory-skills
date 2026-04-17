# Cloud.ru AI Agents — API Reference

## Base URLs

- **BFF (used by this skill):** `https://console.cloud.ru/u-api/ai-agents/v1`
- Raw public API: `https://ai-agents.api.cloud.ru/api/v1` — also accepts the IAM bearer but has the same nil-deref class on create endpoints (expects a full-shaped body). Skill uses BFF.
- IAM auth: `https://iam.api.cloud.ru/api/v1/auth/token`
- A2A (agent runtime): `https://{agent_id}-agent.ai-agent.inference.cloud.ru/a2a/...`

## Authentication

```
POST https://iam.api.cloud.ru/api/v1/auth/token
Body: {"keyId": "<CP_CONSOLE_KEY_ID>", "secret": "<CP_CONSOLE_SECRET>"}
Response: {"access_token": "<token>"}
```

Token TTL ~30 min. Client auto-refreshes on 401.

## Endpoints

All under `/u-api/ai-agents/v1/`. Placeholders: `{p}` = projectId, `{a}` = agentId, `{m}` = mcpId, `{s}` = systemId, `{c}` = cardId, `{e}` = evoClawId, `{t}` = triggerId, `{w}` = workflowId, `{pr}` = promptId, `{sn}` = snippetId, `{sk}` = skillId.

### Deployables (agents, systems, mcp-servers, evo-claws)

| Method | Path | Purpose |
|---|---|---|
| GET | `/{p}/agents` | List |
| GET | `/{p}/agents/{a}` | Get |
| POST | `/{p}/agents` | Create |
| PATCH | `/{p}/agents/{a}` | Update |
| DELETE | `/{p}/agents/{a}` | Delete (soft) |
| PATCH | `/{p}/agents/suspend/{a}` | Suspend |
| PATCH | `/{p}/agents/resume/{a}` | Resume |
| GET | `/{p}/agents/{a}/history` | Audit log |

Substitute `agents` → `agentSystems` / `mcpServers` / `evoClaws` — identical shape, different resource key.

### Prompt library (prompts, snippets, skills)

```
POST|PATCH|DELETE|GET   /{p}/prompts[/{pr}]
                        /{p}/prompts/{pr}/versions
POST|PATCH|DELETE|GET   /{p}/snippets[/{sn}]
POST|DELETE|GET         /{p}/skills[/{sk}]
POST                    /{p}/skills:analyzeSource       # preview git tree before create
```

### Workflows

```
GET|POST|PATCH|DELETE   /{p}/workflows[/{w}]
```

(Graph editing via IDE; CLI only creates the container.)

### Triggers (per-agent)

```
GET    /{p}/agents/{a}/triggers
GET    /{p}/agents/{a}/triggers/{t}
POST   /{p}/agents/{a}/triggers                 # body: {name, options.providerOptions.{schedule|telegram|email}}
PATCH  /{p}/agents/{a}/triggers/{t}
DELETE /{p}/agents/{a}/triggers/{t}
GET    /{p}/agents/{a}/triggers:checkName?name=
```

### EvoClaw workers

```
GET    /{p}/evo-claws/{e}/options/agents        # BROKEN (unknown field OpenClawGatewayToken) — use GET /evo-claws/{e} instead
PUT    /{p}/evo-claws/{e}/options/agents        # full replace semantic
```

### Marketplace & catalog

```
GET  /marketplace/{agents|mcpServers|prompts|snippets|skills}?limit=&search=&sortType=
GET  /marketplace/{...}/{c}
GET  /{p}/instanceTypes?isActive=true           # (without isActive=true returns empty)
GET  /{p}                                        # project info; quotas under key `quotes` (sic)
```

### A2A runtime

```
GET  https://{a}-agent.ai-agent.inference.cloud.ru/a2a/.well-known/agent.json?agentId={a}
POST https://{a}-agent.ai-agent.inference.cloud.ru/a2a?agentId={a}
```

Body is JSON-RPC 2.0. Methods: `message/send`, `message/stream` (SSE), `tasks/get`, `tasks/cancel`.

## Response envelopes

| Where | Shape |
|---|---|
| List | `{"data": [...], "total": N}` |
| Get | `{"agent": {...}}` / `{"mcpServer": {...}}` / `{"agentSystem": {...}}` / `{"evoClaw": {...}}` / `{"prompt": {...}, "promptVersion": {...}}` / `{"workflow": {...}}` / `{"trigger": {...}}` |
| Marketplace get | `{"predefinedAgent": {...}}` / `{"predefinedMcpServer": {...}}` / ... |
| Create | `{"agentId": "..."}` / `{"mcpServerId": "..."}` / `{"triggerId": "..."}` / `{"workflowId": "..."}` (NOT `{"id": "..."}`) |
| Error | `{"code": N, "message": "...", "details": [..., {"Recommendation": "...", "HelpLink": "..."}]}` |

## Statuses

- `AGENT_STATUS_*`: `RESOURCE_ALLOCATION`, `PULLING`, `RUNNING`, `COOLED`, `ON_SUSPENSION`, `SUSPENDED`, `ON_DELETION`, `DELETED`, `FAILED`, `LLM_UNAVAILABLE`, `TOOL_UNAVAILABLE`, `IMAGE_UNAVAILABLE`
- `AGENT_SYSTEM_STATUS_*`: same + `AGENT_UNAVAILABLE` (limit 10 agents per system)
- `MCP_SERVER_STATUS_*`: above plus `WAITING_FOR_SCRAPPING`
- `EVOCLAW_STATUS_*`: `RUNNING`, `FAILED`, `ON_DELETION`
- `TRIGGER_STATUS_*`: `ON_LAUNCHING`, `ON_RESOURCE_ALLOCATION`, `LAUNCHED`, `ON_SUSPENSION`, `SUSPENDED`, `FAILED`, `DELETED`
- `PROMPT_STATUS_*`, `SNIPPET_STATUS_*`, `SKILL_STATUS_*`: `AVAILABLE`, `ON_CREATION`, `FAILED`, `DELETED`
- `WORKFLOW_*`: `ACTIVE`, `ON_CREATION`, `SUSPENDED`, `DELETED`

## Body schemas (core, condensed)

### Agent

```json
{
  "name": "my-agent",
  "description": "...",
  "instanceTypeId": "<uuid>",
  "agentType": "AGENT_TYPE_FROM_HUB | AGENT_TYPE_CUSTOM | AGENT_TYPE_BLUEPRINT",
  "imageSource": {"marketplaceAgentId": "<card-uuid>"},
  "mcpServers": [{"mcpServerId": "<uuid>"}],
  "neighbors": [{"agentId": "<uuid>"}],
  "options": {
    "prompt": {"systemPrompt": "..."},
    "llm": {
      "foundationModels": {"modelName": "zai-org/GLM-4.7"},
      "modelParameters": {
        "temperature": 0.3, "maxTokens": 4096,
        "thinking": {"enabled": true, "level": "THINKING_LEVEL_MEDIUM", "budget": 2000}
      }
    },
    "scaling": {
      "minScale": 0, "maxScale": 3, "keepAliveMinutes": 10,
      "scalingRules": {"rps": {"value": 5}},
      "_meta": {"scalingRulesType": "rps"}
    },
    "runtimeOptions": {"maxLlmCalls": 50},
    "memoryOptions": {
      "memory": {"isEnabled": true},
      "session": {"isEnabled": true}
    }
  },
  "integrationOptions": {
    "authOptions": {"isEnabled": true, "type": "AUTHENTICATION_TYPE_SERVICE_ACCOUNT", "serviceAccountId": "<uuid>"},
    "logging": {"isEnabledLogging": true, "logGroupId": "<uuid>"}
  }
}
```

### Agent System

Same as agent but orchestrator-centric:

```json
{
  "name": "my-system", "instanceTypeId": "<uuid>",
  "agents": [{"agentId": "<uuid>"}],
  "childAgentSystems": [{"agentSystemId": "<uuid>"}],
  "orchestratorOptions": {
    "systemPrompt": {"systemPrompt": "..."},
    "llm": {"foundationModels": {"modelName": "..."}, "modelParameters": {...}},
    "scaling": {... as above ...}
  },
  "options": {
    "contextStorage": {"isEnabled": true},
    "observability": {"isEnabled": true}
  },
  "integrationOptions": {...}
}
```

### MCP Server

```json
{
  "name": "my-mcp", "instanceTypeId": "<uuid>",
  "imageSource": {
    "marketplaceMcpServerId": "<card-uuid>"
    // OR "imageUri": "cr.cloud.ru/ns/my-mcp:v1"
  },
  "exposedPorts": [10000],
  "environmentOptions": {
    "rawEnvs": {"KEY1": "val"},
    "secretEnvs": {"TOKEN": {"id": "<secret_uuid>", "version": 1}}
  },
  "scaling": {... top-level, not under options ...},
  "integrationOptions": {...}
}
```

### Prompt

```json
{
  "name": "my-prompt",
  "description": "...",
  "imageSource": {"marketplacePromptId": "<card>"},
  "promptOptions": {
    "agent": {"prompt": "..."}     // OR "mcp": {...} OR "agentSystem": {...}
  }
}
```

Constructor mode in UI produces plain markdown text (headings = block types). No separate block data model on server.

### Snippet

```json
{
  "name": "my-snippet", "content": "...", "description": "...",
  "blockStyle": "SNIPPET_BLOCK_STYLE_PERSONALITY | _TASK | _CONTEXT | _CONSTRAINTS | _TONE_OF_VOICE | _ANSWER_EXAMPLES | _UNSPECIFIED"
}
```

PATCH rejects `name` (immutable).

### Skill

```json
{
  "name": "my-skill", "description": "...",
  "compatibility": "...",
  "skillSource": {
    "gitSource": {
      "gitUrl": "https://github.com/...",
      "accessToken": "<pat>",           // OMIT when empty — empty string breaks proto
      "skillFolderPaths": ["skills/x"]
    }
    // OR "plaintext": {}
  },
  "allowedTools": ["read_file", "grep", "run_terminal_cmd"],
  "metadata": {
    "prompt": "...",
    "requirementsOsEnvironment": "Linux",
    "requirementsAppsAndTools": "pandoc",
    "requirementsSecrets": "[]",           // JSON-serialized array string
    "artifactPaths": "[\"out/*.docx\"]",
    "resourcesSourceType": "objectStorage"
  }
}
```

`metadata` is `map<string,string>` — list/dict values must be JSON-stringified.

### Trigger (Schedule / Telegram / Email)

Wrapper is identical, only `providerOptions.<provider>` differs:

```json
{
  "name": "my-trigger",       // 5-50 chars, letters+digits+hyphen
  "options": {
    "providerOptions": {
      "schedule": {
        "config": {"cronExpression": "0 10 * * 2", "timezone": "Europe/Moscow"},
        "events": {
          "scheduleTriggered": {
            "eventLabel": "scheduleTriggered", "isEnabled": true,
            "messageRenderTemplate": "{{textMessage}}",
            "messageVariables": [{"variableLabel": "textMessage", "description": "..."}]
          }
        }
      }
    }
  }
}
```

Telegram: `providerOptions.telegram = {events: {messageReceived, messageDeleted, ...9 total}, credentials: {botName, botToken: {id, version}}}`. Server requires ALL event keys present, disabled events still use `{eventLabel:"", isEnabled:false, messageRenderTemplate:"", messageVariables:[]}`.

Email: `providerOptions.email = {events: {emailReceived, emailRead, ...7 total}, credentials: {serverAddress, port, securityCertificate, username, password: {id, version}}}`.

### Workflow

```json
{
  "name": "my-workflow", "description": "",
  "integrationOptions": {
    "logging": {"isEnabledLogging": true, "logGroupId": "<uuid>"},
    "authOptions": {"isEnabled": false, "type": "AUTHENTICATION_TYPE_UNKNOWN"},
    "autoUpdateOptions": {"isEnabled": false}
  }
  // nodes[], connections[], variables{} — edited in IDE, not CLI
}
```

### EvoClaw

```json
{
  "name": "team-claw", "type": "EVOCLAW_TYPE_OPEN_CLAW",
  "instanceTypeId": "<uuid>",
  "options": {
    "defaultLlmOptions": {"foundationModels": {"modelName": "..."}},
    "agents": [                                   // sub-agent workers
      {"name": "researcher", "workingDirectory": "/tmp", "systemPrompt": "...",
       "llmOptions": {"foundationModels": {"modelName": "..."}},
       "sandboxMode": "SANDBOX_MODE_DOCKER"}
    ]
  },
  "integrationOptions": {"logging": {"isEnabled": true, "logGroupId": "<uuid>"}, "tracing": {"isEnabled": true}}
}
```

Worker list is replaced via `PUT /evo-claws/{e}/options/agents` with body `{"agents": [...]}` (NOT merged).

## Public URLs

- Agent: `https://{agent_id}-agent.ai-agent.inference.cloud.ru` (`publicUrl` in agent get response)
- MCP server: `publicUrl` field after deploy

## Known API quirks

- **Project info returns quotas under key `quotes`** (typo preserved).
- **Empty strings break proto decoder**: `accessToken: ""`, empty arrays on required fields → 400 `unexpected token`. Omit the field entirely.
- **Scaling `_meta.scalingRulesType="rps"` is required** when any scaling block is present (even with just minScale/maxScale); server rejects otherwise with "unexpected scaling rule".
- **BFF returns HTTP 500 `nil pointer dereference` on any create with a minimal body.** `POST /agents`, `/agentSystems`, `/mcpServers` all require the full UI-shaped payload (scaling / runtimeOptions / memoryOptions / integrationOptions / authOptions / logging / autoUpdateOptions). BFF does NOT inject defaults server-side — the CLI does, via `apply_bff_*_defaults` helpers. If you send raw requests, mirror the UI payload (see `examples.md`).
- **Raw `/api/v1/` at `ai-agents.api.cloud.ru` is broken on POST /agents** (same nil-deref class). Use BFF at `console.cloud.ru/u-api/ai-agents/v1/`.
- **instanceTypes returns `[]` without `?isActive=true`.**
- **`createdBy` is an IAM SA UUID** — UI shows "неизвестный пользователь" because it resolves users only.
- **GET `/evo-claws/{e}/options/agents` returns 500** `unknown field OpenClawGatewayToken` (BFF bug, server-side). Read the full claw object instead.
- **Suspend/resume on already-suspended/running return 200 `{}`** (idempotent).
- **PATCH prompt full-body merge**: PATCH body must include `name`, `description`, `promptOptions` from current state + overrides. CLI does this automatically.
- **Snippet PATCH rejects `name`** (immutable). Only send changed fields.

## References

- Upstream OpenAPI (public API, not BFF): https://cloud.ru/docs/api/cdn/ai-agents/ug/_specs/openapi__ai-agents.yaml
- Skill CLI: `scripts/ai_agents.py --help` for flag-level docs on every command.
