"""Lightweight Cloud.ru ML Inference client.

Replaces the inference-clients SDK and all pkg.sbercloud.tech dependencies.
Only requires: httpx.
"""

import re
import threading
import time
import uuid
from functools import wraps

import httpx

IAM_URL = "https://iam.api.cloud.ru"
BFF_URL = "https://console.cloud.ru"
BFF_PREFIX = "/u-api/inference/model-run/v1"
INFERENCE_DOMAIN = "modelrun.inference.cloud.ru"
_MODEL_RUN_ID_RE = re.compile(r"^[a-zA-Z0-9-]+$")

MAX_RETRIES = 3
RETRY_STATUSES = (502, 503, 504)
RETRY_BACKOFF_BASE = 1  # seconds


# --- Retry ---


def with_retry(func):
    """Retry on connection errors and 502/503/504."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        last_exc = None
        response = None
        for attempt in range(MAX_RETRIES):
            try:
                response = func(*args, **kwargs)
                if response.status_code not in RETRY_STATUSES:
                    return response
                last_exc = None
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.PoolTimeout) as exc:
                last_exc = exc
                response = None
            sleep = RETRY_BACKOFF_BASE * (2 ** attempt)
            time.sleep(sleep)
        if last_exc:
            raise last_exc
        if response is not None:
            response.raise_for_status()
        return response

    return wrapper


# --- IAM Auth ---


class IAMAuth(httpx.Auth):
    """httpx Auth handler that auto-obtains and refreshes Cloud.ru IAM tokens."""

    def __init__(self, key_id: str, key_secret: str):
        self.key_id = key_id
        self.key_secret = key_secret
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._lock = threading.Lock()

    def _fetch_token(self):
        resp = httpx.post(
            f"{IAM_URL}/api/v1/auth/token",
            json={"keyId": self.key_id, "secret": self.key_secret},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = time.monotonic() + expires_in - 60

    def _is_token_expired(self) -> bool:
        return not self._token or time.monotonic() >= self._token_expires_at

    def sync_auth_flow(self, request):
        with self._lock:
            if self._is_token_expired():
                self._fetch_token()
        request.headers["Authorization"] = f"Bearer {self._token}"
        response = yield request
        if response.status_code in (401, 403):
            with self._lock:
                self._fetch_token()
            request.headers["Authorization"] = f"Bearer {self._token}"
            yield request

    @property
    def token(self):
        with self._lock:
            if self._is_token_expired():
                self._fetch_token()
        return self._token


# --- Client ---


class CloudruInferenceClient:
    """Unified client for Cloud.ru ML Inference BFF and inference endpoints."""

    def __init__(self, key_id: str, key_secret: str, timeout: float = 60):
        self.auth = IAMAuth(key_id, key_secret)
        self._bff = httpx.Client(
            base_url=BFF_URL,
            auth=self.auth,
            timeout=timeout,
        )

    def _headers(self):
        return {
            "X-Request-ID": str(uuid.uuid4()),
        }

    # --- BFF: Model Run CRUD ---

    @with_retry
    def list_model_runs(self, project_id: str, limit: int = 100, offset: int = 0):
        return self._bff.get(
            f"{BFF_PREFIX}/{project_id}/modelruns",
            params={"limit": limit, "offset": offset},
            headers=self._headers(),
        )

    @with_retry
    def get_model_run(self, project_id: str, model_run_id: str):
        return self._bff.get(
            f"{BFF_PREFIX}/{project_id}/modelruns/{model_run_id}",
            headers=self._headers(),
        )

    @with_retry
    def create_model_run(self, project_id: str, payload: dict):
        return self._bff.post(
            f"{BFF_PREFIX}/{project_id}/modelruns",
            json=payload,
            headers=self._headers(),
        )

    @with_retry
    def update_model_run(self, project_id: str, model_run_id: str, payload: dict):
        return self._bff.put(
            f"{BFF_PREFIX}/{project_id}/modelruns/{model_run_id}",
            json=payload,
            headers=self._headers(),
        )

    @with_retry
    def delete_model_run(self, project_id: str, model_run_id: str):
        return self._bff.delete(
            f"{BFF_PREFIX}/{project_id}/modelruns/{model_run_id}",
            headers=self._headers(),
        )

    @with_retry
    def suspend_model_run(self, project_id: str, model_run_id: str):
        return self._bff.patch(
            f"{BFF_PREFIX}/{project_id}/modelruns/{model_run_id}/suspend",
            headers=self._headers(),
        )

    @with_retry
    def resume_model_run(self, project_id: str, model_run_id: str):
        return self._bff.patch(
            f"{BFF_PREFIX}/{project_id}/modelruns/{model_run_id}/resume",
            headers=self._headers(),
        )

    @with_retry
    def get_history(self, project_id: str, model_run_id: str):
        return self._bff.get(
            f"{BFF_PREFIX}/{project_id}/modelruns/{model_run_id}/history",
            headers=self._headers(),
        )

    @with_retry
    def get_quotas(self, project_id: str):
        return self._bff.get(
            f"{BFF_PREFIX}/{project_id}/quotas",
            headers=self._headers(),
        )

    @with_retry
    def get_frameworks(self, project_id: str, limit: int = 100, offset: int = 0):
        return self._bff.get(
            f"{BFF_PREFIX}/{project_id}/runtime_templates",
            params={"limit": limit, "offset": offset},
            headers=self._headers(),
        )

    # --- BFF: Predefined Model Catalog ---

    @with_retry
    def get_catalog(self, **params):
        return self._bff.get(
            f"{BFF_PREFIX}/predefined-models",
            params=params,
            headers=self._headers(),
        )

    @with_retry
    def get_catalog_detail(self, model_card_id: str):
        return self._bff.get(
            f"{BFF_PREFIX}/predefined-models/{model_card_id}",
            headers=self._headers(),
        )

    # --- Inference: call deployed models ---

    def _inference_url(self, model_run_id: str, path: str) -> str:
        if not _MODEL_RUN_ID_RE.match(model_run_id):
            raise ValueError(f"Invalid model_run_id: must be alphanumeric/hyphens only, got '{model_run_id}'")
        return f"https://{model_run_id}.{INFERENCE_DOMAIN}{path}"

    @with_retry
    def chat(self, model_run_id: str, payload: dict, use_auth: bool = False):
        return httpx.post(
            self._inference_url(model_run_id, "/v1/chat/completions"),
            json=payload,
            auth=self.auth if use_auth else None,
            headers=self._headers(),
            timeout=120,
        )

    @with_retry
    def embed(self, model_run_id: str, payload: dict, use_auth: bool = False):
        return httpx.post(
            self._inference_url(model_run_id, "/v1/embeddings"),
            json=payload,
            auth=self.auth if use_auth else None,
            headers=self._headers(),
            timeout=120,
        )

    @with_retry
    def rerank(self, model_run_id: str, payload: dict, use_auth: bool = False):
        return httpx.post(
            self._inference_url(model_run_id, "/v1/rerank"),
            json=payload,
            auth=self.auth if use_auth else None,
            headers=self._headers(),
            timeout=120,
        )

    @with_retry
    def ping(self, model_run_id: str, use_auth: bool = False):
        return httpx.get(
            self._inference_url(model_run_id, "/v1/models"),
            auth=self.auth if use_auth else None,
            headers=self._headers(),
            timeout=30,
        )
