# Cloud.ru ML Inference — API Reference

## Overview

The `cloudru_client.py` module provides `CloudruInferenceClient` — a lightweight httpx-based client for Cloud.ru ML Inference. It covers:

1. **BFF API** — CRUD operations on model runs (managing deployments)
2. **Inference API** — calling deployed models (chat, embeddings, rerank)
3. **IAM Auth** — automatic token management

Base URL for BFF: `https://console.cloud.ru`
Base URL for inference: `https://<model_run_id>.modelrun.inference.cloud.ru`
IAM endpoint: `https://iam.api.cloud.ru/api/v1/auth/token`

---

## Authentication

POST `https://iam.api.cloud.ru/api/v1/auth/token`

Request body:
```json
{"keyId": "<CP_CONSOLE_KEY_ID>", "secret": "<CP_CONSOLE_SECRET>"}
```

Response:
```json
{"access_token": "...", "id_token": "...", "expires_in": 3600}
```

The `IAMAuth` class (httpx.Auth subclass) handles this automatically:
- Caches token in memory
- Sets `Authorization: Bearer <token>` on every request
- Re-fetches token on 401/403 and retries once

---

## Client Setup

```python
from cloudru_client import CloudruInferenceClient

client = CloudruInferenceClient(key_id="...", key_secret="...")
```

All methods return `httpx.Response`. Check `response.is_success` and use `response.json()` to get data.

---

## BFF API Methods

API prefix: `/u-api/inference/model-run/v1`

| Method | HTTP | Path | Description |
|--------|------|------|-------------|
| `list_model_runs(project_id, limit, offset)` | GET | `/{project_id}/modelruns` | List model runs (paginated) |
| `get_model_run(project_id, model_run_id)` | GET | `/{project_id}/modelruns/{id}` | Get single model run |
| `create_model_run(project_id, payload)` | POST | `/{project_id}/modelruns` | Create model run |
| `update_model_run(project_id, model_run_id, payload)` | PUT | `/{project_id}/modelruns/{id}` | Update model run |
| `delete_model_run(project_id, model_run_id)` | DELETE | `/{project_id}/modelruns/{id}` | Delete model run |
| `suspend_model_run(project_id, model_run_id)` | PATCH | `/{project_id}/modelruns/{id}/suspend` | Suspend running model |
| `resume_model_run(project_id, model_run_id)` | PATCH | `/{project_id}/modelruns/{id}/resume` | Resume suspended model |
| `get_history(project_id, model_run_id)` | GET | `/{project_id}/modelruns/{id}/history` | Get event history |
| `get_quotas(project_id)` | GET | `/{project_id}/quota-usage` | Get GPU/CPU quota usage |
| `get_frameworks(project_id, limit, offset)` | GET | `/{project_id}/runtime-templates` | List runtime templates |
| `get_catalog(**params)` | GET | `/predefined-models` | List predefined models |
| `get_catalog_detail(model_card_id)` | GET | `/predefined-models/{id}` | Get model card details |

---

## Inference API Methods

Base URL: `https://{model_run_id}.modelrun.inference.cloud.ru`

| Method | HTTP | Path | Description |
|--------|------|------|-------------|
| `chat(model_run_id, payload, use_auth)` | POST | `/v1/chat/completions` | OpenAI-compatible text generation |
| `embed(model_run_id, payload, use_auth)` | POST | `/v1/embeddings` | Embeddings |
| `rerank(model_run_id, payload, use_auth)` | POST | `/v1/rerank` | Reranking |
| `ping(model_run_id, use_auth)` | GET | `/v1/models` | Health check |

All inference methods accept `use_auth: bool` — set to `True` if the model run has IAM auth enabled.

---

## Enum Values

### Framework Types
| CLI value | API value |
|-----------|-----------|
| `VLLM` | `FrameworkType_VLLM` |
| `SGLANG` | `FrameworkType_SGLANG` |
| `OLLAMA` | `FrameworkType_OLLAMA` |
| `TRANSFORMERS` | `FrameworkType_TRANSFORMERS` |
| `DIFFUSERS` | `FrameworkType_DIFFUSERS` |
| `COMFY` | `FrameworkType_COMFY_UI` |

### Resource Types
| CLI value | API value |
|-----------|-----------|
| `GPU_A100` | `ResourceType_GPU_A100_NVLINK` |
| `GPU_H100` | `ResourceType_GPU_H100` |
| `GPU_V100` | `ResourceType_GPU_V100` |
| `CPU` | `ResourceType_CPU` |

### Model Run Statuses
`COOLED`, `DELETED`, `FAILED`, `ON_DELETION`, `ON_SUSPENSION`, `PULLING`, `RESOURCE_ALLOCATION`, `RUNNING`, `RUNTIME_INITIALIZING`, `SUSPENDED`

### Task Types (common)
`ModelTaskType_GENERATE`, `ModelTaskType_TEXT_2_TEXT_GENERATION`, `ModelTaskType_TEXT_GENERATION`, `ModelTaskType_EMBEDDING`, `ModelTaskType_TEXT_2_IMAGE_GENERATION`, `ModelTaskType_CONVERSATIONAL`, `ModelTaskType_FEATURE_EXTRACTION`, `ModelTaskType_SUMMARIZATION`, `ModelTaskType_TRANSLATION`, `ModelTaskType_QUESTION_ANSWERING`, `ModelTaskType_CLASSIFY`, `ModelTaskType_EMBED`, `ModelTaskType_SCORE`, `ModelTaskType_REWARD`, `ModelTaskType_RERANK`

### Quantization Types
`AWQ`, `GPTQ`, `FP8`, `MARLIN`, `EXL2`, `EETQ`, `COMPRESSED_TENSORS`, `BITSANDBYTES`, `BITSANDBYTES_NF4`, `BITSANDBYTES_FP4`

---

## Request/Response Formats

### Create Model Run (POST payload)

```json
{
    "name": "my-model",
    "frameworkType": "FrameworkType_VLLM",
    "resourceType": "ResourceType_GPU_A100_NVLINK",
    "gpuCount": 1,
    "gpuGbMemory": 20,
    "modelTaskType": "ModelTaskType_GENERATE",
    "runtimeTemplateId": "<uuid>",
    "modelSource": {
        "huggingFaceRepository": {
            "repo": "org/model",
            "model": "",
            "revision": "main",
            "filePaths": []
        },
        "secret": "",
        "repoSize": 0
    },
    "servingOptions": {
        "dynamicalOptions": {"args": [], "loraModules": []}
    },
    "scaling": {
        "minScale": 1,
        "maxScale": 1,
        "scalingRules": {"rpsType": {"value": 200}}
    },
    "options": {
        "isEnabledAuth": false,
        "isEnabledLogging": false
    }
}
```

### Model Sources

**HuggingFace:**
```json
{"huggingFaceRepository": {"repo": "org/model", "model": "", "revision": "main", "filePaths": []}, "secret": "", "repoSize": 0}
```

**Ollama:**
```json
{"ollama": {"model": "tinyllama:latest", "repo": "", "revision": ""}, "secret": "", "repoSize": 0}
```

**Model Registry:**
```json
{"modelRegistry": {"repo": "registry-path", "model": "model-name", "revision": ""}, "secret": "", "repoSize": 0}
```

**ModelScope:**
```json
{"modelScope": {"repo": "org/model", "model": "", "revision": ""}, "secret": "", "repoSize": 0}
```

### Chat Request (POST /v1/chat/completions)

```json
{
    "model": "model-name",
    "messages": [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello!"}
    ],
    "temperature": 0.7,
    "top_p": 0.9
}
```

### Chat Response

```json
{
    "choices": [{"message": {"role": "assistant", "content": "..."}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
}
```

### Embedding Request (POST /v1/embeddings)

```json
{"model": "model-name", "input": ["text1", "text2"]}
```

### Rerank Request (POST /v1/rerank)

```json
{"model": "model-name", "query": "search query", "documents": ["doc1", "doc2"]}
```
