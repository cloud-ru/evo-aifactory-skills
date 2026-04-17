"""Shared high-level flag helpers used by create/update commands across
agents, agent systems, mcp-servers. Each helper applies a group of flags onto
the target dict, but only when user explicitly set them (so we don't clobber
server defaults or values supplied via --config-json).
"""

import sys
import time
from typing import Any, Callable, Iterable

from helpers import check_response, print_json


def wait_for_status(getter: Callable, *, resource_key: str, resource_label: str,
                    success_statuses: Iterable[str], fail_statuses: Iterable[str],
                    timeout: int, poll: int = 15) -> None:
    """Poll `getter()` until status falls into success/fail/timeout.

    getter: zero-arg callable returning httpx.Response
    resource_key: field name under which the resource sits in the response JSON
        (e.g. "agent", "mcpServer", "agentSystem", "evoClaw") — falls back to
        the whole body if that key is absent.
    """
    success_statuses = set(success_statuses)
    fail_statuses = set(fail_statuses)
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        resp = getter()
        check_response(resp, f"polling {resource_label}")
        raw = resp.json()
        data = raw.get(resource_key, raw)
        status = data.get("status")
        if status != last_status:
            print(f"status={status}", file=sys.stderr)
            last_status = status
        if status in success_statuses:
            print_json(data)
            return
        if status in fail_statuses:
            print(f"Error: {resource_label} reached failure state: {status}", file=sys.stderr)
            reason = data.get("statusReason")
            if reason:
                print(f"statusReason: {reason}", file=sys.stderr)
            sys.exit(1)
        time.sleep(poll)
    print(f"Error: timeout after {timeout}s. Last status: {last_status}", file=sys.stderr)
    sys.exit(1)


def dig(d: dict, *keys: str) -> dict:
    """Walk/create nested dicts so `d[k0][k1]...` is returned (ready to mutate)."""
    for k in keys:
        d = d.setdefault(k, {})
    return d


def apply_scaling(scaling: dict, args) -> None:
    """Populate a scaling{} dict. BFF requires all fields explicitly — it does
    not inject defaults server-side — so we seed everything the UI sends.

    Defaults mirror UI: minScale=1, maxScale=1, keepAlive 5 min, rps=200,
    scaleUpAllSystem=true.
    """
    scaling.setdefault("_meta", {"scalingRulesType": "rps"})
    dig(scaling, "scalingRules", "rps").setdefault("value", 200)
    scaling.setdefault("minScale", 1)
    scaling.setdefault("maxScale", 1)
    scaling.setdefault("isScaleUpAllSystem", True)
    scaling.setdefault("isKeepAlive", True)
    scaling.setdefault("keepAliveDuration", {"hours": 0, "minutes": 5, "seconds": 0})
    if getattr(args, "min_scale", None) is not None:
        scaling["minScale"] = args.min_scale
    if getattr(args, "max_scale", None) is not None:
        scaling["maxScale"] = args.max_scale
    if getattr(args, "keep_alive_min", None) is not None:
        scaling["isKeepAlive"] = args.keep_alive_min > 0
        scaling["keepAliveDuration"] = {
            "hours": 0, "minutes": args.keep_alive_min, "seconds": 0,
        }
    if getattr(args, "rps", None) is not None:
        scaling["scalingRules"]["rps"]["value"] = args.rps


def apply_bff_agent_defaults(body: dict) -> None:
    """Seed the defaults BFF requires on POST /agents when the user didn't
    supply them via flags or --config-json. Without these BFF nil-derefs with
    HTTP 500 because server-side code path assumes every optional field is
    present with a concrete value (not null).

    Reverse-engineered from UI's POST payload. Safe to call multiple times —
    uses setdefault so explicit values are preserved.
    """
    body.setdefault("neighbors", [])
    body.setdefault("mcpServers", [])
    opts = body.setdefault("options", {})
    # scaling block — always ensure minimum shape (apply_scaling may have set more)
    scaling = opts.setdefault("scaling", {})
    scaling.setdefault("_meta", {"scalingRulesType": "rps"})
    dig(scaling, "scalingRules", "rps").setdefault("value", 200)
    scaling.setdefault("minScale", 1)
    scaling.setdefault("maxScale", 1)
    scaling.setdefault("isScaleUpAllSystem", True)
    scaling.setdefault("isKeepAlive", True)
    scaling.setdefault("keepAliveDuration", {"hours": 0, "minutes": 5, "seconds": 0})
    # runtimeOptions
    rt = opts.setdefault("runtimeOptions", {})
    rt.setdefault("maxLlmCalls", 10)
    rt.setdefault("reflectAndRetry", {"enabled": True, "maxRetries": 10})
    rt.setdefault("eventsCompaction", {"enabled": True, "interval": 10, "overlapSize": 3})
    rt.setdefault("contextCache", {"enabled": True, "intervals": 5, "ttlSeconds": 10})
    rt.setdefault("isSaveBlobFilesAsArtifacts", True)
    # memoryOptions
    mem = opts.setdefault("memoryOptions", {})
    mem.setdefault("memory", {"isEnabled": True, "embedding": {"foundationModels": {}}})
    mem.setdefault("session", {"isEnabled": True})
    mem.setdefault("artifact",
                   {"isEnabled": True,
                    "s3": {"bucketId": "00000000-0000-0000-0000-000000000000"}})
    # integrationOptions
    ig = body.setdefault("integrationOptions", {})
    ig.setdefault("authOptions", {
        "isEnabled": False,
        "serviceAccountId": "00000000-0000-0000-0000-000000000000",
        "type": "AUTHENTICATION_TYPE_TOKEN_BASED",
    })
    ig.setdefault("logging", {"isEnabledLogging": False, "logGroupId": ""})


def apply_bff_system_defaults(body: dict) -> None:
    """BFF defaults for POST /agentSystems. Same nil-deref class as agents —
    BFF expects full orchestratorOptions + options + integrationOptions shape.
    """
    body.setdefault("agents", [])
    body.setdefault("childAgentSystems", [])
    orch = body.setdefault("orchestratorOptions", {})
    scaling = orch.setdefault("scaling", {})
    scaling.setdefault("_meta", {"scalingRulesType": "rps"})
    dig(scaling, "scalingRules", "rps").setdefault("value", 150)
    scaling.setdefault("minScale", 1)
    scaling.setdefault("maxScale", 1)
    scaling.setdefault("isScaleUpAllSystem", False)
    scaling.setdefault("isKeepAlive", True)
    scaling.setdefault("keepAliveDuration", {"hours": 0, "minutes": 5, "seconds": 0})
    orch.setdefault("env", {"rawEnvs": {}, "secretEnvs": {}})
    orch.setdefault("systemPrompt", {"systemPrompt": ""})
    opts = body.setdefault("options", {})
    opts.setdefault("observability", {"isEnabled": False})
    opts.setdefault("contextStorage", {"isEnabled": False})
    ig = body.setdefault("integrationOptions", {})
    ig.setdefault("authOptions", {
        "isEnabled": False,
        "type": "AUTHENTICATION_TYPE_TOKEN_BASED",
        "serviceAccountId": "00000000-0000-0000-0000-000000000000",
    })
    ig.setdefault("logging", {
        "isEnabledLogging": False,
        "logGroupId": "00000000-0000-0000-0000-000000000000",
    })
    ig.setdefault("autoUpdateOptions", {
        "imageOptions": {"isEnabled": False, "tagMask": ""},
        "promptOptions": {"isEnabled": False},
    })


def apply_bff_mcp_defaults(body: dict) -> None:
    """BFF defaults for POST /mcpServers. Marketplace path tolerates minimal
    body; --image-uri path has not been verified end-to-end, so we seed the
    same shape the UI sends (reverse-engineered from a running project MCP).
    """
    body.setdefault("environmentOptions", {"rawEnvs": {}, "secretEnvs": {}})
    body.setdefault("exposedPorts", [])
    scaling = body.setdefault("scaling", {})
    scaling.setdefault("_meta", {"scalingRulesType": "rps"})
    dig(scaling, "scalingRules", "rps").setdefault("value", 150)
    scaling.setdefault("minScale", 1)
    scaling.setdefault("maxScale", 1)
    scaling.setdefault("isScaleUpAllSystem", False)
    scaling.setdefault("isKeepAlive", True)
    scaling.setdefault("keepAliveDuration", {"hours": 0, "minutes": 5, "seconds": 0})
    ig = body.setdefault("integrationOptions", {})
    ig.setdefault("authOptions", {
        "isEnabled": False,
        "type": "AUTHENTICATION_TYPE_TOKEN_BASED",
        "serviceAccountId": "00000000-0000-0000-0000-000000000000",
    })
    ig.setdefault("logging", {
        "isEnabledLogging": False,
        "logGroupId": "00000000-0000-0000-0000-000000000000",
    })
    ig.setdefault("autoUpdateOptions", {
        "imageOptions": {"isEnabled": False, "tagMask": ""},
        "promptOptions": {"isEnabled": False},
    })


def apply_integration(body: dict, args) -> None:
    """Populate body.integrationOptions.{logging,authOptions}."""
    if getattr(args, "log_group_id", None):
        dig(body, "integrationOptions", "logging").update({
            "isEnabledLogging": True, "logGroupId": args.log_group_id,
        })
    sa_id = getattr(args, "service_account_id", None)
    auth_enabled = getattr(args, "auth_enabled", None)
    if auth_enabled is not None or sa_id:
        auth = dig(body, "integrationOptions", "authOptions")
        if auth_enabled is not None:
            auth["isEnabled"] = auth_enabled
        if sa_id:
            auth["serviceAccountId"] = sa_id
            auth.setdefault("type", "AUTHENTICATION_TYPE_TOKEN_BASED")


def parse_kv_pairs(raw: str) -> dict:
    """Parse 'k1=v1,k2=v2' or multiple --env entries joined with commas."""
    out: dict = {}
    if not raw:
        return out
    for item in raw.split(","):
        if "=" in item:
            k, v = item.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def apply_environment(body: dict, args) -> None:
    """Populate body.environmentOptions.rawEnvs / secretEnvs from --env/--secret-env."""
    if getattr(args, "env", None):
        raw = dig(body, "environmentOptions", "rawEnvs")
        raw.update(parse_kv_pairs(args.env))
    if getattr(args, "secret_env", None):
        sec = dig(body, "environmentOptions", "secretEnvs")
        sec.update(parse_kv_pairs(args.secret_env))
    # Ensure both dicts exist if either was set (API proto)
    if body.get("environmentOptions"):
        body["environmentOptions"].setdefault("rawEnvs", {})
        body["environmentOptions"].setdefault("secretEnvs", {})


def parse_ports(raw: str) -> list:
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def add_common_scaling_flags(p) -> None:
    """Register scaling flags on an argparse subparser."""
    p.add_argument("--min-scale", type=int, help="Minimum replicas")
    p.add_argument("--max-scale", type=int, help="Maximum replicas")
    p.add_argument("--keep-alive-min", type=int,
                    help="Keep warm N minutes after last request (0 disables)")
    p.add_argument("--rps", type=int, help="RPS scaling threshold per replica")


def add_common_integration_flags(p) -> None:
    p.add_argument("--log-group-id", help="Cloud Logging group ID")
    p.add_argument("--auth-enabled", type=lambda v: v.lower() == "true",
                    help="true|false — require authentication to invoke")
    p.add_argument("--service-account-id", help="Service account for auth")


def add_environment_flags(p) -> None:
    p.add_argument("--env",
                    help="Comma-separated KEY=VALUE plain env vars")
    p.add_argument("--secret-env",
                    help="Comma-separated KEY=SECRET_REF env vars sourced from secret manager")
