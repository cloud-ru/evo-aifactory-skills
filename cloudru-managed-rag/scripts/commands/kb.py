"""Knowledge base management commands."""

import os
import re
import sys

from helpers import build_client, check_response, get_env, print_json

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _validate_id(value: str, label: str) -> str:
    """Validate that a value is a well-formed UUID."""
    if not _UUID_RE.match(value):
        print(f"Error: {label} must be a valid UUID, got: {value}", file=sys.stderr)
        sys.exit(1)
    return value


def _get_kb_id(args):
    """Get KB ID from args or env."""
    kb_id = getattr(args, "kb_id", None)
    if not kb_id:
        kb_id = get_env("MANAGED_RAG_KB_ID")
    return _validate_id(kb_id, "kb_id")


def cmd_list(args):
    client, project_id = build_client()
    res = client.list_kbs(project_id)
    check_response(res, "listing knowledge bases")
    data = res.json()
    kbs = data.get("data", [])
    output = {"total": len(kbs), "knowledge_bases": []}
    for kb in kbs:
        entry = {
            "id": kb.get("knowledgebase_id", ""),
            "name": kb.get("name", ""),
            "status": kb.get("status", ""),
            "description": kb.get("description", ""),
            "created_at": kb.get("created_at", ""),
        }
        search_api = kb.get("searchApiResponse", {})
        if search_api.get("url"):
            entry["search_url"] = search_api["url"]
            entry["search_state"] = search_api.get("state", "")
        output["knowledge_bases"].append(entry)
    print_json(output)


def cmd_get(args):
    client, project_id = build_client()
    kb_id = _get_kb_id(args)
    res = client.get_kb(kb_id, project_id)
    check_response(res, f"getting KB {kb_id}")
    data = res.json()
    output = {
        "id": data.get("knowledgebase_id", ""),
        "project_id": data.get("project_id", ""),
        "name": data.get("name", ""),
        "namespace": data.get("namespace", ""),
        "status": data.get("status", ""),
        "description": data.get("description", ""),
        "created_at": data.get("created_at", ""),
        "updated_at": data.get("updated_at", ""),
    }
    search_api = data.get("searchApiResponse", {})
    if search_api:
        output["search_api"] = {
            "url": search_api.get("url", ""),
            "state": search_api.get("state", ""),
        }
    embedder = data.get("embedder")
    if embedder:
        output["embedder"] = embedder
    config = data.get("knowledge_base_configuration")
    if config:
        output["configuration"] = config
    print_json(output)


def cmd_versions(args):
    client, project_id = build_client()
    kb_id = _get_kb_id(args)
    res = client.list_versions(kb_id, project_id)
    check_response(res, f"listing versions for KB {kb_id}")
    data = res.json()
    versions = data.get("data", [])
    output = {"total": len(versions), "versions": []}
    for v in versions:
        output["versions"].append({
            "version_id": v.get("knowledgebase_version_id", ""),
            "version": v.get("version", ""),
            "status": v.get("status", ""),
            "description": v.get("description", ""),
            "created_at": v.get("created_at", ""),
            "started_at": v.get("started_at", ""),
            "finished_at": v.get("finished_at", ""),
        })
    print_json(output)


def cmd_version_detail(args):
    client, project_id = build_client()
    kb_id = _get_kb_id(args) if getattr(args, "kb_id", None) else os.environ.get("MANAGED_RAG_KB_ID", "")
    _validate_id(args.version_id, "version_id")
    res = client.get_version(args.version_id, project_id, kb_id=kb_id)
    check_response(res, f"getting version {args.version_id}")
    data = res.json()
    output = {
        "version_id": data.get("knowledgebase_version_id", ""),
        "knowledgebase_id": data.get("knowledgebase_id", ""),
        "project_id": data.get("project_id", ""),
        "version": data.get("version", ""),
        "status": data.get("status", ""),
        "description": data.get("description", ""),
        "created_at": data.get("created_at", ""),
        "updated_at": data.get("updated_at", ""),
        "started_at": data.get("started_at", ""),
        "finished_at": data.get("finished_at", ""),
    }
    embedder = data.get("embedder")
    if embedder:
        output["embedder"] = embedder
    settings = data.get("knowledge_base_version_settings")
    if settings:
        output["settings"] = settings
    print_json(output)


def cmd_delete(args):
    client, project_id = build_client()
    kb_id = _get_kb_id(args)
    res = client.delete_kb(kb_id, project_id)
    check_response(res, f"deleting KB {kb_id}")
    print_json({"status": "deleted", "kb_id": kb_id})


def cmd_reindex(args):
    client, project_id = build_client()
    kb_id = getattr(args, "kb_id", None) or get_env("MANAGED_RAG_KB_ID")
    _validate_id(args.version_id, "version_id")
    res = client.reindex_version(args.version_id, kb_id, project_id)
    check_response(res, f"reindexing version {args.version_id}")
    print_json(res.json())
