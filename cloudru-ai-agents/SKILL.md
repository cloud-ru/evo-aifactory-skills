---
name: cloudru-ai-agents
description: Manage Cloud.ru AI Agents platform — CRUD, lifecycle, triggers, workflows, MCP, marketplace, A2A chat, EvoClaw gateways
compatibility: Requires httpx and CP_CONSOLE_KEY_ID, CP_CONSOLE_SECRET, PROJECT_ID environment variables
---

## What this skill does

Full CLI for Cloud.ru Evolution AI Agents BFF (`console.cloud.ru/u-api/ai-agents/v1`). Parity with the web UI across **all 12 command groups**:

| Group | Purpose |
|---|---|
| `agents` | AI-агенты — CRUD, suspend/resume, wait, history |
| `systems` | Агентные системы (multi-agent orchestrator) |
| `mcp-servers` | MCP-серверы |
| `prompts` | Промпты (system prompt library) |
| `snippets` | Фрагменты (promptlets, block-style) |
| `skills` | Навыки (Anthropic-style markdown skills from git or plaintext) |
| `workflows` | AI Workflows (low-code graphs; CLI creates the container, graph is edited in IDE) |
| `triggers` | Schedule / Telegram / Email triggers bound to agents |
| `evo-claws` | Managed OpenClaw gateway with sub-agent workers |
| `marketplace` | Browse/get cards for agents/mcp/prompts/snippets/skills |
| `instance-types` | CPU/GPU instance catalog |
| `chat` | A2A (Agent-to-Agent) JSON-RPC chat with a running agent |

## When to use

- Build/operate agents on Cloud.ru Evolution AI Agents
- Install from marketplace, attach MCPs, configure system prompts/models/scaling
- Schedule cron jobs on agents, wire up Telegram/Email bots
- Deploy multi-agent systems with nested agents
- Chat with a deployed agent (A2A) or capture its card
- Manage EvoClaw sub-agents

## Prerequisites

```bash
pip install httpx
export CP_CONSOLE_KEY_ID=...
export CP_CONSOLE_SECRET=...
export PROJECT_ID=...                # or use --project-id on every call
```

Credentials come from Cloud.ru service account with the `ai-agents.admin` umbrella role (covers agents/systems/mcp-servers/prompts/workflows). If missing, refer the user to the `cloudru-account-setup` skill — it attaches the role automatically.

## Command shape

All commands share the same top-level form:

```
python scripts/ai_agents.py [--project-id UUID] <group> <subcommand> [flags]
```

`--project-id` overrides `PROJECT_ID` env for a single invocation.

Every group supports `list`/`get`; most support `create`/`update`/`delete`; deployables (`agents`/`systems`/`mcp-servers`/`evo-claws`) additionally support `suspend`/`resume`/`wait`.

Two universal flags on every create/update:
- `--config-json '{...}'` — inline full body (escape hatch for fields not covered by high-level flags)
- `--config-file path.json` — same, from file

## Common flows

### Create agent from marketplace with MCP cascade install

```bash
python scripts/ai_agents.py agents create \
    --from-marketplace <agent_card_id> \
    --cascade-mcp \
    --name my-excel-agent \
    --instance-type-id <id>
python scripts/ai_agents.py agents wait <agent_id>
```

`--cascade-mcp` auto-installs any MCPs referenced in `card.suitableCatalogMcpServersIds`, reusing existing project MCPs by card id. Installed MCPs get a deterministic name `cascade-mcp-<first-8-chars-of-card-uuid>` so repeat runs are idempotent.

### Custom agent with system prompt, model, scaling, MCPs

```bash
python scripts/ai_agents.py agents create \
    --name research-agent --instance-type-id <id> \
    --system-prompt "You are a research assistant." \
    --model-name zai-org/GLM-4.7 --temperature 0.3 --max-tokens 4096 \
    --thinking medium --thinking-budget 2000 \
    --min-scale 0 --max-scale 3 --keep-alive-min 10 --rps 5 \
    --max-llm-calls 50 --memory-enabled true --session-enabled true \
    --mcp-servers <mcp1_id>,<mcp2_id> \
    --neighbors <other_agent_id> \
    --log-group-id <id> --auth-enabled true --service-account-id <sa_id>
```

### Lifecycle

```bash
python scripts/ai_agents.py agents suspend <id>       # pause (state preserved)
python scripts/ai_agents.py agents resume <id>
python scripts/ai_agents.py agents delete <id> --yes  # permanent (soft-delete, then GC)
python scripts/ai_agents.py agents history <id>       # audit log of edits
```

### Attach a cron trigger

```bash
python scripts/ai_agents.py triggers create <agent_id> \
    --name weekly-digest --trigger-type schedule \
    --cron '0 10 * * 2' --timezone Europe/Moscow \
    --message-template 'Weekly digest: {{textMessage}}'
```

### Telegram trigger

```bash
python scripts/ai_agents.py triggers create <agent_id> \
    --name tg-support --trigger-type telegram \
    --bot-name my_support_bot \
    --bot-token-secret-id <secret_manager_uuid> \
    --tg-events messageReceived,messageEdited
```

Valid events: `messageReceived,messageDeleted,messageEdited,newChatCreated,userJoined,userLeft,callbackQuery,channelPost,editedChannelPost`.

### Email (IMAP) trigger

```bash
python scripts/ai_agents.py triggers create <agent_id> \
    --name mail-intake --trigger-type email \
    --email-server imap.mail.ru --email-port 993 --email-security SSL/TLS \
    --email-user bot@example.ru --email-password-secret-id <uuid> \
    --email-events emailReceived,emailReplied
```

### Agent System (orchestrator)

```bash
python scripts/ai_agents.py systems create \
    --name research-team --instance-type-id <id> \
    --system-prompt "Coordinate these agents to answer the user." \
    --model-name zai-org/GLM-4.7 \
    --agent-ids <a1>,<a2>,<a3> \
    --min-scale 0 --max-scale 2 \
    --context-storage true --observability true
```

### MCP from marketplace or Artifact Registry

```bash
# From marketplace card
python scripts/ai_agents.py mcp-servers create \
    --from-marketplace <card_id> --name my-mcp --instance-type-id <id> \
    --env 'KEY1=val1,KEY2=val2' --secret-env 'TOKEN=<secret_uuid>' \
    --ports 10000

# From your own container in Artifact Registry
python scripts/ai_agents.py mcp-servers create \
    --image-uri cr.cloud.ru/ns/my-mcp:v1 --name my-mcp --instance-type-id <id>
```

### Prompts / Snippets / Skills from marketplace

```bash
python scripts/ai_agents.py prompts create --from-marketplace <card_id> --name my-prompt
python scripts/ai_agents.py snippets create --from-marketplace <card_id> --name my-snippet
python scripts/ai_agents.py skills create --from-marketplace <card_id> --name my-skill --git-token <pat>
```

For custom skills from git:
```bash
python scripts/ai_agents.py skills analyze --git-url https://github.com/... --git-token <pat>
python scripts/ai_agents.py skills create \
    --name docx-skill --git-url <url> --git-token <pat> \
    --git-folder-paths skills/docx \
    --allowed-tools read_file,grep,run_terminal_cmd \
    --requirements-os 'Linux' --requirements-apps 'pandoc' \
    --artifact-paths 'output/*.docx'
```

### AI Workflow

```bash
python scripts/ai_agents.py workflows create --name my-workflow
# edit graph at https://console.cloud.ru/spa/ml-ai-agents/ide/<workflow_id>
```

### EvoClaw managed gateway

```bash
python scripts/ai_agents.py evo-claws create \
    --name team-claw --instance-type-id <id> \
    --model-name zai-org/GLM-4.7 --log-group-id <id>
python scripts/ai_agents.py evo-claws wait <id>

# Manage worker sub-agents (PUT-replaces the full list)
python scripts/ai_agents.py evo-claws add-worker <claw_id> \
    --name researcher --workspace /tmp/research \
    --model-name zai-org/GLM-4.7 \
    --system-prompt "You are a researcher."
python scripts/ai_agents.py evo-claws list-workers <claw_id>
python scripts/ai_agents.py evo-claws remove-worker <claw_id> --name researcher
```

### A2A chat with a running agent

```bash
python scripts/ai_agents.py chat card <agent_id>
python scripts/ai_agents.py chat send <agent_id> --message "Hello, summarize today's briefing."
# Raw JSON-RPC pass-through
python scripts/ai_agents.py chat raw <agent_id> --method tasks/get --params '{"id":"<task_id>"}'
```

### Marketplace browse

```bash
python scripts/ai_agents.py marketplace list-agents --search "excel" --sort-type SORT_TYPE_POPULARITY_DESC
python scripts/ai_agents.py marketplace get-agent <card_id>
# same list-*/get-* for mcp, prompts, snippets, skills
```

## Important behaviors and gotchas

- **Empty strings on required *string* fields break protobuf** (e.g. `skillSource.gitSource.accessToken: ""` → 400 unexpected token). Omit the key instead. Fields that the server treats as optional *flags* (e.g. `logging.logGroupId: ""` with `isEnabledLogging=false`) are accepted — the CLI defaults follow this pattern.
- **BFF does NOT inject defaults on create.** `POST /agents`, `POST /agentSystems`, `POST /mcpServers` all nil-deref with HTTP 500 on a minimal body. The CLI seeds the full UI-shaped body (scaling / runtimeOptions / memoryOptions / integrationOptions) automatically via `apply_bff_*_defaults`. If you build a body yourself via `--config-json`, include the same structure.
- **`metadata` is `map<string,string>`:** list/dict values must be JSON-serialized strings. Skills CLI auto-serializes these.
- **Scaling requires `_meta.scalingRulesType="rps"` and a matching rule** — CLI's `--min-scale/--max-scale/--rps` seed this automatically.
- **Deploy vs orchestrator scaling nesting differs:** agents → `options.scaling`, MCP → top-level `scaling`, systems → `orchestratorOptions.scaling`. CLI hides this.
- **`delete` on missing resource returns 0** (idempotent — prints `already deleted` to stderr).
- **`wait` polls every 10–15s until terminal state;** exit 1 on failure or timeout with `Error:` prefix.
- **Service-account service-role UUID in history/audit** — the bearer belongs to an SA, so `createdBy` renders as `неизвестный пользователь` in UI. Expected.
- **EvoClaw GET `/evo-claws/{id}/options/agents` is broken server-side** (BFF bug: `unknown field OpenClawGatewayToken`). Use `list-workers` which reads the full claw object.

## Limitations

- **Metrics/Logs/Tracing tabs** — separate services (`monaas-metrics-api`, Cloud Logging, Phoenix). Not in this skill.
- **IAM/Права доступа tab** — IAM service, not ai-agents.
- **Mattermost/MAX/Jivo triggers** — UI shows "Скоро", not released.
- **Runtime workflow execution** — graph lives in IDE; CLI only creates the empty container.
- **Do not log or expose API keys/secrets.**

## References

- `references/api-reference.md` — endpoint-level details, BFF vs raw API, body schemas
- `references/examples.md` — Python snippets using the client directly

## Env vars

```
CP_CONSOLE_KEY_ID    IAM access key ID
CP_CONSOLE_SECRET    IAM access key secret
PROJECT_ID           Cloud.ru project UUID (or use --project-id flag)
CLOUDRU_ENV_FILE     Path to .env (default: .env in CWD)
```
