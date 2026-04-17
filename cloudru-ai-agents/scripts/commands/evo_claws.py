"""CLI handlers for `evo-claws` — managed OpenClaw gateway product.

EvoClaw — это managed gateway, в котором развёрнуты sub-agents (workers) со
своей рабочей папкой, моделью, системным промптом и sandbox-режимом. В UI
они называются "агенты", но это НЕ top-level AI-агенты — это записи внутри
EvoClawOptions.agents, управляемые PUT (не POST/PATCH).
"""

import json
import sys

from helpers import (build_client, check_response, print_json, load_config_from_args,
                     confirm_destructive)
from commands._shared import wait_for_status


WAIT_SUCCESS = {"EVOCLAW_STATUS_RUNNING"}
WAIT_FAIL = {"EVOCLAW_STATUS_FAILED", "EVOCLAW_STATUS_ON_DELETION"}


def cmd_list(args):
    client, project_id = build_client()
    statuses = args.statuses.split(",") if getattr(args, "statuses", None) else None
    resp = client.list_evo_claws(project_id, limit=args.limit, offset=args.offset,
                                  statuses=statuses)
    check_response(resp, "listing evo-claws")
    print_json(resp.json())


def cmd_get(args):
    client, project_id = build_client()
    resp = client.get_evo_claw(project_id, args.evoclaw_id)
    check_response(resp, f"getting evo-claw {args.evoclaw_id}")
    print_json(resp.json())


def _build_create_body(args) -> dict:
    body: dict = load_config_from_args(args) or {}
    body.setdefault("type", "EVOCLAW_TYPE_OPEN_CLAW")
    if args.name:
        body["name"] = args.name
    if args.instance_type_id:
        body["instanceTypeId"] = args.instance_type_id
    if args.model_name:
        body.setdefault("options", {}) \
            .setdefault("defaultLlmOptions", {}) \
            .setdefault("foundationModels", {})["modelName"] = args.model_name
    if args.log_group_id is not None:
        logging_opts = body.setdefault("integrationOptions", {}) \
            .setdefault("logging", {})
        if args.log_group_id:
            logging_opts["isEnabled"] = True
            logging_opts["logGroupId"] = args.log_group_id
        else:
            logging_opts["isEnabled"] = False
    if args.enable_tracing:
        body.setdefault("integrationOptions", {})["tracing"] = {"isEnabled": True}
    return body


def cmd_create(args):
    client, project_id = build_client()
    body = _build_create_body(args)
    if not body.get("name"):
        print("Error: --name required (or provide via --config-json)", file=sys.stderr)
        sys.exit(1)
    if not body.get("instanceTypeId"):
        print("Error: --instance-type-id required", file=sys.stderr)
        sys.exit(1)
    resp = client.create_evo_claw(project_id, body)
    check_response(resp, "creating evo-claw")
    print_json(resp.json())


def cmd_update(args):
    client, project_id = build_client()
    body = load_config_from_args(args) or {}
    if args.description is not None:
        body["description"] = args.description
    if args.instance_type_id:
        body["instanceTypeId"] = args.instance_type_id
    if args.model_name:
        body.setdefault("options", {}) \
            .setdefault("defaultLlmOptions", {}) \
            .setdefault("foundationModels", {})["modelName"] = args.model_name
    if not body:
        print("Error: nothing to update", file=sys.stderr)
        sys.exit(1)
    resp = client.update_evo_claw(project_id, args.evoclaw_id, body)
    check_response(resp, f"updating evo-claw {args.evoclaw_id}")
    print_json(resp.json() if resp.text else {})


def cmd_delete(args):
    confirm_destructive("delete", f"evo-claw {args.evoclaw_id}", args.yes)
    client, project_id = build_client()
    resp = client.delete_evo_claw(project_id, args.evoclaw_id)
    check_response(resp, f"deleting evo-claw {args.evoclaw_id}")
    print_json(resp.json() if resp.text else {"status": "deleted"})


def cmd_wait(args):
    client, project_id = build_client()
    wait_for_status(lambda: client.get_evo_claw(project_id, args.evoclaw_id),
                     resource_key="evoClaw",
                     resource_label=f"evo-claw {args.evoclaw_id}",
                     success_statuses=WAIT_SUCCESS, fail_statuses=WAIT_FAIL,
                     timeout=args.timeout, poll=10)


def cmd_list_workers(args):
    client, project_id = build_client()
    resp = client.list_evo_claw_workers(project_id, args.evoclaw_id)
    check_response(resp, f"listing workers of {args.evoclaw_id}")
    print_json(resp.json())


def cmd_set_workers(args):
    """Replace the full workers list (PUT semantic — not merge)."""
    client, project_id = build_client()
    workers_body = load_config_from_args(args) or {}
    workers = workers_body if isinstance(workers_body, list) else workers_body.get("agents", [])
    if not workers:
        print("Error: --config-json/--config-file must contain either an array of workers "
              "or {\"agents\": [...]}", file=sys.stderr)
        sys.exit(1)
    resp = client.set_evo_claw_workers(project_id, args.evoclaw_id, workers)
    check_response(resp, f"setting workers on {args.evoclaw_id}")
    print_json(resp.json() if resp.text else {})


def _load_workers(client, project_id, evoclaw_id) -> list:
    resp = client.list_evo_claw_workers(project_id, evoclaw_id)
    if resp.status_code >= 400:
        # BFF sometimes returns 500 with OpenClawGatewayToken error; fall back to empty
        print(f"Warning: list-workers returned {resp.status_code}, starting from empty",
              file=sys.stderr)
        return []
    data = resp.json()
    return data.get("agents") or data.get("data") or []


def cmd_add_worker(args):
    """Fetch current workers, append a new one, PUT back."""
    client, project_id = build_client()
    worker_cfg = load_config_from_args(args) or {}
    if args.name:
        worker_cfg["name"] = args.name
    if args.description:
        worker_cfg["description"] = args.description
    if args.system_prompt:
        worker_cfg["systemPrompt"] = args.system_prompt
    if args.workspace:
        worker_cfg["workspace"] = args.workspace
    if args.model_name:
        worker_cfg.setdefault("llmOptions", {}) \
            .setdefault("foundationModels", {})["modelName"] = args.model_name
    if not worker_cfg.get("name"):
        print("Error: worker --name required", file=sys.stderr); sys.exit(1)
    worker_cfg.setdefault("workspace", f"./workspace/{worker_cfg['name']}")
    worker_cfg.setdefault("contextTokens", 1000)
    worker_cfg.setdefault("sandboxMode", "OPEN_CLAW_SANDBOX_MODE_UNKNOWN")
    worker_cfg.setdefault("skills", [])
    worker_cfg.setdefault("llmOptions", {}) \
        .setdefault("modelParameters", {"temperature": 0.2, "maxTokens": 500})
    workers = _load_workers(client, project_id, args.evoclaw_id)
    # Replace by name if exists
    workers = [w for w in workers if w.get("name") != worker_cfg["name"]]
    workers.append(worker_cfg)
    resp = client.set_evo_claw_workers(project_id, args.evoclaw_id, workers)
    check_response(resp, f"adding worker to {args.evoclaw_id}")
    print_json(resp.json() if resp.text else {"agents": workers})


def cmd_remove_worker(args):
    client, project_id = build_client()
    workers = _load_workers(client, project_id, args.evoclaw_id)
    new = [w for w in workers if w.get("name") != args.name]
    if len(new) == len(workers):
        print(f"Error: no worker named {args.name!r}", file=sys.stderr); sys.exit(1)
    resp = client.set_evo_claw_workers(project_id, args.evoclaw_id, new)
    check_response(resp, f"removing worker {args.name}")
    print_json(resp.json() if resp.text else {"agents": new})


COMMANDS = {
    "evo-claws.list": cmd_list,
    "evo-claws.get": cmd_get,
    "evo-claws.create": cmd_create,
    "evo-claws.update": cmd_update,
    "evo-claws.delete": cmd_delete,
    "evo-claws.wait": cmd_wait,
    "evo-claws.list-workers": cmd_list_workers,
    "evo-claws.set-workers": cmd_set_workers,
    "evo-claws.add-worker": cmd_add_worker,
    "evo-claws.remove-worker": cmd_remove_worker,
}
