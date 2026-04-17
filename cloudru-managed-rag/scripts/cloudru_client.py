"""Cloud.ru Managed RAG client.

IAMAuth and retry logic copied from cloudru-ml-inference.
Only requires: httpx.
"""

from __future__ import annotations

import os
import re
import threading
import time
import uuid
from functools import wraps
from urllib.parse import urlparse

import httpx

# Bypass corporate proxy for all Cloud.ru API calls
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(_k, None)

IAM_URL = "https://iam.api.cloud.ru"
PUBLIC_API_URL = "https://managed-rag.api.cloud.ru"
SEARCH_DOMAIN = "managed-rag.inference.cloud.ru"

MAX_RETRIES = 3
RETRY_STATUSES = (502, 503, 504)
RETRY_BACKOFF_BASE = 1  # seconds


# --- Retry (copied from cloudru-ml-inference) ---


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
            sleep_time = RETRY_BACKOFF_BASE * (2 ** attempt)
            time.sleep(sleep_time)
        if last_exc:
            raise last_exc
        if response is not None:
            response.raise_for_status()
        return response

    return wrapper


# --- IAM Auth (copied from cloudru-ml-inference) ---


class IAMAuth(httpx.Auth):
    """httpx Auth handler that auto-obtains and refreshes Cloud.ru IAM tokens."""

    def __init__(self, key_id: str, key_secret: str):
        self.key_id = key_id
        self.key_secret = key_secret
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._lock = threading.Lock()

    def __getstate__(self):
        raise TypeError("IAMAuth objects cannot be pickled (contains sensitive token)")

    def _fetch_token(self):
        # Use a fresh client to bypass corporate proxy
        with httpx.Client(transport=httpx.HTTPTransport(proxy=None)) as c:
            resp = c.post(
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


# --- Managed RAG Client ---


class ManagedRagClient:
    """Client for Cloud.ru Managed RAG Public API and Search API."""

    def __init__(self, key_id: str, key_secret: str, timeout: float = 60):
        self.auth = IAMAuth(key_id, key_secret)
        self._public = httpx.Client(
            base_url=PUBLIC_API_URL,
            auth=self.auth,
            timeout=timeout,
            transport=httpx.HTTPTransport(proxy=None),
        )
        self._search_clients: dict[str, httpx.Client] = {}
        self._search_clients_lock = threading.Lock()

    def _headers(self):
        return {"X-Request-ID": str(uuid.uuid4())}

    _KB_ID_RE = re.compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )

    @staticmethod
    def _validate_search_url(url: str) -> None:
        """Validate that the search URL points to a trusted Cloud.ru domain."""
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise ValueError(f"Search URL must use HTTPS, got: {parsed.scheme}")
        if parsed.username or parsed.password:
            raise ValueError("Search URL must not contain user credentials")
        host = parsed.hostname or ""
        expected_suffix = f".{SEARCH_DOMAIN}"
        if not host.endswith(expected_suffix):
            raise ValueError(
                f"Search URL host '{host}' is not under trusted domain '{SEARCH_DOMAIN}'"
            )
        subdomain = host[: -len(expected_suffix)]
        if not ManagedRagClient._KB_ID_RE.match(subdomain):
            raise ValueError(
                f"Search URL subdomain '{subdomain}' is not a valid KB UUID"
            )

    def _search_client(self, search_url: str) -> httpx.Client:
        """Get or create a search client for a specific KB search URL."""
        if not search_url.startswith("https://"):
            search_url = f"https://{search_url}"
        search_url = search_url.rstrip("/")
        self._validate_search_url(search_url)

        with self._search_clients_lock:
            if search_url not in self._search_clients:
                self._search_clients[search_url] = httpx.Client(
                    base_url=search_url,
                    transport=httpx.HTTPTransport(proxy=None),
                    auth=self.auth,
                    timeout=120,
                )
            return self._search_clients[search_url]

    # --- Public API: Knowledge Base CRUD ---

    @with_retry
    def list_kbs(self, project_id: str, page_size: int = 50):
        return self._public.get(
            "/v1/knowledge-bases",
            params={"project_id": project_id, "page_size": page_size},
            headers=self._headers(),
        )

    @with_retry
    def get_kb(self, kb_id: str, project_id: str):
        return self._public.get(
            f"/v1/knowledge-bases/{kb_id}",
            params={"project_id": project_id},
            headers=self._headers(),
        )

    @with_retry
    def delete_kb(self, kb_id: str, project_id: str):
        return self._public.request(
            "DELETE",
            f"/v1/knowledge-bases/{kb_id}",
            json={"project_id": project_id},
            headers=self._headers(),
        )

    @with_retry
    def list_versions(self, kb_id: str, project_id: str, page_size: int = 50):
        return self._public.get(
            "/v1/knowledge-bases/versions",
            params={
                "knowledgebase_id": kb_id,
                "project_id": project_id,
                "page_size": page_size,
            },
            headers=self._headers(),
        )

    @with_retry
    def get_version(self, version_id: str, project_id: str, kb_id: str = ""):
        params = {"project_id": project_id}
        if kb_id:
            params["knowledgebase_id"] = kb_id
        return self._public.get(
            f"/v1/knowledge-bases/versions/{version_id}",
            params=params,
            headers=self._headers(),
        )

    @with_retry
    def reindex_version(self, version_id: str, kb_id: str, project_id: str):
        return self._public.post(
            f"/v1/knowledge-bases/versions/{version_id}/reindex",
            json={"knowledgebaseId": kb_id, "projectId": project_id},
            headers=self._headers(),
        )

    # --- Search API: Retrieve & Generate ---

    @with_retry
    def search(self, search_url: str, query: str, num_results: int = 5,
               kb_version: str = "latest", rerank_model: str | None = None,
               rerank_results: int = 0):
        body = {
            "knowledge_base_version": kb_version,
            "query": query,
            "retrieval_configuration": {
                "number_of_results": num_results,
                "retrieval_type": "SEMANTIC",
            },
            "request_id": str(uuid.uuid4()),
        }
        if rerank_model:
            body["reranking_configuration"] = {
                "model_name": rerank_model,
                "model_source": "FOUNDATION_MODELS",
                "number_of_reranked_results": rerank_results or num_results,
            }
        client = self._search_client(search_url)
        return client.post("/api/v2/retrieve", json=body, headers=self._headers())

    @with_retry
    def ask(self, search_url: str, query: str, num_results: int = 3,
            kb_version: str = "latest", model: str = "t-tech/T-lite-it-1.0",
            system_prompt: str | None = None, rerank_model: str | None = None,
            rerank_results: int = 0):
        gen_config = {
            "model_name": model,
            "model_source": "FOUNDATION_MODELS",
            "number_of_chunks_in_context": num_results,
        }
        if system_prompt:
            gen_config["system_prompt"] = system_prompt

        body = {
            "knowledge_base_version": kb_version,
            "query": query,
            "retrieval_configuration": {
                "number_of_results": num_results,
                "retrieval_type": "SEMANTIC",
            },
            "generationConfiguration": gen_config,
            "requestId": str(uuid.uuid4()),
        }
        if rerank_model:
            body["reranking_configuration"] = {
                "model_name": rerank_model,
                "model_source": "FOUNDATION_MODELS",
                "number_of_reranked_results": rerank_results or num_results,
            }
        client = self._search_client(search_url)
        return client.post(
            "/api/v2/retrieve_generate", json=body, headers=self._headers()
        )

    # --- Helpers ---

    def resolve_search_url(self, kb_id: str, project_id: str) -> str:
        """Get Search API URL from KB metadata (searchApiResponse.url)."""
        resp = self.get_kb(kb_id, project_id)
        if not resp.is_success:
            return ""
        data = resp.json()
        url = data.get("searchApiResponse", {}).get("url", "")
        if not url and kb_id:
            url = f"https://{kb_id}.{SEARCH_DOMAIN}"
        return url
