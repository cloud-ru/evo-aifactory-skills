"""CLI handlers for `agents` subcommand."""

import sys

from helpers import (build_client, check_response, print_json, load_config_from_args,
                     confirm_destructive)
from commands._shared import (dig, apply_scaling, apply_integration, wait_for_status,
                               apply_bff_agent_defaults)


WAIT_FINAL_SUCCESS = {"AGENT_STATUS_RUNNING", "AGENT_STATUS_COOLED"}
WAIT_FINAL_FAIL = {
    "AGENT_STATUS_FAILED",
    "AGENT_STATUS_LLM_UNAVAILABLE",
    "AGENT_STATUS_TOOL_UNAVAILABLE",
    "AGENT_STATUS_IMAGE_UNAVAILABLE",
    "AGENT_STATUS_ON_DELETION",
    "AGENT_STATUS_DELETED",
}


def cmd_list(args):
    client, project_id = build_client()
    statuses = args.statuses.split(",") if getattr(args, "statuses", None) else None
    not_in = args.not_in_statuses.split(",") if getattr(args, "not_in_statuses", None) else None
    resp = client.list_agents(project_id, limit=args.limit, offset=args.offset,
                               statuses=statuses, not_in_statuses=not_in)
    check_response(resp, "listing agents")
    print_json(resp.json())


def cmd_get(args):
    client, project_id = build_client()
    resp = client.get_agent(project_id, args.agent_id)
    check_response(resp, f"getting agent {args.agent_id}")
    print_json(resp.json())


def _apply_agent_option_flags(body: dict, args) -> None:
    """Apply high-level flags mirroring the UI create-form (options.prompt,
    options.llm.{model,params,thinking}, options.scaling, options.runtimeOptions,
    options.memoryOptions, neighbors, integrationOptions.logging/auth)."""
    if getattr(args, "system_prompt", None):
        dig(body, "options", "prompt")["systemPrompt"] = args.system_prompt
    if getattr(args, "system_prompt_file", None):
        with open(args.system_prompt_file) as f:
            dig(body, "options", "prompt")["systemPrompt"] = f.read()
    if getattr(args, "model_name", None):
        dig(body, "options", "llm", "foundationModels")["modelName"] = args.model_name
    if getattr(args, "temperature", None) is not None:
        dig(body, "options", "llm", "modelParameters")["temperature"] = args.temperature
    if getattr(args, "max_tokens", None) is not None:
        dig(body, "options", "llm", "modelParameters")["maxTokens"] = args.max_tokens
    if getattr(args, "thinking", None):
        thinking = dig(body, "options", "llm", "modelParameters", "thinking")
        if args.thinking == "off":
            thinking["enabled"] = False
        else:
            thinking["enabled"] = True
            thinking["level"] = f"THINKING_LEVEL_{args.thinking.upper()}"
    if getattr(args, "thinking_budget", None) is not None:
        dig(body, "options", "llm", "modelParameters", "thinking")["budget"] = args.thinking_budget
    # scaling lives under options for agents
    apply_scaling(dig(body, "options", "scaling"), args)
    if getattr(args, "max_llm_calls", None) is not None:
        dig(body, "options", "runtimeOptions")["maxLlmCalls"] = args.max_llm_calls
    if getattr(args, "memory_enabled", None) is not None:
        dig(body, "options", "memoryOptions", "memory")["isEnabled"] = args.memory_enabled
    if getattr(args, "session_enabled", None) is not None:
        dig(body, "options", "memoryOptions", "session")["isEnabled"] = args.session_enabled
    apply_integration(body, args)
    if getattr(args, "neighbors", None):
        nbrs = body.get("neighbors") or []
        for nid in args.neighbors.split(","):
            nid = nid.strip()
            if nid and not any(n.get("agentId") == nid for n in nbrs):
                nbrs.append({"agentId": nid})
        body["neighbors"] = nbrs


def _ensure_mcp_from_marketplace(client, project_id: str, marketplace_mcp_id: str,
                                  instance_type_id: str = None) -> str:
    """Return project MCP ID for a given marketplace card. Reuse existing if any,
    otherwise create a fresh installation and return new ID.

    Name is deterministic (`cascade-mcp-<uuid8>`) so repeat cascades recognise an
    existing install and don't try to create a name-clashing resource.
    """
    # Try to reuse: list project MCPs and match by marketplaceMcpServerId
    resp = client.list_mcp_servers(project_id, limit=100, offset=0)
    if resp.status_code == 200:
        for m in resp.json().get("data", []):
            src = m.get("imageSource") or {}
            if src.get("marketplaceMcpServerId") == marketplace_mcp_id:
                return m["id"]
    # Create fresh
    card_resp = client.get_marketplace_mcp_server(project_id, marketplace_mcp_id)
    check_response(card_resp, f"fetching marketplace MCP card {marketplace_mcp_id}")
    card = card_resp.json().get("predefinedMcpServer", card_resp.json())
    body = {
        "name": f"cascade-mcp-{marketplace_mcp_id[:8]}",   # matches ^[a-z][a-z0-9-]{3,48}[a-z0-9]$
        "imageSource": {"marketplaceMcpServerId": marketplace_mcp_id},
        "description": card.get("description", ""),
    }
    if instance_type_id:
        body["instanceTypeId"] = instance_type_id
    if card.get("exposedPorts"):
        body["exposedPorts"] = card["exposedPorts"]
    resp = client.create_mcp_server(project_id, body)
    check_response(resp, f"cascade-creating MCP from marketplace {marketplace_mcp_id}")
    return resp.json()["mcpServerId"]


def _build_create_body(args, client, project_id) -> dict:
    """Combine --from-marketplace card + --config-json/file + simple flags into create body."""
    body: dict = load_config_from_args(args)
    cascade_mcp_ids: list = []
    if args.from_marketplace:
        card_resp = client.get_marketplace_agent(project_id, args.from_marketplace)
        check_response(card_resp, f"fetching marketplace card {args.from_marketplace}")
        raw = card_resp.json()
        card = raw.get("predefinedAgent", raw)
        body.setdefault("imageSource", {})["marketplaceAgentId"] = card.get("id", args.from_marketplace)
        body.setdefault("description", card.get("description", ""))
        body.setdefault("agentType", "AGENT_TYPE_FROM_HUB")
        model_id = card.get("modelId")
        if model_id:
            dig(body, "options", "llm", "foundationModels").setdefault("modelName", model_id)
        # Cascade install of MCP servers referenced by the agent card
        if getattr(args, "cascade_mcp", False):
            for mp_mcp_id in card.get("suitableCatalogMcpServersIds") or []:
                project_mcp_id = _ensure_mcp_from_marketplace(
                    client, project_id, mp_mcp_id,
                    instance_type_id=args.instance_type_id)
                cascade_mcp_ids.append(project_mcp_id)
                print(f"cascade: MCP {mp_mcp_id} -> project MCP {project_mcp_id}",
                      file=sys.stderr)
    else:
        body.setdefault("agentType", "AGENT_TYPE_CUSTOM")
    if args.name:
        body["name"] = args.name
    if args.description:
        body["description"] = args.description
    if args.instance_type_id:
        body["instanceTypeId"] = args.instance_type_id
    # MCP: single (legacy) or multiple via --mcp-servers, plus cascade-installed
    mcp_ids: list = list(cascade_mcp_ids)
    if args.mcp_server_id:
        mcp_ids.append(args.mcp_server_id)
    if getattr(args, "mcp_servers", None):
        mcp_ids.extend(x.strip() for x in args.mcp_servers.split(",") if x.strip())
    if mcp_ids:
        existing = body.get("mcpServers") or []
        for mid in mcp_ids:
            if not any(m.get("mcpServerId") == mid for m in existing):
                existing.append({"mcpServerId": mid})
        body["mcpServers"] = existing
    _apply_agent_option_flags(body, args)
    apply_bff_agent_defaults(body)
    return body


def cmd_create(args):
    client, project_id = build_client()
    body = _build_create_body(args, client, project_id)
    resp = client.create_agent(project_id, body)
    check_response(resp, "creating agent")
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
    _apply_agent_option_flags(body, args)
    if not body:
        print("Error: nothing to update (no flags, no --config-json)", file=sys.stderr)
        sys.exit(1)
    resp = client.update_agent(project_id, args.agent_id, body)
    check_response(resp, f"updating agent {args.agent_id}")
    print_json(resp.json() if resp.text else {})


def cmd_delete(args):
    confirm_destructive("delete", f"agent {args.agent_id}", args.yes)
    client, project_id = build_client()
    resp = client.delete_agent(project_id, args.agent_id)
    if resp.status_code == 404:
        print(f"Agent {args.agent_id} already deleted", file=sys.stderr)
        return
    check_response(resp, f"deleting agent {args.agent_id}")
    print_json(resp.json() if resp.text else {"status": "deleted"})


def cmd_suspend(args):
    client, project_id = build_client()
    resp = client.suspend_agent(project_id, args.agent_id)
    check_response(resp, f"suspending agent {args.agent_id}")
    print_json(resp.json() if resp.text else {"status": "suspended"})


def cmd_resume(args):
    client, project_id = build_client()
    resp = client.resume_agent(project_id, args.agent_id)
    check_response(resp, f"resuming agent {args.agent_id}")
    print_json(resp.json() if resp.text else {"status": "resumed"})


def cmd_wait(args):
    client, project_id = build_client()
    wait_for_status(lambda: client.get_agent(project_id, args.agent_id),
                     resource_key="agent", resource_label=f"agent {args.agent_id}",
                     success_statuses=WAIT_FINAL_SUCCESS, fail_statuses=WAIT_FINAL_FAIL,
                     timeout=args.timeout)


def cmd_history(args):
    client, project_id = build_client()
    resp = client.get_agent_history(project_id, args.agent_id,
                                     limit=args.limit, offset=args.offset)
    check_response(resp, f"fetching history for agent {args.agent_id}")
    print_json(resp.json())


COMMANDS = {
    "agents.list": cmd_list,
    "agents.get": cmd_get,
    "agents.create": cmd_create,
    "agents.update": cmd_update,
    "agents.delete": cmd_delete,
    "agents.suspend": cmd_suspend,
    "agents.resume": cmd_resume,
    "agents.wait": cmd_wait,
    "agents.history": cmd_history,
}
