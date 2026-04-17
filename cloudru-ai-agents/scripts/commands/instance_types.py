"""CLI handlers for `instance-types` subcommand."""

from helpers import build_client, check_response, print_json


def cmd_list(args):
    client, project_id = build_client()
    resp = client.list_instance_types(project_id)
    check_response(resp, "listing instance types")
    print_json(resp.json())


COMMANDS = {
    "instance-types.list": cmd_list,
}
