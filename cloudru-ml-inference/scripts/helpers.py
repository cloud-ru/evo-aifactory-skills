"""Common helpers for the ML Inference CLI."""

import json
import os
import sys

from cloudru_client import CloudruInferenceClient

_ALLOWED_ENV_KEYS = frozenset({
    "CP_CONSOLE_KEY_ID", "CP_CONSOLE_SECRET", "PROJECT_ID",
    "CLOUD_RU_FOUNDATION_MODELS_API_KEY", "CLOUDRU_ENV_FILE",
    "MANAGED_RAG_KB_ID", "MANAGED_RAG_SEARCH_URL",
})


def _load_dotenv():
    """Read .env file (key=value lines) into os.environ if keys not already set.

    Search order:
      1. CLOUDRU_ENV_FILE env var (explicit path)
      2. .env in current working directory
    """
    explicit = os.environ.get("CLOUDRU_ENV_FILE")
    candidates = [explicit] if explicit else [os.path.join(os.getcwd(), ".env")]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            with open(candidate) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                        value = value[1:-1]
                    if key in _ALLOWED_ENV_KEYS and key not in os.environ:
                        os.environ[key] = value
            break


_load_dotenv()

FRAMEWORK_ENUM_MAP = {
    "VLLM": "FrameworkType_VLLM",
    "SGLANG": "FrameworkType_SGLANG",
    "OLLAMA": "FrameworkType_OLLAMA",
    "TRANSFORMERS": "FrameworkType_TRANSFORMERS",
    "DIFFUSERS": "FrameworkType_DIFFUSERS",
    "COMFY": "FrameworkType_COMFY_UI",
}

RESOURCE_ENUM_MAP = {
    "GPU_A100": "ResourceType_GPU_A100_NVLINK",
    "GPU_H100": "ResourceType_GPU_H100",
    "GPU_V100": "ResourceType_GPU_V100",
    "CPU": "ResourceType_CPU",
}

TASK_ENUM_MAP = {
    "GENERATE": "ModelTaskType_GENERATE",
    "TEXT_2_TEXT_GENERATION": "ModelTaskType_TEXT_2_TEXT_GENERATION",
    "TEXT_GENERATION": "ModelTaskType_TEXT_GENERATION",
    "EMBEDDING": "ModelTaskType_EMBEDDING",
    "TEXT_2_IMAGE_GENERATION": "ModelTaskType_TEXT_2_IMAGE_GENERATION",
    "CONVERSATIONAL": "ModelTaskType_CONVERSATIONAL",
    "FEATURE_EXTRACTION": "ModelTaskType_FEATURE_EXTRACTION",
    "SUMMARIZATION": "ModelTaskType_SUMMARIZATION",
    "TRANSLATION": "ModelTaskType_TRANSLATION",
    "QUESTION_ANSWERING": "ModelTaskType_QUESTION_ANSWERING",
    "CLASSIFY": "ModelTaskType_CLASSIFY",
    "EMBED": "ModelTaskType_EMBED",
    "SCORE": "ModelTaskType_SCORE",
    "REWARD": "ModelTaskType_REWARD",
    "RERANK": "ModelTaskType_RERANK",
}


def get_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"Error: environment variable {name} is not set", file=sys.stderr)
        sys.exit(1)
    return val


def build_client():
    key_id = get_env("CP_CONSOLE_KEY_ID")
    key_secret = get_env("CP_CONSOLE_SECRET")
    project_id = get_env("PROJECT_ID")
    client = CloudruInferenceClient(key_id, key_secret)
    return client, project_id


def check_response(response, action: str):
    if not response.is_success:
        print(f"Error {action}: HTTP {response.status_code}", file=sys.stderr)
        sys.exit(1)


def print_json(obj):
    print(json.dumps(obj, indent=2, default=str, ensure_ascii=False))
