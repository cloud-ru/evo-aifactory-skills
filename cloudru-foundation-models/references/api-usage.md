# Cloud.ru Foundation Models API usage

## Base URL

Use the OpenAI-compatible base URL:

```text
https://foundation-models.api.cloud.ru/v1
```

Always prefer fetching the live model catalog from `/models` instead of hard-coding a large static list.

## List models

```bash
curl https://foundation-models.api.cloud.ru/v1/models \
  -H "Authorization: Bearer $CLOUD_RU_FOUNDATION_MODELS_API_KEY"
```

## Chat completions via cURL

```bash
curl https://foundation-models.api.cloud.ru/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $CLOUD_RU_FOUNDATION_MODELS_API_KEY" \
  -d '{
    "model": "openai/gpt-oss-120b",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

## Chat completions via OpenAI SDK

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["CLOUD_RU_FOUNDATION_MODELS_API_KEY"],
    base_url="https://foundation-models.api.cloud.ru/v1",
)

response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "user", "content": "How do I write cleaner Python?"}
    ],
)

print(response.choices[0].message.content)
```

## Notes

- Model IDs can contain `/`. Keep the full model ID unchanged when you call the API.
- The public Cloud.ru product page currently advertises text models, embedding and reranker models, Whisper, and OCR models. Still prefer querying `/models` at runtime because the catalog can change.
