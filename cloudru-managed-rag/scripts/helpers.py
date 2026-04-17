"""Common helpers for the Managed RAG CLI."""

import json
import os
import sys

from cloudru_client import ManagedRagClient

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


def get_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"Error: environment variable {name} is not set", file=sys.stderr)
        sys.exit(1)
    return val


def build_client():
    """Build ManagedRagClient from env vars. Returns (client, project_id)."""
    key_id = get_env("CP_CONSOLE_KEY_ID")
    key_secret = get_env("CP_CONSOLE_SECRET")
    project_id = get_env("PROJECT_ID")
    client = ManagedRagClient(key_id, key_secret)
    return client, project_id


def check_response(response, action: str):
    if not response.is_success:
        print(f"Error {action}: HTTP {response.status_code}", file=sys.stderr)
        sys.exit(1)


def print_json(obj):
    print(json.dumps(obj, indent=2, default=str, ensure_ascii=False))
