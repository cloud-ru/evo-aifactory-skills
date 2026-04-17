# Cloud.ru ML Inference

> **Name:** cloudru-ml-inference
> **Description:** Manage Cloud.ru ML Inference model runs — browse the predefined model catalog, deploy models with one command, manage lifecycle, and call inference endpoints. Full CRUD and inference via lightweight httpx-based client.
> **Required env:** `CP_CONSOLE_KEY_ID`, `CP_CONSOLE_SECRET`, `PROJECT_ID`
> **Required pip:** `httpx`

## What this skill does

Manages ML model deployments (Model Runs) on Cloud.ru ML Inference service. Supports:
- Predefined model catalog (browse, search, deploy with exact configs — no guessing)
- Full CRUD on model runs (create, list, get details, update, delete)
- Lifecycle operations (suspend, resume)
- Inference calls to running models (text generation, embeddings, rerank)
- Quota and runtime template queries
- Health checks (ping) for deployed models

## When to use

Use this skill when the user:
- wants to deploy or manage ML models on Cloud.ru ML Inference
- asks about Model RUN or Docker RUN on Cloud.ru
- wants to see what models are available in the Cloud.ru catalog
- needs to create, list, update, delete, suspend, or resume inference endpoints
- wants to call a deployed model for text generation, embeddings, or reranking
- asks about GPU quotas or available frameworks on Cloud.ru ML Inference

## Prerequisites

The user must have these environment variables set:
- `CP_CONSOLE_KEY_ID` — Cloud.ru console service account key ID
- `CP_CONSOLE_SECRET` — Cloud.ru console service account secret
- `PROJECT_ID` — Cloud.ru project UUID

If credentials are missing, direct the user to the `cloudru-account-setup` skill.

The only external dependency is `httpx`. Install if not present:
```bash
pip install httpx
```

## How to use

1. Read `./references/api-reference.md` for the full API surface, enums, and data models.
2. Read `./references/examples.md` for ready-to-use Python code examples.
3. Use `./scripts/ml_inference.py` as the main script — it supports all operations via CLI subcommands.

### Deploying models (recommended flow)

Always prefer deploying from the predefined catalog — it uses exact, tested configurations:

```bash
# 1. Browse the catalog
python ./scripts/ml_inference.py catalog

# 2. See detailed configs for a model
python ./scripts/ml_inference.py catalog-detail <model_card_id>

# 3. Deploy it
python ./scripts/ml_inference.py deploy <model_card_id> --name "my-model"
```

The `deploy` command fetches the exact GPU type, memory, framework version, serving options, and scaling from the catalog — nothing to guess or configure manually.

### Managing model runs

```bash
# List all model runs
python ./scripts/ml_inference.py list

# Get model run details
python ./scripts/ml_inference.py get <model_run_id>

# Delete a model run
python ./scripts/ml_inference.py delete <model_run_id>

# Suspend / Resume
python ./scripts/ml_inference.py suspend <model_run_id>
python ./scripts/ml_inference.py resume <model_run_id>

# Get event history
python ./scripts/ml_inference.py history <model_run_id>
```

### Calling deployed models

```bash
# Chat (OpenAI-compatible)
python ./scripts/ml_inference.py call <model_run_id> \
    --prompt "Why is the sky blue?"

# Embeddings
python ./scripts/ml_inference.py embed <model_run_id> \
    --texts "Hello world" "Another text"

# Rerank
python ./scripts/ml_inference.py rerank <model_run_id> \
    --query "machine learning" --documents "ML is AI" "Weather is nice"

# Health check
python ./scripts/ml_inference.py ping <model_run_id>
```

### Infrastructure queries

```bash
# GPU/CPU quota usage
python ./scripts/ml_inference.py quotas

# Available framework versions
python ./scripts/ml_inference.py frameworks
```

### Advanced: custom model deployment

For models not in the catalog, use `create` with manual parameters:
```bash
python ./scripts/ml_inference.py create --name "my-llm" \
    --framework VLLM --resource GPU_A100 --task GENERATE \
    --source-type huggingface --repo "org/model" \
    --gpu-count 1 --gpu-memory 20 \
    --vllm-args '[{"key":"dtype","value":"bfloat16","parameterType":"PARAMETER_TYPE_ARG_KV_QUOTED"}]'
```

Note: the Cloud.ru API is strict about payload format. Prefer `deploy` from the catalog when possible.

### OpenAI-compatible endpoint

Every deployed model run exposes an **OpenAI-compatible API** at:
```
https://<model_run_id>.modelrun.inference.cloud.ru/v1
```

This means you can use it as a drop-in replacement for OpenAI in any tool:

**OpenAI Python SDK:**
```python
from openai import OpenAI
client = OpenAI(
    base_url="https://<model_run_id>.modelrun.inference.cloud.ru/v1",
    api_key="<IAM_TOKEN>",  # required — isEnabledAuth is true by default
)
response = client.chat.completions.create(
    model="model-name",
    messages=[{"role": "user", "content": "Hello!"}],
)
```

**As OPENAI_API_BASE_URL (for OpenWebUI, LiteLLM, etc.):**
```bash
export OPENAI_API_BASE_URLS="https://<model_run_id>.modelrun.inference.cloud.ru/v1"
export OPENAI_API_KEYS="not-needed"
```

**Multiple providers (FM API + ML Inference) in one config:**
```bash
# Semicolon-separated for tools that support multiple providers
export OPENAI_API_BASE_URLS="https://foundation-models.api.cloud.ru/v1;https://<model_run_id>.modelrun.inference.cloud.ru/v1"
export OPENAI_API_KEYS="$CLOUD_RU_FOUNDATION_MODELS_API_KEY;not-needed"
```

### Auth: off vs on (`isEnabledAuth`)

- **`isEnabledAuth: true`** (default) — every request must include `Authorization: Bearer <IAM_TOKEN>`. The IAM token is obtained from `https://iam.api.cloud.ru/api/v1/auth/token` using `CP_CONSOLE_KEY_ID` + `CP_CONSOLE_SECRET`. The `CloudruInferenceClient` handles this automatically when you pass `use_auth=True`. **Always use this for production deployments.**
- **`isEnabledAuth: false`** — the model endpoint is publicly accessible, no API key or token needed. Anyone with the URL can call it. **Security warning:** only use this in isolated development environments; never in production.
- To call with auth via CLI: add `--with-auth` flag to `call`, `embed`, `rerank`, `ping` commands.

### Building custom Python code

When the user needs custom code beyond what the script provides, use the patterns from `./references/examples.md` to construct Python code with the `CloudruInferenceClient` from `./scripts/cloudru_client.py`.

## What to return

- Results of operations in readable format (JSON or summary)
- Python code snippets when the user wants to integrate into their own code
- Model catalog browsing results with prices and specs

## Important notes and gotchas

### Model run names
- Names must be **lowercase latin letters, digits, and hyphens only**. No underscores, no uppercase.
- Names must start with a letter.
- The `deploy` command auto-sanitizes names from the catalog (lowercases, replaces invalid chars with hyphens).

### Deleted model runs block names
- **Deleted model runs still occupy their names.** If you delete `my-model` and try to create a new one with the same name, the API returns "a modelrun with the given name could not be created".
- The `deploy` command auto-retries with suffixed names (`-2`, `-3`, etc.) when this happens.
- To avoid this, use unique names or include a date/number.

### Deploy --wait
```bash
python ./scripts/ml_inference.py deploy <model_card_id> --name "my-model" --wait
python ./scripts/ml_inference.py deploy <model_card_id> --name "my-model" --wait --wait-timeout 900
```
Polls every 15s until the model reaches RUNNING status (default timeout: 600s).

### Catalog task types
- Models with task type `ModelTaskType_GENERATE` or `ModelTaskType_TEXT_2_TEXT_GENERATION` are compatible with OpenAI Chat Completions API (`/v1/chat/completions`).
- Models with task type `ModelTaskType_EMBEDDING` use the embeddings endpoint (`/v1/embeddings`).
- Models with task type `ModelTaskType_RERANK` use the rerank endpoint (`/v1/rerank`).
- Models with task type `ModelTaskType_TEXT_2_IMAGE_GENERATION` are NOT compatible with OpenAI Chat Completions API.

## Limitations

- Do not log or expose API keys/secrets in responses.
- Do not execute destructive operations (delete, suspend) without user confirmation.
- The inference call endpoint URL pattern is `https://<model_run_id>.modelrun.inference.cloud.ru`.
