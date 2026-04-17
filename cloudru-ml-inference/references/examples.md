# Cloud.ru ML Inference — Python Examples

## Setup (common for all examples)

```python
import os
from cloudru_client import CloudruInferenceClient

CP_CONSOLE_KEY_ID = os.environ["CP_CONSOLE_KEY_ID"]
CP_CONSOLE_SECRET = os.environ["CP_CONSOLE_SECRET"]
PROJECT_ID = os.environ["PROJECT_ID"]

client = CloudruInferenceClient(CP_CONSOLE_KEY_ID, CP_CONSOLE_SECRET)
```

---

## 1. List Model Runs

```python
res = client.list_model_runs(PROJECT_ID)
assert res.is_success
data = res.json()
print(f"Total model runs: {data['total']}")
for mr in data["modelRuns"]:
    print(f"  {mr['modelRunId']} | {mr['name']} | {mr['status']} | {mr['frameworkType']}")
```

### With pagination

```python
res = client.list_model_runs(PROJECT_ID, limit=10, offset=0)
```

---

## 2. Get Model Run Details

```python
model_run_id = "ad6f4f28-cba2-40a7-b7bf-0cf55cb4382c"
res = client.get_model_run(PROJECT_ID, model_run_id)
assert res.is_success
import json
print(json.dumps(res.json()["modelRun"], indent=2))
```

---

## 3. Create Model Run — vLLM from HuggingFace

```python
payload = {
    "name": "llama2-7b-chat",
    "frameworkType": "FrameworkType_VLLM",
    "resourceType": "ResourceType_GPU_A100_NVLINK",
    "modelTaskType": "ModelTaskType_TEXT_2_TEXT_GENERATION",
    "modelSource": {
        "huggingFaceRepository": {
            "repo": "meta-llama/Llama-2-7b-chat-hf",
            "model": "",
            "revision": "main",
            "filePaths": [],
        },
        "secret": "",
        "repoSize": 0,
    },
    "gpuCount": 1,
    "gpuGbMemory": 20,
    "runtimeTemplateId": "<get from frameworks>",
    "servingOptions": {
        "dynamicalOptions": {"args": [], "loraModules": []},
    },
    "scaling": {
        "minScale": 0,
        "maxScale": 1,
        "scalingRules": {"concurrencyType": {"soft": 1, "hard": 2}},
        "keepAliveDuration": {"hours": 0, "minutes": 15, "seconds": 0},
    },
    "options": {"isEnabledAuth": False, "isEnabledLogging": False},
}

res = client.create_model_run(PROJECT_ID, payload)
assert res.is_success
print(f"Created model run: {res.json()['modelRunId']}")
```

---

## 4. Create Model Run — Ollama

```python
payload = {
    "name": "tinyllama-ollama",
    "frameworkType": "FrameworkType_OLLAMA",
    "resourceType": "ResourceType_GPU_V100",
    "modelTaskType": "ModelTaskType_TEXT_2_TEXT_GENERATION",
    "modelSource": {
        "ollama": {"model": "tinyllama:latest", "repo": "", "revision": ""},
        "secret": "",
        "repoSize": 0,
    },
    "gpuCount": 1,
    "gpuGbMemory": 16,
    "runtimeTemplateId": "<get from frameworks>",
    "servingOptions": {"ollamaOptions": {}},
    "scaling": {"minScale": 1, "maxScale": 1, "scalingRules": {"rpsType": {"value": 200}}},
    "options": {"isEnabledAuth": False, "isEnabledLogging": False},
}

res = client.create_model_run(PROJECT_ID, payload)
assert res.is_success
print(f"Created: {res.json()['modelRunId']}")
```

---

## 5. Create Model Run — Diffusers (Image Generation)

```python
payload = {
    "name": "stable-diffusion",
    "frameworkType": "FrameworkType_DIFFUSERS",
    "resourceType": "ResourceType_GPU_A100_NVLINK",
    "modelTaskType": "ModelTaskType_TEXT_2_IMAGE_GENERATION",
    "modelSource": {
        "huggingFaceRepository": {
            "repo": "stabilityai/stable-diffusion-xl-base-1.0",
            "model": "",
            "revision": "main",
            "filePaths": [],
        },
        "secret": "",
        "repoSize": 0,
    },
    "gpuCount": 1,
    "gpuGbMemory": 20,
    "runtimeTemplateId": "<get from frameworks>",
    "servingOptions": {"diffusersOptions": {}},
    "scaling": {"minScale": 1, "maxScale": 1, "scalingRules": {"rpsType": {"value": 200}}},
    "options": {"isEnabledAuth": False, "isEnabledLogging": False},
}

res = client.create_model_run(PROJECT_ID, payload)
assert res.is_success
```

---

## 6. Update Model Run

```python
payload = {
    "name": "llama2-7b-chat-updated",
    "scaling": {
        "minScale": 1,
        "maxScale": 3,
        "scalingRules": {"concurrencyType": {"soft": 2, "hard": 4}},
        "keepAliveDuration": {"hours": 1, "minutes": 0, "seconds": 0},
    },
}

res = client.update_model_run(PROJECT_ID, model_run_id, payload)
assert res.is_success
```

---

## 7. Delete Model Run

```python
res = client.delete_model_run(PROJECT_ID, model_run_id)
assert res.is_success
print("Deleted")
```

---

## 8. Suspend / Resume

```python
# Suspend
res = client.suspend_model_run(PROJECT_ID, model_run_id)
assert res.is_success

# Resume
res = client.resume_model_run(PROJECT_ID, model_run_id)
assert res.is_success
```

---

## 9. Call Model — OpenAI-compatible Chat

```python
payload = {
    "model": "tinyllama:latest",
    "messages": [
        {"role": "user", "content": "Why is the sky blue?"},
    ],
    "temperature": 0.7,
    "top_p": 0.9,
}

res = client.chat(model_run_id, payload)
assert res.is_success
result = res.json()
print(result["choices"][0]["message"]["content"])
print(f"Tokens used: {result['usage']['total_tokens']}")
```

---

## 10. Call Model — Chat with System Prompt

```python
payload = {
    "model": "meta-llama/Llama-2-7b-chat-hf",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain quantum computing briefly."},
    ],
    "temperature": 0.7,
    "top_p": 0.9,
}

res = client.chat(model_run_id, payload)
assert res.is_success
print(res.json()["choices"][0]["message"]["content"])
```

---

## 11. Call Model — Embeddings

```python
payload = {
    "model": "BAAI/bge-large-en-v1.5",
    "input": ["Hello world", "How are you?"],
}

res = client.embed(model_run_id, payload)
assert res.is_success
result = res.json()
for item in result["data"]:
    print(f"  [{item['index']}] dim={len(item['embedding'])} first_3={item['embedding'][:3]}")
```

---

## 12. Call Model — Rerank

```python
payload = {
    "model": "BAAI/bge-reranker-v2-m3",
    "query": "What is machine learning?",
    "documents": [
        "Machine learning is a subset of AI.",
        "The weather is nice today.",
        "Deep learning uses neural networks.",
    ],
}

res = client.rerank(model_run_id, payload)
assert res.is_success
for r in res.json()["results"]:
    print(f"  [{r['index']}] score={r['relevance_score']:.4f} text={r['document']['text'][:50]}")
```

---

## 13. Ping / Health Check

```python
res = client.ping(model_run_id)
print(f"Healthy: {res.is_success}")
```

---

## 14. Get Quotas

```python
res = client.get_quotas(PROJECT_ID)
assert res.is_success
for q in res.json()["data"]:
    print(f"  {q['resourceType']}: {q['free']} free / {q['limit']} total")
```

---

## 15. Get Available Framework Versions

```python
res = client.get_frameworks(PROJECT_ID)
assert res.is_success
for rt in res.json()["runtimeTemplates"]:
    gpus = ", ".join(
        f"{g['resourceType']}{'(default)' if g.get('isDefault') else ''}"
        for g in rt["gpus"] if g.get("isAllowed")
    )
    print(f"  {rt['frameworkType']} v{rt['version']} (id={rt['id']}) GPUs: [{gpus}]")
```

---

## 16. Get Model Run Event History

```python
res = client.get_history(PROJECT_ID, model_run_id)
assert res.is_success
for event in res.json()["events"]:
    print(f"  {event['eventType']} at {event['version']} by {event['authorId']}")
```

---

## 17. Browse Predefined Model Catalog

```python
# List models
res = client.get_catalog(limit=20, offset=0, sort="SORT_TYPE_PRICE_ASC")
assert res.is_success
for card in res.json()["modelCards"]:
    print(f"  {card['id']} | {card['name']} | {card.get('paramsBn')}B | {card.get('price')} rub/hour")

# Get detailed configs for a model
res = client.get_catalog_detail("<model_card_id>")
assert res.is_success
data = res.json()
for cfg in data["modelCardConfigs"]:
    print(f"  GPU: {cfg['allowedGpu']} x{cfg['gpuCount']} | Framework: {cfg['frameworkType']}")
```

---

## 18. Deploy from Catalog (end-to-end)

```python
# 1. Pick a model from catalog
res = client.get_catalog(query="Llama", limit=5)
card_id = res.json()["modelCards"][0]["id"]

# 2. Get its configs
res = client.get_catalog_detail(card_id)
data = res.json()
card = data["modelCard"]
cfg = data["modelCardConfigs"][0]  # pick first config

# 3. Deploy
payload = {
    "name": card["name"],
    "frameworkType": cfg["frameworkType"],
    "resourceType": cfg["allowedGpu"],
    "gpuCount": cfg["gpuCount"],
    "gpuGbMemory": cfg["gpuMemoryAllocGb"],
    "modelTaskType": card["taskType"],
    "runtimeTemplateId": cfg["runtimeTemplateId"],
    "modelSource": card["modelSource"],
    "servingOptions": cfg.get("servingOptions", {}),
    "scaling": cfg.get("scaling", {"minScale": 1, "maxScale": 1}),
    "options": {"isEnabledAuth": False, "isEnabledLogging": False},
}

res = client.create_model_run(PROJECT_ID, payload)
assert res.is_success
model_run_id = res.json()["modelRunId"]
print(f"Deployed: {model_run_id}.modelrun.inference.cloud.ru")
```
