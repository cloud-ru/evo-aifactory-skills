"""CLI handlers for `systems` (agent-systems) subcommand."""

import sys

from helpers import (build_client, check_response, print_json, load_config_from_args,
                     confirm_destructive)
from commands._shared import (dig, apply_scaling, apply_integration, wait_for_status,
                               apply_bff_system_defaults)


WAIT_FINAL_SUCCESS = {"AGENT_SYSTEM_STATUS_RUNNING", "AGENT_SYSTEM_STATUS_COOLED"}
WAIT_FINAL_FAIL = {
    "AGENT_SYSTEM_STATUS_FAILED",
    "AGENT_SYSTEM_STATUS_AGENT_UNAVAILABLE",
    "AGENT_SYSTEM_STATUS_IMAGE_UNAVAILABLE",
    "AGENT_SYSTEM_STATUS_ON_DELETION",
    "AGENT_SYSTEM_STATUS_DELETED",
}


def cmd_list(args):
    client, project_id = build_client()
    resp = client.list_systems(project_id, limit=args.limit, offset=args.offset)
    check_response(resp, "listing systems")
    print_json(resp.json())


def cmd_get(args):
    client, project_id = build_client()
    resp = client.get_system(project_id, args.system_id)
    check_response(resp, f"getting system {args.system_id}")
    print_json(resp.json())


def _apply_system_flags(body: dict, args) -> None:
    """Fill orchestratorOptions.{systemPrompt, llm, scaling}, options.{contextStorage,
    observability}, integrationOptions.{authOptions, logging}, agents[], childAgentSystems[]."""
    # Orchestrator: prompt
    if getattr(args, "system_prompt", None):
        dig(body, "orchestratorOptions", "systemPrompt")["systemPrompt"] = args.system_prompt
    if getattr(args, "system_prompt_file", None):
        with open(args.system_prompt_file) as f:
            dig(body, "orchestratorOptions", "systemPrompt")["systemPrompt"] = f.read()
    # Orchestrator: LLM
    if getattr(args, "model_name", None):
        dig(body, "orchestratorOptions", "llm", "foundationModels")["modelName"] = args.model_name
    if getattr(args, "temperature", None) is not None:
        dig(body, "orchestratorOptions", "llm", "modelParameters")["temperature"] = args.temperature
    if getattr(args, "max_tokens", None) is not None:
        dig(body, "orchestratorOptions", "llm", "modelParameters")["maxTokens"] = args.max_tokens
    # Orchestrator: scaling
    if any(getattr(args, k, None) is not None for k in
           ("min_scale", "max_scale", "keep_alive_min", "rps")):
        apply_scaling(dig(body, "orchestratorOptions", "scaling"), args)
    # Top-level options toggles
    if getattr(args, "context_storage", None) is not None:
        dig(body, "options", "contextStorage")["isEnabled"] = args.context_storage
    if getattr(args, "observability", None) is not None:
        dig(body, "options", "observability")["isEnabled"] = args.observability
    # Integration (auth + logging)
    apply_integration(body, args)
    # Members: agents + child systems
    if getattr(args, "agent_ids", None):
        lst = body.get("agents") or []
        for aid in args.agent_ids.split(","):
            aid = aid.strip()
            if aid and not any(x.get("agentId") == aid for x in lst):
                lst.append({"agentId": aid})
        body["agents"] = lst
    if getattr(args, "child_system_ids", None):
        lst = body.get("childAgentSystems") or []
        for sid in args.child_system_ids.split(","):
            sid = sid.strip()
            if sid and not any(x.get("agentSystemId") == sid for x in lst):
                lst.append({"agentSystemId": sid})
        body["childAgentSystems"] = lst


def _build_create_body(args) -> dict:
    body: dict = load_config_from_args(args)
    if args.name:
        body["name"] = args.name
    if args.description:
        body["description"] = args.description
    if args.instance_type_id:
        body["instanceTypeId"] = args.instance_type_id
    _apply_system_flags(body, args)
    apply_bff_system_defaults(body)
    return body


def cmd_create(args):
    client, project_id = build_client()
    body = _build_create_body(args)
    resp = client.create_system(project_id, body)
    check_response(resp, "creating system")
    print_json(resp.json())


def cmd_update(args):
    client, project_id = build_client()
    body = load_config_from_args(args)
    if args.name:
        body["name"] = args.name
    if args.description is not None:
        body["description"] = args.description
    if args.instance_type_id:
        body["instanceTypeId"] = args.instance_type_id
    _apply_system_flags(body, args)
    if not body:
        print("Error: nothing to update", file=sys.stderr)
        sys.exit(1)
    resp = client.update_system(project_id, args.system_id, body)
    check_response(resp, f"updating system {args.system_id}")
    print_json(resp.json() if resp.text else {})


def cmd_delete(args):
    confirm_destructive("delete", f"system {args.system_id}", args.yes)
    client, project_id = build_client()
    resp = client.delete_system(project_id, args.system_id)
    if resp.status_code == 404:
        print(f"System {args.system_id} already deleted", file=sys.stderr)
        return
    check_response(resp, f"deleting system {args.system_id}")
    print_json(resp.json() if resp.text else {"status": "deleted"})


def cmd_suspend(args):
    client, project_id = build_client()
    resp = client.suspend_system(project_id, args.system_id)
    check_response(resp, f"suspending system {args.system_id}")
    print_json(resp.json() if resp.text else {"status": "suspended"})


def cmd_resume(args):
    client, project_id = build_client()
    resp = client.resume_system(project_id, args.system_id)
    check_response(resp, f"resuming system {args.system_id}")
    print_json(resp.json() if resp.text else {"status": "resumed"})


def cmd_wait(args):
    client, project_id = build_client()
    wait_for_status(lambda: client.get_system(project_id, args.system_id),
                     resource_key="agentSystem",
                     resource_label=f"system {args.system_id}",
                     success_statuses=WAIT_FINAL_SUCCESS, fail_statuses=WAIT_FINAL_FAIL,
                     timeout=args.timeout)


COMMANDS = {
    "systems.list": cmd_list,
    "systems.get": cmd_get,
    "systems.create": cmd_create,
    "systems.update": cmd_update,
    "systems.delete": cmd_delete,
    "systems.suspend": cmd_suspend,
    "systems.resume": cmd_resume,
    "systems.wait": cmd_wait,
}
