---
name: cloudru-foundation-models
description: Work with Cloud.ru Evolution Foundation Models via the OpenAI-compatible API. List models, generate cURL/Python examples, and use Cloud.ru as a model provider.
compatibility: Requires httpx and CLOUD_RU_FOUNDATION_MODELS_API_KEY environment variable
---

# Cloud.ru Foundation Models

## What this skill does

Helps the user work with the Cloud.ru Foundation Models API:
1. list available models from `https://foundation-models.api.cloud.ru/v1/models`;
2. produce cURL and Python examples for chat completions;
3. configure any AI agent or application to use Cloud.ru as a model provider.

## Important

Do NOT switch your own model provider to Cloud.ru unless the user explicitly asks you to. This skill is for helping the user work with Cloud.ru models, not for reconfiguring yourself.

## When to use

- The user wants to call Cloud.ru Foundation Models via API or code.
- The user asks how to list Cloud.ru models.
- The user wants to set up an AI agent with Cloud.ru as a provider.
- The user mentions Cloud.ru Foundation Models or similar model names.

## Prerequisites

The user must have `CLOUD_RU_FOUNDATION_MODELS_API_KEY` set. If the key is missing, direct the user to the `cloudru-account-setup` skill first.

## Pricing

- Prices are **per 1 million tokens** (input and output may differ).
- Some models are **free** (`is_billable: false`, `cost: 0`). Check the catalog with `fm.py models` or the `/v1/models` endpoint.
- Free models are a good starting point for experiments and prototyping.

## CLI script

```bash
# List available models (shows model ID, owner, type)
python3 scripts/fm.py models

# List models as raw JSON
python3 scripts/fm.py models --json

# Call a model
python3 scripts/fm.py call <model_id> --prompt "Hello!"

# Call with system prompt and temperature
python3 scripts/fm.py call <model_id> --prompt "Explain AI" --system "Be brief" --temperature 0.3
```

## How to use

1. Read `references/api-usage.md` for cURL and Python examples.
2. Read `references/agent-provider-setup.md` when the user wants to configure an AI agent to use Cloud.ru as a model provider.
3. Prefer fetching the live model catalog from `/v1/models` instead of hard-coding model IDs.
4. Model IDs can contain `/` — keep the full ID unchanged.

## What to return

- cURL or Python examples tailored to the user's request.
- Provider config snippets for the user's agent/framework when asked.
- Current model IDs from the live catalog when relevant.

## Limitations

- Do not log or expose API keys in responses.
- Do not execute API calls with untrusted user input without validation.
