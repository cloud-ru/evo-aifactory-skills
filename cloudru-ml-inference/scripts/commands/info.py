"""Info commands: history, quotas, frameworks."""

from helpers import build_client, check_response


def cmd_history(args):
    client, project_id = build_client()
    res = client.get_history(project_id, args.model_run_id)
    check_response(res, "getting history")
    for event in res.json().get("events", []):
        print(f"  {event.get('eventType', '?')} at {event.get('version', '?')} by {event.get('authorId', '?')}")


def cmd_quotas(args):
    client, project_id = build_client()
    res = client.get_quotas(project_id)
    check_response(res, "getting quotas")
    for q in res.json().get("data", []):
        print(f"  {q['resourceType']}: {q['free']} free / {q['limit']} total")


def cmd_frameworks(args):
    client, project_id = build_client()
    res = client.get_frameworks(project_id)
    check_response(res, "getting frameworks")
    for rt in res.json().get("runtimeTemplates", []):
        gpus = ", ".join(
            f"{g['resourceType']}{'(default)' if g.get('isDefault') else ''}"
            for g in rt.get("gpus", [])
            if g.get("isAllowed")
        )
        active = "active" if rt.get("isActive") else "inactive"
        print(f"  {rt['frameworkType']} v{rt['version']} [{active}] (id={rt['id']}) GPUs: [{gpus}]")
