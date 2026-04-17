"""CLI handlers for `skills` (Навыки) subcommand."""

import json
import sys

from helpers import (build_client, check_response, print_json, load_config_from_args,
                     confirm_destructive)


def _serialize_metadata(metadata: dict) -> dict:
    """Skill metadata is map<string,string>: serialize list/dict values as JSON strings."""
    out = {}
    for k, v in metadata.items():
        if isinstance(v, (list, dict)):
            out[k] = json.dumps(v, ensure_ascii=False)
        else:
            out[k] = str(v) if v is not None else ""
    return out


def cmd_list(args):
    client, project_id = build_client()
    not_in = args.not_in_statuses.split(",") if getattr(args, "not_in_statuses", None) else None
    resp = client.list_skills(project_id, limit=args.limit, offset=args.offset,
                               name=args.search, not_in_statuses=not_in)
    check_response(resp, "listing skills")
    print_json(resp.json())


def cmd_get(args):
    client, project_id = build_client()
    resp = client.get_skill(project_id, args.skill_id)
    check_response(resp, f"getting skill {args.skill_id}")
    print_json(resp.json())


def cmd_create(args):
    client, project_id = build_client()
    body: dict = load_config_from_args(args)
    # Install from marketplace: reuse name/description/compatibility/metadata from card,
    # build gitSource from metadata.repo/branch/path.
    if getattr(args, "from_marketplace", None):
        card_resp = client.get_marketplace_skill(args.from_marketplace)
        check_response(card_resp, f"fetching marketplace skill {args.from_marketplace}")
        card = card_resp.json().get("skill", card_resp.json())
        body.setdefault("name", card.get("name"))
        body.setdefault("description", card.get("description", ""))
        body.setdefault("compatibility", card.get("compatibility", ""))
        md = card.get("metadata") or {}
        repo = md.get("upstream") or (f"https://github.com/{md['repo']}" if md.get("repo") else None)
        if repo and not body.get("skillSource"):
            gs: dict = {"gitUrl": repo}
            if args.git_token:
                gs["accessToken"] = args.git_token
            if md.get("path"):
                gs["skillFolderPaths"] = [md["path"]]
            body["skillSource"] = {"gitSource": gs}
        # Preserve metadata (branch, version, ...) from marketplace card
        if md:
            body.setdefault("metadata", {}).update({k: v for k, v in md.items()
                                                     if isinstance(v, str)})
        # Preserve allowedTools from card
        at = card.get("allowedTools")
        if at and not body.get("allowedTools"):
            body["allowedTools"] = at
    if args.name:
        body["name"] = args.name
    if args.description is not None:
        body["description"] = args.description
    if args.compatibility:
        body["compatibility"] = args.compatibility

    metadata = body.get("metadata") or {}
    if args.prompt:
        metadata["prompt"] = args.prompt
    if args.prompt_file:
        with open(args.prompt_file) as f:
            metadata["prompt"] = f.read()
    # Requirements & artifacts (the UI's "Добавить ограничения и требования" block)
    if getattr(args, "requirements_os", None):
        metadata["requirementsOsEnvironment"] = args.requirements_os
    if getattr(args, "requirements_apps", None):
        metadata["requirementsAppsAndTools"] = args.requirements_apps
    if getattr(args, "requirements_secrets", None):
        metadata["requirementsSecrets"] = args.requirements_secrets
    if getattr(args, "artifact_paths", None):
        metadata["artifactPaths"] = args.artifact_paths
    if getattr(args, "resources_url", None):
        metadata["resourcesRepositoryUrl"] = args.resources_url
    metadata.setdefault("resourcesSourceType", "objectStorage")
    metadata.setdefault("resourcesRepositoryUrl", "")
    metadata.setdefault("resourcesRepositorySecrets", "[]")
    metadata.setdefault("requirementsOsEnvironment", "")
    metadata.setdefault("requirementsAppsAndTools", "")
    metadata.setdefault("requirementsSecrets", "[]")
    metadata.setdefault("artifactPaths", "[]")
    body["metadata"] = _serialize_metadata(metadata)

    # allowedTools — UI lets user pick tool names (read_file/grep/run_terminal_cmd/...)
    if getattr(args, "allowed_tools", None):
        body["allowedTools"] = [t.strip() for t in args.allowed_tools.split(",") if t.strip()]
    body.setdefault("allowedTools", body.get("allowedTools") or [])
    if not body.get("skillSource"):
        if args.git_url:
            gs: dict = {"gitUrl": args.git_url}
            if args.git_token:
                gs["accessToken"] = args.git_token
            if args.git_folder_paths:
                gs["skillFolderPaths"] = args.git_folder_paths.split(",")
            body["skillSource"] = {"gitSource": gs}
        else:
            body["skillSource"] = {"plaintext": {}}

    if not body.get("name"):
        print("Error: --name required", file=sys.stderr)
        sys.exit(1)
    resp = client.create_skill(project_id, body)
    check_response(resp, "creating skill")
    print_json(resp.json())


def cmd_analyze(args):
    """Probe git/file source for skill — returns fileTree + skillFolderPaths."""
    client, project_id = build_client()
    body: dict = load_config_from_args(args)
    if args.git_url:
        gs: dict = {"gitUrl": args.git_url}
        if args.git_token:
            gs["accessToken"] = args.git_token
        body = {"gitSource": gs}
    if not body:
        print("Error: --git-url or --config-json required", file=sys.stderr)
        sys.exit(1)
    resp = client.analyze_skill_source(project_id, body)
    check_response(resp, "analyzing skill source")
    print_json(resp.json())


def cmd_delete(args):
    confirm_destructive("delete", f"skill {args.skill_id}", args.yes)
    client, project_id = build_client()
    resp = client.delete_skill(project_id, args.skill_id)
    check_response(resp, f"deleting skill {args.skill_id}")
    print_json(resp.json() if resp.text else {})


COMMANDS = {
    "skills.list": cmd_list,
    "skills.get": cmd_get,
    "skills.create": cmd_create,
    "skills.delete": cmd_delete,
    "skills.analyze": cmd_analyze,
}
