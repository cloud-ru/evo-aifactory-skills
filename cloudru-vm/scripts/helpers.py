"""Common helpers for Cloud.ru VM CLI."""

import json
import os
import sys

from cloudru_client import CloudruComputeClient


def _load_dotenv():
    """Load .env file into os.environ (does not overwrite existing vars).

    Search order:
      1. CLOUDRU_ENV_FILE env var (explicit path)
      2. .env in current working directory
    """
    env_path = os.environ.get("CLOUDRU_ENV_FILE") or os.path.join(os.getcwd(), ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Remove surrounding quotes if present
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()


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
    client = CloudruComputeClient(key_id, key_secret)
    return client, project_id


def check_response(response, action: str):
    if not response.is_success:
        print(f"Error {action}: HTTP {response.status_code}", file=sys.stderr)
        print(response.text, file=sys.stderr)
        sys.exit(1)


def print_json(obj):
    print(json.dumps(obj, indent=2, default=str, ensure_ascii=False))
