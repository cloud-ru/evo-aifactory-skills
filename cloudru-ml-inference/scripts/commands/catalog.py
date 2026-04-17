"""Catalog commands: browse predefined models and deploy them."""

import re
import sys
import time

from helpers import build_client, check_response

# Model run names: only latin letters, digits, hyphens
NAME_RE = re.compile(r'^[a-z][a-z0-9\-]*$')


def cmd_catalog(args):
    """List predefined models from the Cloud.ru catalog."""
    client, _ = build_client()
    params = {"limit": args.limit or 100, "offset": args.offset or 0}
    if args.query:
        params["query"] = args.query
    if args.sort:
        params["sort"] = args.sort

    res = client.get_catalog(**params)
    check_response(res, "fetching catalog")

    data = res.json()
    total = data.get("total", 0)
    has_more = data.get("hasMore", False)
    cards = data.get("modelCards", [])
    print(f"Predefined models ({len(cards)} shown, {total} total, hasMore={has_more}):\n")
    for c in cards:
        tags = ", ".join(c.get("tags", []))
        tags_str = f" [{tags}]" if tags else ""
        print(
            f"  {c['id']} | {c['name']:<40} | {c.get('vendorName',''):<10} "
            f"| {c.get('paramsBn','')}B | ctx={c.get('contextK','')}K "
            f"| {c.get('price','')} rub/hour{tags_str}"
        )


def cmd_catalog_detail(args):
    """Show detailed configs for a predefined model."""
    client, _ = build_client()
    res = client.get_catalog_detail(args.model_card_id)
    check_response(res, "fetching model card")

    data = res.json()
    card = data.get("modelCard", {})
    configs = data.get("modelCardConfigs", [])

    print(f"Model: {card.get('name', '?')}")
    print(f"Vendor: {card.get('vendorName', '?')}")
    print(f"Task: {card.get('taskType', '?')}")
    print(f"Params: {card.get('paramsBn', '?')}B | Context: {card.get('contextK', '?')}K")
    print(f"License: {card.get('licenseName', '?')}")
    print(f"Description: {card.get('description', '')[:200]}")
    print(f"\nAvailable configurations ({len(configs)}):")
    for i, cfg in enumerate(configs):
        print(
            f"\n  [{i}] GPU: {cfg.get('allowedGpu', '?')} x{cfg.get('gpuCount', '?')} "
            f"({cfg.get('gpuMemoryAllocGb', '?')}GB) | "
            f"Framework: {cfg.get('frameworkType', '?')} {cfg.get('frameworkVersion', '')} | "
            f"Price: {cfg.get('price', '?')} rub/hour"
        )
        print(f"      Config ID: {cfg.get('id', '?')}")
        print(f"      Runtime: {cfg.get('runtimeTemplateId', '?')}")


def cmd_deploy(args):
    """Deploy a predefined model — fetches exact config from catalog and creates model run."""
    client, project_id = build_client()

    res = client.get_catalog_detail(args.model_card_id)
    check_response(res, "fetching model card")

    data = res.json()
    card = data.get("modelCard", {})
    configs = data.get("modelCardConfigs", [])

    if not configs:
        print("Error: no configurations available for this model", file=sys.stderr)
        sys.exit(1)

    config_index = args.config_index if args.config_index is not None else 0
    if config_index >= len(configs):
        print(f"Error: config index {config_index} out of range (0-{len(configs)-1})", file=sys.stderr)
        sys.exit(1)
    cfg = configs[config_index]

    raw_name = args.name or card.get("name", "model-run")
    # Sanitize: lowercase, replace non-alphanum with hyphens, collapse
    model_name = re.sub(r'[^a-z0-9\-]', '-', raw_name.lower())
    model_name = re.sub(r'-+', '-', model_name).strip('-')
    if not model_name or not model_name[0].isalpha():
        model_name = "model-" + model_name
    task_type = card.get("taskType", "ModelTaskType_GENERATE")

    payload = {
        "name": model_name,
        "frameworkType": cfg["frameworkType"],
        "resourceType": cfg["allowedGpu"],
        "gpuCount": cfg["gpuCount"],
        "gpuGbMemory": cfg["gpuMemoryAllocGb"],
        "modelTaskType": task_type,
        "runtimeTemplateId": cfg["runtimeTemplateId"],
        "modelSource": card.get("modelSource", {}),
        "servingOptions": cfg.get("servingOptions", {}),
        "scaling": cfg.get("scaling", {"minScale": 1, "maxScale": 1, "scalingRules": {"rpsType": {"value": 200}}}),
        "options": {
            "isEnabledAuth": True,
            "isEnabledLogging": False,
        },
    }

    print(f"Deploying '{card.get('name', '?')}' with config [{config_index}]:")
    print(f"  GPU: {cfg.get('allowedGpu')} x{cfg.get('gpuCount')} ({cfg.get('gpuMemoryAllocGb')}GB)")
    print(f"  Framework: {cfg.get('frameworkType')} {cfg.get('frameworkVersion', '')}")
    print(f"  Price: {cfg.get('price', '?')} rub/hour")

    create_res = client.create_model_run(project_id, payload)

    # Handle name collision — retry with suffixed names
    if not create_res.is_success and "name" in create_res.text.lower():
        for suffix in range(2, 6):
            new_name = f"{model_name}-{suffix}"
            print(f"Name '{payload['name']}' is taken, trying '{new_name}'...")
            payload["name"] = new_name
            create_res = client.create_model_run(project_id, payload)
            if create_res.is_success:
                break

    check_response(create_res, "creating model run")

    result = create_res.json()
    model_run_id = result.get("modelRunId", result)
    print(f"\nCreated model run: {model_run_id}")
    print(f"Public URL: https://{model_run_id}.modelrun.inference.cloud.ru")

    # --wait: poll until RUNNING
    if getattr(args, "wait", False) and model_run_id:
        print("Waiting for model to become RUNNING...")
        deadline = time.time() + (getattr(args, "wait_timeout", 600) or 600)
        last_status = None
        while time.time() < deadline:
            r = client.get_model_run(project_id, model_run_id)
            if r.is_success:
                mr = r.json().get("modelRun", r.json())
                status = mr.get("status", "?")
                if status != last_status:
                    print(f"  Status: {status}")
                    last_status = status
                if status == "MODEL_RUN_STATUS_RUNNING":
                    print("Model is RUNNING!")
                    return
                if "FAILED" in status or "DELETED" in status:
                    print(f"Error: model entered status {status}", file=sys.stderr)
                    sys.exit(1)
            time.sleep(15)
        print(f"Warning: timed out waiting for RUNNING (last: {last_status})", file=sys.stderr)
