#!/usr/bin/env python3
"""Bootstrap Cloud.ru service account and Foundation Models API key.

Creates a service account, creates an API key for Foundation Models,
and prints a JSON summary with the credentials.

Requires: httpx
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlencode, urlparse

import httpx

_ALLOWED_HOSTS = frozenset({"console.cloud.ru", "iam.api.cloud.ru"})

SERVICE_ACCOUNT_URL = "https://console.cloud.ru/u-api/bff-console/v2/service-accounts/add"
SERVICE_ACCOUNT_LIST_URL = "https://console.cloud.ru/u-api/bff-console/v2/service-accounts"
API_KEY_URL_TEMPLATE = (
    "https://console.cloud.ru/u-api/bff-console/v1/service-accounts/{service_account_id}/api_keys"
)
ACCESS_KEY_URL_TEMPLATE = (
    "https://console.cloud.ru/u-api/bff-console/v1/service-accounts/{service_account_id}/access_keys"
)
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


@dataclass
class ProjectContext:
    project_url: str
    project_id: Optional[str]
    customer_id: Optional[str]
    customer_id_source: Optional[str]
    notes: List[str]


class BootstrapError(RuntimeError):
    """Raised when the bootstrap flow cannot proceed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a Cloud.ru service account and Foundation Models API key."
        )
    )
    parser.add_argument(
        "--project-url",
        default="",
        help="Current Cloud.ru project URL from the browser. Used to infer project_id and customer_id.",
    )
    parser.add_argument(
        "--project-id",
        default="",
        help="Explicit project ID. Overrides project_id inferred from --project-url.",
    )
    parser.add_argument(
        "--customer-id",
        default="",
        help=(
            "Explicit Cloud.ru customerId. Overrides customer_id inferred from --project-url. "
            "The user-supplied flow sometimes calls this secret_id."
        ),
    )
    parser.add_argument(
        "--secret-id",
        default="",
        help="Alias for --customer-id. Useful when the project URL exposes secret_id instead of customerId.",
    )
    parser.add_argument(
        "--token",
        default="",
        help="Cloud.ru console bearer token. The provided flow uses the browser access_token from localStorage.",
    )
    parser.add_argument(
        "--service-account-name",
        default="foundation-models-account",
        help="Name for the created Cloud.ru service account.",
    )
    parser.add_argument(
        "--service-account-description",
        default="foundation-models-account",
        help="Description for the created Cloud.ru service account.",
    )
    parser.add_argument(
        "--project-role",
        default="PROJECT_ROLE_PROJECT_ADMIN",
        help="Project role to assign to the service account.",
    )
    parser.add_argument(
        "--api-key-name",
        default="foundation-models-api-key",
        help="Name for the created Foundation Models API key.",
    )
    parser.add_argument(
        "--api-key-description",
        default="foundation-models-api-key",
        help="Description for the created Foundation Models API key.",
    )
    parser.add_argument(
        "--product",
        default="ml_inference_ai_marketplace",
        help="Cloud.ru product code to include when creating the API key.",
    )
    parser.add_argument(
        "--timezone",
        type=int,
        default=3,
        help="Timezone offset used in the API key restrictions payload.",
    )
    parser.add_argument(
        "--days-valid",
        type=int,
        default=365,
        help="API key validity in days. Cloud.ru docs say the maximum is one year.",
    )
    parser.add_argument(
        "--access-key-description",
        default="ml-inference-access-key",
        help="Description for the created access key (used for CP_CONSOLE_KEY_ID / CP_CONSOLE_SECRET).",
    )
    parser.add_argument(
        "--access-key-ttl",
        type=int,
        default=30,
        help="Access key TTL in days.",
    )
    parser.add_argument(
        "--skip-access-key",
        action="store_true",
        help="Skip access key creation (only create service account and API key).",
    )
    parser.add_argument(
        "--from-stdin",
        action="store_true",
        help="Read all parameters as JSON from stdin (used by browser_login.py).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not call Cloud.ru APIs. Only parse inputs and render payloads.",
    )
    return parser.parse_args()


def parse_project_context(
    project_url: str,
    explicit_project_id: str,
    explicit_customer_id: str,
    explicit_secret_id: str,
) -> ProjectContext:
    notes: List[str] = []
    if not project_url and not explicit_project_id:
        raise BootstrapError(
            "Pass --project-url or --project-id so the script can determine the target project."
        )

    project_id = explicit_project_id or None
    customer_id = explicit_customer_id or explicit_secret_id or None
    customer_id_source: Optional[str] = None

    if explicit_secret_id and not explicit_customer_id:
        customer_id_source = "--secret-id"
        notes.append("Using --secret-id as customerId because the API expects customerId.")
    elif explicit_customer_id:
        customer_id_source = "--customer-id"

    if not project_url:
        return ProjectContext(
            project_url="",
            project_id=project_id,
            customer_id=customer_id,
            customer_id_source=customer_id_source,
            notes=notes,
        )

    parsed = urlparse(project_url)
    query_map = collapse_query_maps(parsed)
    path_segments = [segment for segment in parsed.path.split("/") if segment]

    if not project_id:
        project_id = first_non_empty(
            query_map.get("project_id"),
            query_map.get("projectId"),
            query_map.get("project-id"),
            path_uuid_after(path_segments, "projects"),
            path_uuid_after(path_segments, "project"),
        )

    if not customer_id:
        inferred_customer = first_non_empty(
            query_map.get("customerId"),
            query_map.get("customer_id"),
            query_map.get("secret_id"),
            query_map.get("secretId"),
            query_map.get("secret-id"),
            path_uuid_after(path_segments, "customers"),
            path_uuid_after(path_segments, "customer"),
            path_uuid_after(path_segments, "organizations"),
            path_uuid_after(path_segments, "organization"),
        )
        customer_id = inferred_customer
        if query_map.get("secret_id") or query_map.get("secretId") or query_map.get("secret-id"):
            customer_id_source = "secret_id-from-url"
            notes.append(
                "Mapped secret_id from the project URL to customerId because the service-account API expects customerId."
            )
        elif inferred_customer:
            customer_id_source = "customerId-from-url"

    if not project_id:
        notes.append(
            "Could not infer project_id from the URL. Pass --project-id explicitly if the Cloud.ru URL format changed."
        )
    if not customer_id:
        notes.append(
            "Could not infer customerId from the URL. Pass --customer-id explicitly if the Cloud.ru URL format changed."
        )

    return ProjectContext(
        project_url=project_url,
        project_id=project_id,
        customer_id=customer_id,
        customer_id_source=customer_id_source,
        notes=notes,
    )


def collapse_query_maps(parsed) -> Dict[str, str]:
    query_map: Dict[str, str] = {}

    def merge(raw: str) -> None:
        if not raw:
            return
        pairs = parse_qs(raw, keep_blank_values=False)
        for key, values in pairs.items():
            if values:
                query_map[key] = unquote(values[-1])

    merge(parsed.query)

    fragment = parsed.fragment or ""
    if "?" in fragment:
        merge(fragment.split("?", 1)[1])
    elif "=" in fragment and "&" in fragment:
        merge(fragment)

    return query_map


def first_non_empty(*values: Optional[str]) -> Optional[str]:
    for value in values:
        if value:
            return value
    return None


def path_uuid_after(path_segments: List[str], marker: str) -> Optional[str]:
    try:
        index = path_segments.index(marker)
    except ValueError:
        return None
    if index + 1 < len(path_segments):
        candidate = path_segments[index + 1]
        if UUID_RE.fullmatch(candidate):
            return candidate
    return None


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=(dt.microsecond // 1000) * 1000).isoformat().replace(
        "+00:00", "Z"
    )


def request_json(
    url: str,
    *,
    method: str = "GET",
    bearer_token: Optional[str] = None,
    json_body: Optional[Dict[str, Any]] = None,
    query_params: Optional[Dict[str, str]] = None,
) -> Any:
    if query_params:
        url = f"{url}?{urlencode(query_params)}"
    headers: Dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": "PostmanRuntime/7.48.0",
    }
    data = None
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    if json_body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(json_body).encode("utf-8")

    parsed_url = urlparse(url)
    if parsed_url.scheme not in ("https",):
        raise BootstrapError(f"Only HTTPS URLs are allowed, got: {parsed_url.scheme}")
    hostname = parsed_url.hostname or ""
    if hostname not in _ALLOWED_HOSTS:
        raise BootstrapError(f"Host '{hostname}' is not in the allowed list: {_ALLOWED_HOSTS}")

    try:
        with httpx.Client(verify=True, timeout=30) as client:
            resp = client.request(method, url, headers=headers, content=data)
            if resp.status_code >= 400:
                raise BootstrapError(f"{method} {url} failed with HTTP {resp.status_code}")
            raw = resp.text
            if not raw:
                return None
            return json.loads(raw)
    except httpx.HTTPError as exc:
        raise BootstrapError(f"{method} {url} failed: {exc}") from exc


def service_account_payload(args: argparse.Namespace, ctx: ProjectContext) -> Dict[str, Any]:
    if not ctx.project_id:
        raise BootstrapError("Missing project_id. Pass --project-id or provide a parseable --project-url.")
    if not ctx.customer_id:
        raise BootstrapError(
            "Missing customerId. Pass --customer-id or --secret-id, or provide a project URL that exposes it."
        )
    return {
        "name": args.service_account_name,
        "description": args.service_account_description,
        "customerId": ctx.customer_id,
        "serviceRoles": [
            "managed_rag.admin",
            "ai-agents.admin",
        ],
        "projectId": ctx.project_id,
        "projectRole": args.project_role,
        "artifactRoles": [],
        "artifactRegistries": [],
        "s3eRoles": [],
        "s3eBuckets": [],
    }


def api_key_payload(args: argparse.Namespace) -> Dict[str, Any]:
    expiry = datetime.now(timezone.utc) + timedelta(days=args.days_valid)
    return {
        "name": args.api_key_name,
        "description": args.api_key_description,
        "products": [args.product],
        "restrictions": {
            "ipAddresses": [],
            "timeRange": {
                "timeSlots": [{"start": 0, "end": 24}],
                "timezone": args.timezone,
            },
        },
        "enabled": True,
        "expiredAt": iso_z(expiry),
    }


def find_service_account(token: str, project_id: str, customer_id: Optional[str], name: str) -> Optional[Dict[str, Any]]:
    """Find an existing service account by name via POST list endpoint."""
    if not customer_id:
        return None
    try:
        data = request_json(
            SERVICE_ACCOUNT_LIST_URL,
            method="POST",
            bearer_token=token,
            json_body={"projectIds": [project_id], "customerId": customer_id},
        )
    except BootstrapError as exc:
        print(f"  List service accounts failed: {exc}", file=sys.stderr)
        return None

    # Extract accounts from response — API returns {"accounts": [...]}
    if isinstance(data, list):
        accounts = data
    elif isinstance(data, dict):
        accounts = (
            data.get("accounts")
            or data.get("serviceAccounts")
            or data.get("items")
            or data.get("data")
            or []
        )
    else:
        return None

    for sa in accounts:
        if sa.get("name") == name:
            return sa

    return None


def create_service_account(token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return request_json(
        SERVICE_ACCOUNT_URL,
        method="POST",
        bearer_token=token,
        json_body=payload,
    )


def create_api_key(token: str, service_account_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = API_KEY_URL_TEMPLATE.format(service_account_id=service_account_id)
    return request_json(url, method="POST", bearer_token=token, json_body=payload)


def create_access_key(token: str, service_account_id: str, description: str, ttl_days: int) -> Dict[str, Any]:
    """Create an access key for IAM authentication (CP_CONSOLE_KEY_ID / CP_CONSOLE_SECRET).

    POST /u-api/bff-console/v1/service-accounts/{id}/access_keys
    Body: {"description": "...", "ttl": <days>}
    Returns: {"id", "service_account_id", "description", "key_id", "secret", "created_at", "expired_at"}
    """
    url = ACCESS_KEY_URL_TEMPLATE.format(service_account_id=service_account_id)
    return request_json(
        url,
        method="POST",
        bearer_token=token,
        json_body={"description": description, "ttl": ttl_days},
    )


def ensure_service_roles(token: str, sa_id: str, project_id: str, roles: List[str]) -> Dict[str, Any]:
    """PATCH service account to add multiple service roles. Idempotent.

    PATCH /u-api/bff-console/v2/service-accounts/{sa_id}
    Body: {"projectId": "...", "serviceRoles": {"adds": [...], "removes": []}}
    Accepts an IAM bearer OR a console OIDC bearer.
    """
    url = f"https://console.cloud.ru/u-api/bff-console/v2/service-accounts/{sa_id}"
    body = {
        "projectId": project_id,
        "serviceRoles": {"adds": roles, "removes": []},
    }
    return request_json(url, method="PATCH", bearer_token=token, json_body=body)


def build_result(
    args: argparse.Namespace,
    ctx: ProjectContext,
    sa_payload: Dict[str, Any],
    key_payload: Dict[str, Any],
    service_account: Optional[Dict[str, Any]],
    api_key: Optional[Dict[str, Any]],
    access_key: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    notes = list(ctx.notes)
    if args.days_valid > 365:
        notes.append("days-valid is greater than 365; Cloud.ru documentation says one year is the maximum.")
    if service_account:
        notes.append(
            "Service roles assigned to the SA: managed_rag.admin, ai-agents.admin."
        )
    result: Dict[str, Any] = {
        "project": {
            "project_url": ctx.project_url,
            "project_id": ctx.project_id,
            "customer_id": ctx.customer_id,
            "customer_id_source": ctx.customer_id_source,
        },
        "inputs": {
            "service_account_payload": sa_payload,
            "api_key_payload": key_payload,
        },
        "service_account": service_account,
        "api_key": api_key,
        "access_key": access_key,
        "notes": notes,
    }
    if access_key:
        result["credentials_summary"] = {
            "CLOUD_RU_FOUNDATION_MODELS_API_KEY": api_key.get("secret") if api_key else None,
            "CP_CONSOLE_KEY_ID": access_key.get("key_id"),
            "CP_CONSOLE_SECRET": access_key.get("secret"),
            "PROJECT_ID": ctx.project_id,
        }
    return result


def main() -> int:
    args = parse_args()

    # --from-stdin mode: read all parameters as JSON from stdin
    if args.from_stdin:
        stdin_data = json.loads(sys.stdin.read())
        args.project_url = stdin_data.get("project_url", args.project_url)
        args.token = stdin_data.get("token", args.token)
        if stdin_data.get("customer_id"):
            args.customer_id = stdin_data["customer_id"]
        if stdin_data.get("service_account_name"):
            args.service_account_name = stdin_data["service_account_name"]
        if stdin_data.get("skip_access_key"):
            args.skip_access_key = True

    try:
        ctx = parse_project_context(
            project_url=args.project_url,
            explicit_project_id=args.project_id,
            explicit_customer_id=args.customer_id,
            explicit_secret_id=args.secret_id,
        )
        sa_payload = service_account_payload(args, ctx)
        key_payload = api_key_payload(args)

        if args.dry_run:
            result = build_result(args, ctx, sa_payload, key_payload, None, None)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if not args.token:
            args.token = os.environ.get("CLOUDRU_BOOTSTRAP_TOKEN", "")
        if not args.token:
            raise BootstrapError(
                "Missing --token. Pass the Cloud.ru console bearer token via --token, --from-stdin, or CLOUDRU_BOOTSTRAP_TOKEN env var."
            )

        try:
            service_account = create_service_account(args.token, sa_payload)
        except BootstrapError as exc:
            if "409" not in str(exc) and "already exists" not in str(exc):
                raise

            print(f"Service account '{args.service_account_name}' already exists, looking it up...", file=sys.stderr)
            service_account = find_service_account(args.token, ctx.project_id, ctx.customer_id, args.service_account_name)

            if not service_account:
                # Fallback: create with a unique name
                import random, string
                suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
                new_name = f"{args.service_account_name}-{suffix}"
                print(f"Could not find existing account. Creating new one: '{new_name}'", file=sys.stderr)
                sa_payload["name"] = new_name
                sa_payload["description"] = new_name
                service_account = create_service_account(args.token, sa_payload)
            else:
                print(f"Found existing service account: {service_account.get('id')}", file=sys.stderr)
                ai_agents_roles = [
                    "managed_rag.admin",
                    "ai-agents.admin",
                ]
                try:
                    ensure_service_roles(
                        args.token,
                        service_account.get("id"),
                        ctx.project_id,
                        ai_agents_roles,
                    )
                    print(
                        f"Ensured service roles on existing SA {service_account.get('id')}: {ai_agents_roles}",
                        file=sys.stderr,
                    )
                except BootstrapError as exc:
                    ctx.notes.append(
                        f"Existing SA found but ensure_service_roles failed: {exc}. "
                        f"Verify service roles are assigned via UI."
                    )

        service_account_id = service_account.get("id")
        if not service_account_id:
            raise BootstrapError(
                f"Cloud.ru service account response does not contain an id: {json.dumps(service_account, ensure_ascii=False)}"
            )

        api_key = create_api_key(args.token, service_account_id, key_payload)
        api_secret = api_key.get("secret")
        if not api_secret:
            raise BootstrapError(
                f"Cloud.ru API key response does not contain a secret: {json.dumps(api_key, ensure_ascii=False)}"
            )

        access_key = None
        if not args.skip_access_key:
            access_key = create_access_key(
                args.token,
                service_account_id,
                args.access_key_description,
                args.access_key_ttl,
            )
            if not access_key.get("key_id") or not access_key.get("secret"):
                raise BootstrapError(
                    f"Cloud.ru access key response missing key_id or secret: {json.dumps(access_key, ensure_ascii=False)}"
                )

        result = build_result(args, ctx, sa_payload, key_payload, service_account, api_key, access_key)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except BootstrapError as exc:
        import traceback
        traceback.print_exc()
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
