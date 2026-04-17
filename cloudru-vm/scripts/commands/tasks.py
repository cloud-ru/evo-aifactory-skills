"""Task tracking commands."""

from helpers import build_client, check_response, print_json


def cmd_task(args):
    client, _ = build_client()
    res = client.get_task(args.task_id)
    check_response(res, "getting task")
    print_json(res.json())
