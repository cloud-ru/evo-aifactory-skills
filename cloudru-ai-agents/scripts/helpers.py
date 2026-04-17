"""Common helpers for the AI Agents CLI."""

import json
import os
import sys

from cloudru_client import CloudruAiAgentsClient


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
                    if key not in os.environ:
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
    """Build CloudruAiAgentsClient from env vars. Returns (client, project_id)."""
    key_id = get_env("CP_CONSOLE_KEY_ID")
    key_secret = get_env("CP_CONSOLE_SECRET")
    project_id = get_env("PROJECT_ID")
    client = CloudruAiAgentsClient(key_id, key_secret)
    return client, project_id


def check_response(response, action: str):
    if not response.is_success:
        print(f"Error {action}: HTTP {response.status_code}", file=sys.stderr)
        try:
            data = response.json()
            if isinstance(data, dict):
                for detail in data.get("details", []):
                    if isinstance(detail, dict):
                        if "Recommendation" in detail:
                            print(f"Recommendation: {detail['Recommendation']}", file=sys.stderr)
                        if "HelpLink" in detail:
                            print(f"See: {detail['HelpLink']}", file=sys.stderr)
        except Exception:
            pass
        print(response.text, file=sys.stderr)
        sys.exit(1)


def print_json(obj):
    print(json.dumps(obj, indent=2, default=str, ensure_ascii=False))


def load_config_from_args(args) -> dict:
    """Load JSON config from --config-json (inline) or --config-file (path)."""
    if getattr(args, "config_json", None):
        return json.loads(args.config_json)
    if getattr(args, "config_file", None):
        with open(args.config_file) as f:
            return json.load(f)
    return {}


def confirm_destructive(action: str, target: str, auto_yes: bool) -> None:
    """Prompt the user to confirm a destructive action; exit 1 if declined."""
    if auto_yes:
        return
    if input(f"Confirm {action} on {target}? [y/N] ").strip().lower() not in ("y", "yes"):
        print("Aborted.", file=sys.stderr)
        sys.exit(1)
