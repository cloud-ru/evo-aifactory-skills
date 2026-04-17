"""Cloud.ru Managed RAG Infrastructure Setup pipeline.

Requires CP_CONSOLE_KEY_ID/SECRET/PROJECT_ID env vars (from cloudru-account-setup).

Pipeline (IAM-only, no browser OIDC token):
  1. get-iam-token  -- exchange CP_CONSOLE_KEY_ID/SECRET for an IAM bearer
  2. get-tenant-id  -- get tenant_id for S3
  3. ensure-bucket  -- create S3 bucket via BFF
  4. upload-docs    -- upload documents to bucket (boto3)
  5. create-kb      -- create Knowledge Base (with log group)
  6. wait-active    -- poll until KNOWLEDGEBASE_ACTIVE
  7. save-env       -- save .env with KB-specific vars
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IAM_HOST = "iam.api.cloud.ru"
CONSOLE_HOST = "console.cloud.ru"
RAG_API_HOST = "managed-rag.api.cloud.ru"
S3_ENDPOINT = "https://s3.cloud.ru"
S3_REGION = "ru-central-1"

NO_PROXY_HOSTS = (
    "managed-rag.api.cloud.ru",
    "iam.api.cloud.ru",
    "s3.cloud.ru",
    "console.cloud.ru",
    "managed-rag.inference.cloud.ru",
)

DEFAULT_SA_NAME = "managed-rag-sa"
DEFAULT_FILE_EXTENSIONS = "txt,pdf"
DEFAULT_KB_POLL_INTERVAL = 15  # seconds
DEFAULT_KB_POLL_TIMEOUT = 600  # 10 minutes
MAX_UPLOAD_FILE_SIZE = 100 * 1024 * 1024  # 100 MB per file
DEFAULT_ACCESS_KEY_TTL = 365  # days (BFF expects uint32 in range [0, 10000])
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,62}$")
DEFAULT_ENV_PATH = os.path.expanduser(
    "~/.openclaw/workspace/skills/managed-rag-skill/.env"
)

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

ALL_STEPS = [
    "get-iam-token",
    "get-tenant-id",
    "ensure-bucket",
    "upload-docs",
    "create-kb",
    "wait-active",
    "save-env",
]


# ---------------------------------------------------------------------------
# Helpers: proxy bypass
# ---------------------------------------------------------------------------


def _setup_no_proxy() -> None:
    """Append Cloud.ru hosts to no_proxy to bypass corporate proxies."""
    current = os.environ.get("no_proxy", "")
    hosts_to_add = [h for h in NO_PROXY_HOSTS if h not in current]
    if hosts_to_add:
        separator = "," if current else ""
        os.environ["no_proxy"] = current + separator + ",".join(hosts_to_add)
        os.environ["NO_PROXY"] = os.environ["no_proxy"]
    # Remove proxy env vars that would override no_proxy for http.client / urllib
    for pvar in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ.pop(pvar, None)


# Force bypass on module import
_no_proxy = ",".join(NO_PROXY_HOSTS)
os.environ["no_proxy"] = _no_proxy + "," + os.environ.get("no_proxy", "")
for _pvar in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(_pvar, None)


# ---------------------------------------------------------------------------
# Helpers: output
# ---------------------------------------------------------------------------


def emit(data: Dict[str, Any]) -> None:
    """Print a JSON object to stdout (one line)."""
    print(json.dumps(data, ensure_ascii=False))


def make_error(step: str, message: str, code: Optional[int] = None) -> Dict[str, Any]:
    """Build an error result dict (does NOT emit -- caller uses ctx.record)."""
    result: Dict[str, Any] = {"step": step, "error": message}
    if code is not None:
        result["code"] = code
    return result


# ---------------------------------------------------------------------------
# Helpers: httpx-based HTTPS requests for BFF/Console API
# ---------------------------------------------------------------------------


def _bff_request(
    method: str,
    path: str,
    token: str,
    body: Optional[Any] = None,
    timeout: float = 30.0,
) -> Tuple[int, Dict[str, Any]]:
    """Perform BFF (console) HTTPS request using httpx. Returns (status, data)."""
    url = f"https://{CONSOLE_HOST}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Origin": "https://console.cloud.ru",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(verify=True, timeout=timeout, proxy=None) as client:
            resp = client.request(method, url, headers=headers, json=body)
            status = resp.status_code
            raw = resp.text
    except Exception as exc:
        return 0, {"_error": str(exc)}

    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {"_raw": raw}
    return status, data


def _api_request(
    host: str,
    method: str,
    path: str,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Any] = None,
    timeout: float = 30.0,
) -> Tuple[int, Dict[str, Any]]:
    """Generic HTTPS request via httpx for public API / IAM calls."""
    url = f"https://{host}{path}"
    hdrs = dict(headers or {})
    hdrs.setdefault("Content-Type", "application/json")
    try:
        with httpx.Client(verify=True, timeout=timeout, proxy=None) as client:
            resp = client.request(method, url, headers=hdrs, json=body)
            status = resp.status_code
            raw = resp.text
    except Exception as exc:
        return 0, {"_error": str(exc)}
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {"_raw": raw}
    return status, data


# ---------------------------------------------------------------------------
# Helpers: headers
# ---------------------------------------------------------------------------


def _auth_headers(token: str) -> Dict[str, str]:
    """Standard Authorization header for public API."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Helpers: IAM token exchange
# ---------------------------------------------------------------------------


def get_iam_token(key_id: str, secret: str) -> str:
    """Exchange an access key pair for an IAM bearer token."""
    status, data = _api_request(
        IAM_HOST,
        "POST",
        "/api/v1/auth/token",
        headers={"Content-Type": "application/json"},
        body={"key_id": key_id, "secret": secret},
    )
    if status != 200:
        raise RuntimeError(
            f"IAM token exchange failed (HTTP {status}): {json.dumps(data)}"
        )
    token = data.get("access_token") or data.get("token")
    if not token:
        raise RuntimeError(f"No token in IAM response: {json.dumps(data)}")
    return token


# ---------------------------------------------------------------------------
# Pipeline context -- carries state between steps
# ---------------------------------------------------------------------------


class PipelineContext:
    """Mutable bag of state threaded through pipeline steps."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        bucket_name: Optional[str] = None,
        docs_path: Optional[str] = None,
        kb_name: Optional[str] = None,
        file_extensions: str = DEFAULT_FILE_EXTENSIONS,
        output_env: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        self.project_id: Optional[str] = project_id
        self.bucket_name: Optional[str] = bucket_name
        self.docs_path: Optional[str] = docs_path
        self.kb_name: Optional[str] = kb_name
        self.file_extensions: str = file_extensions
        self.output_env: Optional[str] = output_env
        self.dry_run: bool = dry_run

        self.tenant_id: Optional[str] = None
        self.kb_id: Optional[str] = None
        self.search_url: Optional[str] = None
        self.log_group_id: Optional[str] = None
        self.iam_token: Optional[str] = None
        self.results: List[Dict[str, Any]] = []

    def record(self, result: Dict[str, Any]) -> Dict[str, Any]:
        self.results.append(result)
        emit(result)
        return result

    def ensure_iam_token(self) -> str:
        """Fresh exchange CP_CONSOLE_KEY_ID/SECRET -> IAM bearer on each call."""
        if self.dry_run:
            return ""
        key_id = os.environ.get("CP_CONSOLE_KEY_ID")
        key_secret = os.environ.get("CP_CONSOLE_SECRET")
        if not key_id or not key_secret:
            raise RuntimeError(
                "CP_CONSOLE_KEY_ID/CP_CONSOLE_SECRET not set. "
                "Run cloudru-account-setup first."
            )
        self.iam_token = get_iam_token(key_id, key_secret)
        return self.iam_token


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------


def step_get_iam_token(ctx: PipelineContext) -> Dict[str, Any]:
    """Step 1: Exchange CP_CONSOLE_KEY_ID/SECRET for an IAM bearer token.

    Fails early if env vars are missing or the IAM exchange returns non-200.
    """
    step = "get-iam-token"
    if ctx.dry_run:
        ctx.iam_token = ""
        return ctx.record({"step": step, "dry_run": True})
    try:
        ctx.ensure_iam_token()
    except Exception as exc:
        return ctx.record(make_error(step, str(exc)))
    return ctx.record({"step": step, "ok": True})


def step_get_tenant_id(ctx: PipelineContext) -> Dict[str, Any]:
    """Step 2: Get tenant_id from the S3 controller BFF (httpx)."""
    step = "get-tenant-id"

    if not ctx.project_id:
        return ctx.record(
            make_error(step, "project_id required -- run extract-info first")
        )

    if ctx.dry_run:
        ctx.tenant_id = ctx.tenant_id or "dry-run-tenant-id"
        return ctx.record(
            {"step": step, "project_id": ctx.project_id, "dry_run": True}
        )

    path = f"/u-api/s3e-controller/v2/projects/{ctx.project_id}"
    status, data = _bff_request("GET", path, ctx.ensure_iam_token())

    if status != 200:
        return ctx.record(
            make_error(step, f"Failed to get tenant_id: {json.dumps(data)}", status)
        )

    ctx.tenant_id = (
        data.get("tenant_id")
        or data.get("tenantId")
        or data.get("tenant", {}).get("id")
        or data.get("data", {}).get("tenant_id")
    )
    if not ctx.tenant_id:
        return ctx.record(
            make_error(step, "tenant_id not found in response")
        )
    if not _UUID_RE.match(ctx.tenant_id):
        return ctx.record(
            make_error(step, f"tenant_id has invalid format: {ctx.tenant_id}")
        )

    return ctx.record({"step": step, "tenant_id": ctx.tenant_id})


def _fetch_bucket_log_group_id(ctx: PipelineContext, bucket_name: str) -> None:
    """Try to get log_group_id from an existing bucket via BFF.

    Called when bucket creation returns 409 (already exists).
    Sets ctx.log_group_id if found.
    """
    if not ctx.tenant_id:
        return
    # List buckets and find ours
    status, data = _bff_request(
        "GET",
        f"/u-api/s3e-controller/v1/tenants/{ctx.tenant_id}/buckets",
        ctx.ensure_iam_token(),
    )
    if status != 200:
        return
    buckets = data if isinstance(data, list) else data.get("buckets", data.get("items", []))
    for b in buckets:
        if b.get("name") == bucket_name:
            gid = b.get("log_group_id") or b.get("logGroupId") or ""
            if gid:
                ctx.log_group_id = gid
            return


def step_ensure_bucket(ctx: PipelineContext) -> Dict[str, Any]:
    """Step 6: Create an S3 bucket via BFF (s3e-controller).

    Uses BFF endpoint so the bucket is registered in Cloud.ru platform
    and accessible by Managed RAG for indexing.
    """
    step = "ensure-bucket"
    bucket_name = ctx.bucket_name

    if not bucket_name:
        return ctx.record(
            make_error(step, "--bucket-name is required")
        )
    if not _SAFE_NAME_RE.match(bucket_name):
        return ctx.record(
            make_error(step, f"Invalid bucket name '{bucket_name}': must be 1-63 alphanumeric chars, dots, hyphens, underscores")
        )
    if not ctx.tenant_id:
        return ctx.record(
            make_error(step, "tenant_id required -- run get-tenant-id first")
        )

    if ctx.dry_run:
        return ctx.record(
            {"step": step, "bucket_name": bucket_name, "dry_run": True}
        )

    # Create bucket via BFF s3e-controller (registers in platform)
    # Match UI payload exactly — no global_name/domain_name, quota=0
    bucket_body = {
        "name": bucket_name,
        "storage_class": "STANDARD",
        "quotas": [{"type": "BUCKET_SIZE", "value": 0, "unit": "GB"}],
    }
    status, data = _bff_request(
        "POST",
        f"/u-api/s3e-controller/v1/tenants/{ctx.tenant_id}/buckets",
        ctx.ensure_iam_token(),
        body=bucket_body,
    )

    created = False
    if status in (200, 201):
        created = True
        # Save log_group_id from response for telemetry_configuration in KB
        ctx.log_group_id = data.get("log_group_id") if isinstance(data, dict) else None
    elif status == 409 or (isinstance(data, dict) and "already exists" in str(data).lower()):
        # Bucket already exists — try to fetch its log_group_id
        created = False
        _fetch_bucket_log_group_id(ctx, bucket_name)
    else:
        return ctx.record(
            make_error(step, f"Failed to create bucket via BFF: {json.dumps(data)}", status)
        )

    return ctx.record({"step": step, "bucket_name": bucket_name, "created": created})


def step_upload_docs(ctx: PipelineContext) -> Dict[str, Any]:
    """Step 7: Upload documents from a local folder to the S3 bucket.

    Uses boto3 with AWS Signature V4 -- NOT rewritten to httpx.
    """
    step = "upload-docs"
    docs_path = ctx.docs_path
    bucket_name = ctx.bucket_name

    if not docs_path:
        return ctx.record(
            make_error(step, "--docs-path is required")
        )
    if not bucket_name:
        return ctx.record(
            make_error(step, "--bucket-name is required")
        )

    docs_dir = pathlib.Path(docs_path).expanduser().resolve()
    if not docs_dir.is_dir():
        return ctx.record(
            make_error(step, f"docs-path is not a directory: {docs_dir}")
        )

    # Collect files matching extensions
    extensions = {
        ext.strip().lstrip(".")
        for ext in (ctx.file_extensions or DEFAULT_FILE_EXTENSIONS).split(",")
    }
    files_to_upload: List[pathlib.Path] = []
    for ext in extensions:
        files_to_upload.extend(docs_dir.rglob(f"*.{ext}"))
    for ext in list(extensions):
        files_to_upload.extend(docs_dir.rglob(f"*.{ext.upper()}"))
    files_to_upload = sorted(set(files_to_upload))

    if not files_to_upload:
        return ctx.record(
            make_error(step, f"No files with extensions {extensions} found in {docs_dir}")
        )

    if ctx.dry_run:
        return ctx.record(
            {
                "step": step,
                "files_found": len(files_to_upload),
                "extensions": sorted(extensions),
                "dry_run": True,
            }
        )

    if not ctx.tenant_id:
        return ctx.record(
            make_error(step, "tenant_id required -- run get-tenant-id first")
        )
    key_id = os.environ.get("CP_CONSOLE_KEY_ID")
    key_secret = os.environ.get("CP_CONSOLE_SECRET")
    if not key_id or not key_secret:
        return ctx.record(
            make_error(
                step,
                "CP_CONSOLE_KEY_ID/CP_CONSOLE_SECRET env vars required "
                "(run cloudru-account-setup first)",
            )
        )

    try:
        import boto3
        from botocore.config import Config as BotoConfig
    except ImportError:
        return ctx.record(
            make_error(step, "boto3 is not installed -- pip install boto3")
        )

    s3_access_key = f"{ctx.tenant_id}:{key_id}"
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name=S3_REGION,
        aws_access_key_id=s3_access_key,
        aws_secret_access_key=key_secret,
        config=BotoConfig(s3={"addressing_style": "path"}),
    )

    total_size = 0
    uploaded = 0
    for fpath in files_to_upload:
        relative = fpath.relative_to(docs_dir)
        s3_key = str(relative)
        file_size = fpath.stat().st_size
        if file_size > MAX_UPLOAD_FILE_SIZE:
            emit({"step": step, "warning": f"Skipping {relative}: exceeds {MAX_UPLOAD_FILE_SIZE} byte limit ({file_size} bytes)"})
            continue
        try:
            # ACL=bucket-owner-full-control is CRITICAL:
            # Without it, Managed RAG Search API cannot read the files
            s3.upload_file(
                str(fpath), bucket_name, s3_key,
                ExtraArgs={
                    "StorageClass": "STANDARD",
                    "ACL": "bucket-owner-full-control",
                },
            )
            uploaded += 1
            total_size += file_size
        except Exception as exc:
            emit({"step": step, "warning": f"Failed to upload {relative}: {exc}"})

    return ctx.record(
        {"step": step, "files_uploaded": uploaded, "total_size_bytes": total_size}
    )


LOGAAS_HOST_PATH = "/u-api/logaas-bff-console/v1"
DEFAULT_LOG_GROUP_NAME = "managed-rag-logs"


def _resolve_log_group_id(ctx: PipelineContext) -> str:
    """Get logaas_log_group_id for telemetry configuration.

    CRITICAL: Empty string breaks Search API deployment (platform bug).
    Must provide a real log group ID.

    Strategy:
      1. Already resolved (from bucket creation) → use it
      2. List project log groups → prefer 'default', else first active
      3. No log groups → create one
    """
    if ctx.log_group_id:
        return ctx.log_group_id

    if not ctx.project_id:
        return ""

    # List existing log groups
    status, data = _bff_request(
        "GET",
        f"{LOGAAS_HOST_PATH}/{ctx.project_id}/log-groups",
        ctx.ensure_iam_token(),
    )
    if status == 200:
        groups = data.get("logGroups", [])
        # Prefer 'default' type, then any active
        for g in groups:
            if g.get("type") == "DEFAULT" and g.get("status") == "STATUS_ACTIVE":
                ctx.log_group_id = g["id"]
                return g["id"]
        for g in groups:
            if g.get("status") == "STATUS_ACTIVE":
                ctx.log_group_id = g["id"]
                return g["id"]

    # No log groups — create one
    emit({"info": "Нет log groups на проекте, создаю managed-rag-logs..."})
    status, data = _bff_request(
        "POST",
        f"{LOGAAS_HOST_PATH}/{ctx.project_id}/log-group",
        ctx.ensure_iam_token(),
        body={
            "name": DEFAULT_LOG_GROUP_NAME,
            "description": "Auto-created for Managed RAG (required for Search API)",
            "retentionPeriod": 3,
            "status": "STATUS_ACTIVE",
        },
    )
    if status == 200 and data.get("id"):
        ctx.log_group_id = data["id"]
        return data["id"]

    emit({
        "warning": "Не удалось получить или создать log group. "
        "Search API может не заработать. Создайте log group в консоли "
        "(Observability → Log Groups) и повторите setup."
    })
    return ""


def _build_kb_payload(ctx: PipelineContext) -> Dict[str, Any]:
    """Build the Knowledge Base creation payload."""
    extensions = [
        ext.strip().lstrip(".")
        for ext in (ctx.file_extensions or DEFAULT_FILE_EXTENSIONS).split(",")
    ]

    extractors = []
    if "txt" in extensions:
        extractors.append(
            {
                "file_patterns": ["txt"],
                "text_extractor": {
                    "recursive_char_splitter": {
                        "separators": "\n\n",
                        "is_separator_regex": False,
                        "keep_separator": "KeepSeparator_None",
                        "chunk_size": 1500,
                        "chunk_overlap": 300,
                    }
                },
            }
        )
    if "pdf" in extensions:
        extractors.append(
            {
                "file_patterns": ["pdf"],
                "pdf_extractor": {
                    "pdf_parser": {"method": "table_struct", "mode": "single"},
                    "markdown_smart_splitter": {
                        "chunk_size": 1500,
                        "chunk_overlap": 300,
                        "allow_oversize": False,
                        "headers_to_split_on": "",
                    },
                },
            }
        )

    return {
        "project_id": ctx.project_id,
        "knowledgebase_configuration": {
            "name": ctx.kb_name,
            "description": f"Knowledge Base '{ctx.kb_name}' (auto-created by setup pipeline)",
            "auth_configuration": {"forward_auth": False, "api_key": False},
            "database_configuration": {"support_hybrid_search": False},
        },
        "knowledgebase_version_configuration": {
            "name": "version-1",
            "description": "",
            "embedder_configuration": {
                "model_name": "Qwen/Qwen3-Embedding-0.6B",
                "model_source": "MODEL_SOURCE_FOUNDATION_MODELS",
            },
            "telemetry_configuration": {
                "logging": {
                    "logaas_log_group_id": _resolve_log_group_id(ctx),
                },
            },
            "data_source_configuration": {
                "cloud_ru_evolution_object_storage_source": {
                    "bucket_name": ctx.bucket_name,
                    "paths": [""],
                    "object_storage_scan_options": {
                        "recursive": True,
                        "file_extensions": extensions,
                        "max_depth": 0,
                    },
                }
            },
            "extractors_configuration": {"extractors": extractors},
        },
    }


def step_create_kb(ctx: PipelineContext) -> Dict[str, Any]:
    """Step 8: Create a Knowledge Base via BFF API (httpx, requires browser token)."""
    step = "create-kb"

    if not ctx.kb_name:
        return ctx.record(
            make_error(step, "--kb-name is required")
        )
    if not _SAFE_NAME_RE.match(ctx.kb_name):
        return ctx.record(
            make_error(step, f"Invalid KB name '{ctx.kb_name}': must be 1-63 alphanumeric chars, dots, hyphens, underscores")
        )
    if not ctx.project_id:
        return ctx.record(
            make_error(step, "project_id required -- run extract-info first")
        )

    payload = _build_kb_payload(ctx)

    if ctx.dry_run:
        ctx.kb_id = ctx.kb_id or "dry-run-kb-id"
        return ctx.record(
            {"step": step, "kb_name": ctx.kb_name, "payload": payload, "dry_run": True}
        )

    status, data = _bff_request(
        "POST",
        "/u-api/managed-rag/user-plane/api/v2/knowledge-bases",
        ctx.ensure_iam_token(),
        body=payload,
        timeout=60.0,
    )

    if status not in (200, 201):
        return ctx.record(
            make_error(step, f"Failed to create KB: {json.dumps(data)}", status)
        )

    ctx.kb_id = (
        data.get("knowledgebase_id")
        or data.get("id")
        or data.get("knowledgebase", {}).get("id")
        or data.get("knowledgebase", {}).get("knowledgebase_id")
    )
    kb_status = (
        data.get("status")
        or data.get("knowledgebase", {}).get("status")
        or "UNKNOWN"
    )

    return ctx.record({"step": step, "kb_id": ctx.kb_id, "status": kb_status})


def step_wait_active(ctx: PipelineContext) -> Dict[str, Any]:
    """Step 9: Poll until the KB becomes KNOWLEDGEBASE_ACTIVE.

    Strategy:
    - If access-key is available, obtain SA IAM token and poll via public API.
    - Otherwise fall back to BFF polling via browser token.
    """
    step = "wait-active"

    if not ctx.kb_id:
        return ctx.record(
            make_error(step, "kb_id required -- run create-kb first")
        )
    if not ctx.project_id:
        return ctx.record(
            make_error(step, "project_id required")
        )

    if ctx.dry_run:
        ctx.search_url = f"https://{ctx.kb_id}.managed-rag.inference.cloud.ru"
        return ctx.record(
            {"step": step, "kb_id": ctx.kb_id, "dry_run": True}
        )

    # Decide polling strategy: IAM token (preferred) or BFF fallback
    use_iam = False
    iam_token = None
    try:
        iam_token = ctx.ensure_iam_token()
        use_iam = True
    except RuntimeError:
        pass

    if use_iam:
        poll_host = RAG_API_HOST
        poll_path = f"/v1/knowledge-bases/{ctx.kb_id}?project_id={ctx.project_id}"
        emit({"step": step, "info": "Using SA IAM token for polling via public API"})
    else:
        poll_host = CONSOLE_HOST
        poll_path = (
            f"/u-api/managed-rag/user-plane/api/v2/knowledge-bases/{ctx.kb_id}"
            f"?project_id={ctx.project_id}"
        )
        emit({
            "step": step,
            "info": "No SA IAM token available, falling back to BFF polling. "
                    "Warning: browser token may expire before KB becomes active.",
        })

    deadline = time.monotonic() + DEFAULT_KB_POLL_TIMEOUT
    last_status = "UNKNOWN"
    poll_count = 0

    while time.monotonic() < deadline:
        poll_count += 1

        if use_iam:
            headers = _auth_headers(iam_token)
            status_code, data = _api_request(
                poll_host, "GET", poll_path, headers=headers, timeout=30.0
            )
        else:
            status_code, data = _bff_request("GET", poll_path, ctx.ensure_iam_token(), timeout=30.0)

        if status_code == 401 and use_iam:
            # IAM token expired -- refresh
            try:
                ctx.iam_token = None
                iam_token = ctx.ensure_iam_token()
            except RuntimeError:
                pass
            time.sleep(DEFAULT_KB_POLL_INTERVAL)
            continue

        if status_code == 401 and not use_iam:
            return ctx.record(
                make_error(
                    step,
                    "Browser token expired during polling. Re-run with a fresh token, "
                    "or ensure access-key step completes so IAM token can be used.",
                    401,
                )
            )

        if status_code != 200:
            emit({"step": step, "poll": poll_count, "http_status": status_code})
            time.sleep(DEFAULT_KB_POLL_INTERVAL)
            continue

        last_status = (
            data.get("status")
            or data.get("knowledgebase", {}).get("status")
            or "UNKNOWN"
        )

        if last_status == "KNOWLEDGEBASE_ACTIVE":
            ctx.search_url = f"https://{ctx.kb_id}.managed-rag.inference.cloud.ru"
            return ctx.record(
                {
                    "step": step,
                    "status": last_status,
                    "search_url": ctx.search_url,
                    "polls": poll_count,
                }
            )

        # Emit progress every 4 polls (~60s)
        if poll_count % 4 == 0:
            emit(
                {
                    "step": step,
                    "progress": True,
                    "status": last_status,
                    "polls": poll_count,
                }
            )

        time.sleep(DEFAULT_KB_POLL_INTERVAL)

    return ctx.record(
        make_error(
            step,
            f"Timeout after {DEFAULT_KB_POLL_TIMEOUT}s. Last status: {last_status}",
        )
    )


def step_save_env(ctx: PipelineContext) -> Dict[str, Any]:
    """Step 7: Save KB-specific env vars to .env file.

    CP_CONSOLE_KEY_ID/SECRET/PROJECT_ID are provided by cloudru-account-setup
    and not rewritten here. Only KB-specific vars are written.
    """
    step = "save-env"

    env_path = ctx.output_env or DEFAULT_ENV_PATH

    env_content_lines = [
        "# Auto-generated by managed_rag setup pipeline",
        f"# Created: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f'MANAGED_RAG_KB_ID={ctx.kb_id or ""}',
        f'MANAGED_RAG_SEARCH_URL={ctx.search_url or ""}',
        "",
    ]
    env_content = "\n".join(env_content_lines)

    if ctx.dry_run:
        return ctx.record(
            {"step": step, "path": env_path, "content_preview": env_content, "dry_run": True}
        )

    env_file = pathlib.Path(env_path).expanduser()
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text(env_content, encoding="utf-8")
    env_file.chmod(0o600)

    return ctx.record({"step": step, "path": str(env_file)})


# ---------------------------------------------------------------------------
# Step registry
# ---------------------------------------------------------------------------

STEP_REGISTRY: Dict[str, Any] = {
    "get-iam-token": step_get_iam_token,
    "get-tenant-id": step_get_tenant_id,
    "ensure-bucket": step_ensure_bucket,
    "upload-docs": step_upload_docs,
    "create-kb": step_create_kb,
    "wait-active": step_wait_active,
    "save-env": step_save_env,
}


# ---------------------------------------------------------------------------
# Pipeline runners
# ---------------------------------------------------------------------------


STEP_LABELS = {
    "get-iam-token": "Получаю IAM токен из access key",
    "get-tenant-id": "Получаю tenant_id для S3",
    "ensure-bucket": "Создаю S3 бакет",
    "upload-docs": "Загружаю документы в S3",
    "create-kb": "Создаю Knowledge Base",
    "wait-active": "Жду активации KB",
    "save-env": "Сохраняю .env с KB info",
}


def run_pipeline(ctx: PipelineContext) -> int:
    """Run all steps sequentially. Stop on first critical error."""
    total = len(ALL_STEPS)
    warnings = []

    for i, step_name in enumerate(ALL_STEPS, 1):
        label = STEP_LABELS.get(step_name, step_name)
        emit({"progress": f"[{i}/{total}] {label}..."})

        step_fn = STEP_REGISTRY[step_name]
        try:
            result = step_fn(ctx)
        except Exception as exc:
            result = {"step": step_name, "error": str(exc)}
            ctx.record(result)

        if result.get("warning"):
            warnings.append(f"  - {step_name}: {result['warning']}")

        if "error" in result:
            if step_name not in ("ensure-role", "upload-docs", "wait-active", "save-env"):
                emit({"progress": f"[{i}/{total}] ОШИБКА на шаге '{label}'"})
                emit(
                    {
                        "pipeline": "stopped",
                        "failed_step": step_name,
                        "results": ctx.results,
                    }
                )
                return 1

    # Human-readable summary
    summary_lines = [f"Pipeline завершён ({total} шагов)"]
    if ctx.kb_id:
        summary_lines.append(f"  KB: {ctx.kb_id}")
    if ctx.search_url:
        summary_lines.append(f"  Search URL: {ctx.search_url}")
    if warnings:
        summary_lines.append("  Warnings:")
        summary_lines.extend(warnings)

    emit({"progress": "\n".join(summary_lines)})
    emit({"pipeline": "complete", "results": ctx.results})
    return 0


def run_single_step(ctx: PipelineContext, step_name: str) -> int:
    """Run a single named step."""
    step_fn = STEP_REGISTRY.get(step_name)
    if not step_fn:
        emit(make_error("cli", f"Unknown step: {step_name}"))
        return 1
    try:
        result = step_fn(ctx)
    except Exception as exc:
        emit(make_error(step_name, str(exc)))
        return 1
    return 0 if "error" not in result else 1


# ---------------------------------------------------------------------------
# CLI entry points (called from managed_rag.py via commands registry)
# ---------------------------------------------------------------------------


def _build_context(args) -> PipelineContext:
    """Build PipelineContext from argparse namespace."""
    _setup_no_proxy()
    pid = getattr(args, "project_id", None) or os.environ.get("PROJECT_ID")
    if not pid and not getattr(args, "dry_run", False):
        print(
            "PROJECT_ID is required. Pass --project-id or set PROJECT_ID env "
            "(usually from cloudru-account-setup).",
            file=sys.stderr,
        )
        sys.exit(1)
    if pid and not _UUID_RE.match(pid):
        print(f"PROJECT_ID must be a valid UUID, got: {pid}", file=sys.stderr)
        sys.exit(1)
    return PipelineContext(
        project_id=pid,
        bucket_name=getattr(args, "bucket_name", None),
        docs_path=getattr(args, "docs_path", None),
        kb_name=getattr(args, "kb_name", None),
        file_extensions=getattr(args, "file_extensions", DEFAULT_FILE_EXTENSIONS),
        output_env=getattr(args, "output_env", None),
        dry_run=getattr(args, "dry_run", False),
    )


def cmd_setup(args):
    """Full 10-step infrastructure setup pipeline."""
    ctx = _build_context(args)
    rc = run_pipeline(ctx)
    if rc != 0:
        raise SystemExit(rc)


def cmd_setup_step(args):
    """Single step execution."""
    ctx = _build_context(args)
    step_name = args.step
    rc = run_single_step(ctx, step_name)
    if rc != 0:
        raise SystemExit(rc)
