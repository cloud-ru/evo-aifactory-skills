"""CRUD commands for model runs: list, get, create, update, delete, suspend, resume."""

import sys

from helpers import (
    FRAMEWORK_ENUM_MAP,
    RESOURCE_ENUM_MAP,
    TASK_ENUM_MAP,
    build_client,
    check_response,
    print_json,
)


def cmd_list(args):
    client, project_id = build_client()
    res = client.list_model_runs(project_id, limit=args.limit or 100, offset=args.offset or 0)
    check_response(res, "listing model runs")
    data = res.json()
    all_runs = data.get("modelRuns", [])

    # Filter by --status if provided
    if getattr(args, "status", None):
        all_runs = [mr for mr in all_runs if mr.get("status") == args.status]

    # Hide deleted runs by default unless --all is set
    hidden = 0
    show_all = getattr(args, "all", False)
    if not getattr(args, "status", None) and not show_all:
        visible = []
        for mr in all_runs:
            if mr.get("status") == "MODEL_RUN_STATUS_DELETED":
                hidden += 1
            else:
                visible.append(mr)
        all_runs = visible

    print(f"Total: {data.get('total', '?')}")
    for mr in all_runs:
        print(
            f"  {mr['modelRunId']} | {mr['name']} | {mr['status']} | "
            f"{mr.get('frameworkType', '')} | {mr.get('resourceType', '')} | gpu={mr.get('gpuCount', '?')}"
        )
    if hidden > 0:
        print(f"\n(hiding {hidden} deleted runs, use --all to show)")


def cmd_get(args):
    client, project_id = build_client()
    res = client.get_model_run(project_id, args.model_run_id)
    check_response(res, "getting model run details")
    mr = res.json().get("modelRun", res.json())

    if getattr(args, "output_json", False):
        print_json(mr)
        return

    # Compact human-readable output
    print(f"Name:          {mr.get('name', '?')}")
    print(f"ID:            {mr.get('modelRunId', '?')}")
    print(f"Status:        {mr.get('status', '?')}")
    print(f"Framework:     {mr.get('frameworkType', '?')}")
    print(f"Resource:      {mr.get('resourceType', '?')}")
    print(f"GPU count:     {mr.get('gpuCount', '?')}")

    # Model source
    source = mr.get("modelSource", {})
    for src_key in ("huggingFaceRepository", "ollama", "modelRegistry", "modelScope"):
        src = source.get(src_key)
        if src:
            print(f"Model source:  {src.get('repo', '')}/{src.get('model', '')}")
            break

    # Scaling
    scaling = mr.get("scaling", {})
    print(f"Scaling:       min={scaling.get('minScale', '?')} max={scaling.get('maxScale', '?')}")

    # Auth
    options = mr.get("options", {})
    auth = "yes" if options.get("isEnabledAuth") else "no"
    print(f"Auth enabled:  {auth}")

    # Endpoint
    endpoint = mr.get("publicUrl") or mr.get("endpoint") or f"{mr.get('modelRunId', '?')}.modelrun.inference.cloud.ru"
    print(f"Endpoint:      {endpoint}")

    # Timestamps
    print(f"Created at:    {mr.get('createdAt', '?')}")
    print(f"Updated at:    {mr.get('updatedAt', '?')}")


def cmd_create(args):
    """Create a model run using raw JSON payload."""
    client, project_id = build_client()

    fw = args.framework.upper()
    framework_val = FRAMEWORK_ENUM_MAP.get(fw)
    if not framework_val:
        print(f"Unknown framework: {args.framework}", file=sys.stderr)
        sys.exit(1)

    resource_val = RESOURCE_ENUM_MAP.get(args.resource.upper()) if args.resource else "ResourceType_GPU_A100_NVLINK"
    task_val = TASK_ENUM_MAP.get(args.task.upper()) if args.task else "ModelTaskType_GENERATE"

    # Build model source
    repo = args.repo or ""
    model_name = args.model_name
    if not model_name and "/" in repo:
        repo, model_name = repo.split("/", 1)

    if args.source_type == "huggingface":
        model_source = {
            "huggingFaceRepository": {
                "repo": repo,
                "model": model_name or "",
                "revision": args.revision or "main",
                "filePaths": [],
            },
            "secret": "",
            "repoSize": 0,
        }
    elif args.source_type == "ollama":
        model_source = {
            "ollama": {
                "model": model_name or repo,
                "repo": "",
                "revision": "",
            },
            "secret": "",
            "repoSize": 0,
        }
    elif args.source_type == "registry":
        model_source = {
            "modelRegistry": {
                "repo": repo,
                "model": model_name or "",
                "revision": args.revision or "",
            },
            "secret": "",
            "repoSize": 0,
        }
    elif args.source_type == "modelscope":
        model_source = {
            "modelScope": {
                "repo": repo,
                "model": model_name or "",
                "revision": args.revision or "",
            },
            "secret": "",
            "repoSize": 0,
        }
    else:
        model_source = {}

    # Build serving options
    serving_options = {}
    if fw in ("VLLM", "SGLANG"):
        dyn_args = args.vllm_args if hasattr(args, "vllm_args") and args.vllm_args else []
        serving_options = {
            "dynamicalOptions": {
                "args": dyn_args,
                "loraModules": [],
            }
        }
    elif fw == "OLLAMA":
        serving_options = {"ollamaOptions": {}}
    elif fw == "TRANSFORMERS":
        serving_options = {"transformersOptions": {}}
    elif fw == "DIFFUSERS":
        serving_options = {"diffusersOptions": {}}

    # Build scaling
    min_scale = args.min_scale if args.min_scale is not None else 1
    max_scale = args.max_scale if args.max_scale is not None else 1
    scaling = {
        "minScale": min_scale,
        "maxScale": max_scale,
        "scalingRules": {"rpsType": {"value": 200}},
    }

    # Resolve runtime template if not provided
    runtime_template_id = args.runtime_template_id
    if not runtime_template_id:
        rt_res = client.get_frameworks(project_id)
        if rt_res.is_success:
            for rt in rt_res.json().get("runtimeTemplates", []):
                if rt.get("frameworkType") == framework_val and rt.get("isActive"):
                    runtime_template_id = rt["id"]
                    break
        if not runtime_template_id:
            print("Error: could not auto-detect runtime template. Pass --runtime-template-id.", file=sys.stderr)
            sys.exit(1)

    payload = {
        "name": args.name,
        "frameworkType": framework_val,
        "resourceType": resource_val,
        "gpuCount": args.gpu_count or 1,
        "gpuGbMemory": args.gpu_memory or 20,
        "modelTaskType": task_val,
        "runtimeTemplateId": runtime_template_id,
        "modelSource": model_source,
        "servingOptions": serving_options,
        "scaling": scaling,
        "options": {
            "isEnabledAuth": True,
            "isEnabledLogging": False,
        },
    }

    res = client.create_model_run(project_id, payload)
    check_response(res, "creating model run")
    data = res.json()
    print(f"Created model run: {data.get('modelRunId', data)}")


def cmd_update(args):
    client, project_id = build_client()

    payload = {}
    if args.name:
        payload["name"] = args.name
    if args.min_scale is not None or args.max_scale is not None:
        payload["scaling"] = {
            "minScale": args.min_scale if args.min_scale is not None else 0,
            "maxScale": args.max_scale if args.max_scale is not None else 1,
            "scalingRules": {
                "concurrencyType": {"soft": 1, "hard": 2},
            },
            "keepAliveDuration": {
                "hours": 0,
                "minutes": args.keep_alive_minutes or 15,
                "seconds": 0,
            },
        }

    res = client.update_model_run(project_id, args.model_run_id, payload)
    check_response(res, "updating model run")
    print("Updated successfully")


def cmd_delete(args):
    client, project_id = build_client()
    res = client.delete_model_run(project_id, args.model_run_id)
    check_response(res, "deleting model run")
    print("Deleted successfully")


def cmd_suspend(args):
    client, project_id = build_client()
    res = client.suspend_model_run(project_id, args.model_run_id)
    check_response(res, "suspending model run")
    print("Suspended successfully")


def cmd_resume(args):
    client, project_id = build_client()
    res = client.resume_model_run(project_id, args.model_run_id)
    check_response(res, "resuming model run")
    print("Resumed successfully")
