"""CLI handlers for `prompts` subcommand."""

import sys

from helpers import (build_client, check_response, print_json, load_config_from_args,
                     confirm_destructive)


def _build_create_body(args, client, project_id) -> dict:
    body: dict = load_config_from_args(args)
    if args.from_marketplace:
        card_resp = client.get_marketplace_prompt(project_id, args.from_marketplace)
        check_response(card_resp, f"fetching marketplace prompt {args.from_marketplace}")
        raw = card_resp.json()
        card = raw.get("predefinedPrompt", raw)
        body.setdefault("imageSource", {})["marketplacePromptId"] = card.get("id", args.from_marketplace)
        body.setdefault("description", card.get("description") or card.get("previewDescription", ""))
    if args.name:
        body["name"] = args.name
    if args.description:
        body["description"] = args.description
    target = getattr(args, "target", None) or "agent"  # agent | mcp | agentSystem
    if args.prompt:
        body.setdefault("promptOptions", {}).setdefault(target, {})["prompt"] = args.prompt
    if args.prompt_file:
        with open(args.prompt_file) as f:
            body.setdefault("promptOptions", {}).setdefault(target, {})["prompt"] = f.read()
    return body


def cmd_list(args):
    client, project_id = build_client()
    not_in = args.not_in_statuses.split(",") if args.not_in_statuses else None
    resp = client.list_prompts(project_id, limit=args.limit, offset=args.offset,
                                name=args.search, not_in_statuses=not_in)
    check_response(resp, "listing prompts")
    print_json(resp.json())


def cmd_get(args):
    client, project_id = build_client()
    resp = client.get_prompt(project_id, args.prompt_id)
    check_response(resp, f"getting prompt {args.prompt_id}")
    print_json(resp.json())


def cmd_create(args):
    client, project_id = build_client()
    body = _build_create_body(args, client, project_id)
    if not body.get("name"):
        print("Error: --name or --config-json/--config-file with name is required", file=sys.stderr)
        sys.exit(1)
    resp = client.create_prompt(project_id, body)
    check_response(resp, "creating prompt")
    print_json(resp.json())


def cmd_update(args):
    client, project_id = build_client()
    cur = client.get_prompt(project_id, args.prompt_id)
    check_response(cur, f"getting prompt {args.prompt_id}")
    cur_data = cur.json()
    prompt_meta = cur_data.get("prompt", {})
    version = cur_data.get("promptVersion", {})
    body = {
        "name": prompt_meta.get("name"),
        "description": prompt_meta.get("description", ""),
        "promptOptions": version.get("promptOptions", {}),
    }
    overrides = load_config_from_args(args)
    if overrides:
        body.update(overrides)
    if args.name:
        body["name"] = args.name
    if args.description is not None:
        body["description"] = args.description
    target = getattr(args, "target", None) or "agent"
    if args.prompt:
        body.setdefault("promptOptions", {}).setdefault(target, {})["prompt"] = args.prompt
    if args.prompt_file:
        with open(args.prompt_file) as f:
            body.setdefault("promptOptions", {}).setdefault(target, {})["prompt"] = f.read()
    resp = client.update_prompt(project_id, args.prompt_id, body)
    check_response(resp, f"updating prompt {args.prompt_id}")
    print_json(resp.json())


def cmd_delete(args):
    confirm_destructive("delete", f"prompt {args.prompt_id}", args.yes)
    client, project_id = build_client()
    resp = client.delete_prompt(project_id, args.prompt_id)
    check_response(resp, f"deleting prompt {args.prompt_id}")
    print_json(resp.json() if resp.text else {})


def cmd_versions(args):
    client, project_id = build_client()
    resp = client.list_prompt_versions(project_id, args.prompt_id,
                                        limit=args.limit, offset=args.offset)
    check_response(resp, f"listing versions of {args.prompt_id}")
    print_json(resp.json())


COMMANDS = {
    "prompts.list": cmd_list,
    "prompts.get": cmd_get,
    "prompts.create": cmd_create,
    "prompts.update": cmd_update,
    "prompts.delete": cmd_delete,
    "prompts.versions": cmd_versions,
}
