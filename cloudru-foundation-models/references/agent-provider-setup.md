# Using Cloud.ru Foundation Models as an AI provider

Cloud.ru Foundation Models expose an **OpenAI-compatible API**. Any tool or framework that supports custom OpenAI-compatible endpoints can use Cloud.ru.

## Connection details

| Parameter | Value |
|-----------|-------|
| Base URL | `https://foundation-models.api.cloud.ru/v1` |
| API key | `CLOUD_RU_FOUNDATION_MODELS_API_KEY` env var |
| Compatibility | OpenAI Chat Completions API |
| Example model | `openai/gpt-oss-120b` (run `/v1/models` to see all) |

## OpenAI Python SDK

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["CLOUD_RU_FOUNDATION_MODELS_API_KEY"],
    base_url="https://foundation-models.api.cloud.ru/v1",
)

response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

## cURL

```bash
curl https://foundation-models.api.cloud.ru/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $CLOUD_RU_FOUNDATION_MODELS_API_KEY" \
  -d '{"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": "Hello!"}]}'
```

## LiteLLM

```python
import litellm

response = litellm.completion(
    model="openai/openai/gpt-oss-120b",
    messages=[{"role": "user", "content": "Hello!"}],
    api_base="https://foundation-models.api.cloud.ru/v1",
    api_key=os.environ["CLOUD_RU_FOUNDATION_MODELS_API_KEY"],
)
```

## Generic agent / framework config

For any agent that accepts a custom OpenAI-compatible provider, use:
- **Base URL:** `https://foundation-models.api.cloud.ru/v1`
- **API key:** the value of `CLOUD_RU_FOUNDATION_MODELS_API_KEY`
- **Model ID:** a full model ID from the `/v1/models` endpoint (e.g. `openai/gpt-oss-120b`)

## Notes

- Model IDs can contain `/`. Keep the full model ID unchanged.
- Prefer querying `/v1/models` at runtime — the catalog can change.
- Prefer secret refs or env vars over pasting the raw API key into config.
