"""CLI handlers for `workflows` (AI Workflows, Preview) subcommand.

Workflows — low-code графовые пайплайны (узлы + связи). CLI умеет создавать
пустой workflow-контейнер (имя + log-группа) и править meta-поля; full
редактирование графа (nodes/connections) делается в IDE через UI.
"""

import sys

from helpers import (build_client, check_response, print_json, load_config_from_args,
                     confirm_destructive)


def cmd_list(args):
    client, project_id = build_client()
    statuses = args.statuses.split(",") if getattr(args, "statuses", None) else None
    resp = client.list_workflows(project_id, limit=args.limit, offset=args.offset,
                                  search=args.search, statuses=statuses)
    check_response(resp, "listing workflows")
    print_json(resp.json())


def cmd_get(args):
    client, project_id = build_client()
    resp = client.get_workflow(project_id, args.workflow_id)
    check_response(resp, f"getting workflow {args.workflow_id}")
    print_json(resp.json())


def cmd_delete(args):
    confirm_destructive("delete", f"workflow {args.workflow_id}", args.yes)
    client, project_id = build_client()
    resp = client.delete_workflow(project_id, args.workflow_id)
    check_response(resp, f"deleting workflow {args.workflow_id}")
    print_json(resp.json() if resp.text else {})


def cmd_create(args):
    client, project_id = build_client()
    body: dict = load_config_from_args(args)
    if args.name:
        body["name"] = args.name
    if args.description is not None:
        body["description"] = args.description
    if args.log_group_id:
        body.setdefault("integrationOptions", {}).setdefault("logging", {})[
            "logGroupId"] = args.log_group_id
        body["integrationOptions"]["logging"]["isEnabledLogging"] = True
    if not body.get("name"):
        print("Error: --name required", file=sys.stderr)
        sys.exit(1)
    resp = client.create_workflow(project_id, body)
    check_response(resp, "creating workflow")
    print_json(resp.json())


def cmd_update(args):
    client, project_id = build_client()
    body: dict = load_config_from_args(args)
    if args.name:
        body["name"] = args.name
    if args.description is not None:
        body["description"] = args.description
    if args.log_group_id:
        body.setdefault("integrationOptions", {}).setdefault("logging", {})[
            "logGroupId"] = args.log_group_id
    if not body:
        print("Error: nothing to update", file=sys.stderr)
        sys.exit(1)
    resp = client.update_workflow(project_id, args.workflow_id, body)
    check_response(resp, f"updating workflow {args.workflow_id}")
    print_json(resp.json() if resp.text else {})


COMMANDS = {
    "workflows.list": cmd_list,
    "workflows.get": cmd_get,
    "workflows.create": cmd_create,
    "workflows.update": cmd_update,
    "workflows.delete": cmd_delete,
}
