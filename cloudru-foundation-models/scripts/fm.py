#!/usr/bin/env python3
"""Cloud.ru Foundation Models CLI — list models and call completions."""

import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx

_API_BASE = "https://foundation-models.api.cloud.ru/v1"


def load_api_key():
    key = os.environ.get("CLOUD_RU_FOUNDATION_MODELS_API_KEY")
    if key:
        return key
    env_path = os.environ.get("CLOUDRU_ENV_FILE")
    if env_path:
        resolved = os.path.realpath(env_path)
        if not os.path.isfile(resolved):
            print(f"Error: CLOUDRU_ENV_FILE does not exist: {env_path}", file=sys.stderr)
            sys.exit(1)
    else:
        resolved = os.path.join(os.getcwd(), ".env")
    if os.path.isfile(resolved):
        with open(resolved) as f:
            for line in f:
                line = line.strip()
                if line.startswith("CLOUD_RU_FOUNDATION_MODELS_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("\"'")
    print("Error: CLOUD_RU_FOUNDATION_MODELS_API_KEY not set", file=sys.stderr)
    sys.exit(1)


def api_request(path, api_key, method="GET", body=None):
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    url = f"{_API_BASE}{path}"
    with httpx.Client(verify=True, timeout=120) as client:
        resp = client.request(method, url, headers=headers, json=body if body else None)
        resp.raise_for_status()
        return resp.json()


def cmd_models(raw_json=False):
    api_key = load_api_key()
    data = api_request("/models", api_key)

    if raw_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    models = data.get("data") or data.get("models") or []
    if not models:
        print("No models found.")
        return

    print(f"{'MODEL ID':<50} {'OWNED BY':<20} {'TYPE':<15}")
    print("-" * 85)
    for m in models:
        mid = m.get("id", "")
        owner = m.get("owned_by", "-")
        mtype = m.get("type", m.get("object", "-"))
        print(f"{mid:<50} {owner:<20} {mtype:<15}")
    print(f"\nTotal: {len(models)} model(s)")


def cmd_call(model, prompt, system=None, temperature=0.7, raw_json=False):
    api_key = load_api_key()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {"model": model, "messages": messages, "temperature": temperature}
    data = api_request("/chat/completions", api_key, method="POST", body=body)

    if raw_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    choices = data.get("choices", [])
    if choices:
        print(choices[0].get("message", {}).get("content", ""))
    usage = data.get("usage", {})
    if usage:
        print(f"\nTokens: {usage.get('total_tokens', '?')} "
              f"(prompt={usage.get('prompt_tokens', '?')}, completion={usage.get('completion_tokens', '?')})")


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python fm.py <command> [options]")
        print("Commands:")
        print("  models [--json]                               List available models")
        print("  call <model_id> --prompt '...' [--system '...'] [--temperature 0.7] [--json]")
        print("                                                 Call chat completions")
        sys.exit(0)

    cmd = args[0]
    if cmd == "models":
        cmd_models(raw_json="--json" in args)
    elif cmd == "call":
        if len(args) < 2:
            print("Usage: fm.py call <model_id> --prompt '...'", file=sys.stderr)
            sys.exit(1)
        model = args[1]
        prompt = None
        system = None
        temperature = 0.7
        raw_json = "--json" in args
        i = 2
        while i < len(args):
            if args[i] == "--prompt" and i + 1 < len(args):
                prompt = args[i + 1]; i += 2
            elif args[i] == "--system" and i + 1 < len(args):
                system = args[i + 1]; i += 2
            elif args[i] == "--temperature" and i + 1 < len(args):
                temperature = float(args[i + 1]); i += 2
            else:
                i += 1
        if not prompt:
            print("Error: --prompt is required", file=sys.stderr)
            sys.exit(1)
        cmd_call(model, prompt, system=system, temperature=temperature, raw_json=raw_json)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
