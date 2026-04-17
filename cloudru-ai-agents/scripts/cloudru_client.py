"""Cloud.ru AI Agents client.

IAMAuth and retry logic copied from cloudru-managed-rag.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx

# Bypass corporate proxy for all Cloud.ru API calls
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(_k, None)


IAM_URL = "https://iam.api.cloud.ru"
# BFF endpoint — raw public API (ai-agents.api.cloud.ru) has server-side bugs on
# POST /agents (nil pointer / invalid UUID); BFF injects required defaults and
# accepts the same IAM Bearer token.
PUBLIC_API_URL = "https://console.cloud.ru"
API_PREFIX = "/u-api/ai-agents/v1"

RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_BASE = 1.0


# --- Retry (copied from cloudru-managed-rag) ---

def _retryable(resp: httpx.Response) -> bool:
    return resp.status_code >= 500


def _request_with_retry(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(RETRY_MAX_ATTEMPTS):
        try:
            resp = client.request(method, url, **kwargs)
            if not _retryable(resp) or attempt == RETRY_MAX_ATTEMPTS - 1:
                return resp
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt == RETRY_MAX_ATTEMPTS - 1:
                raise
        sleep_time = RETRY_BACKOFF_BASE * (2 ** attempt)
        time.sleep(sleep_time)
    if last_exc:
        raise last_exc
    return resp  # type: ignore


# --- IAM Auth (copied from cloudru-managed-rag) ---

class IAMAuth(httpx.Auth):
    requires_response_body = True

    def __init__(self, key_id: str, key_secret: str):
        self.key_id = key_id
        self.key_secret = key_secret
        self._token: Optional[str] = None

    def _refresh(self) -> None:
        with httpx.Client(transport=httpx.HTTPTransport(proxy=None)) as c:
            resp = c.post(
                f"{IAM_URL}/api/v1/auth/token",
                json={"keyId": self.key_id, "secret": self.key_secret},
                timeout=30,
            )
            resp.raise_for_status()
            self._token = resp.json()["access_token"]

    def auth_flow(self, request):
        if self._token is None:
            self._refresh()
        request.headers["Authorization"] = f"Bearer {self._token}"
        response = yield request
        if response.status_code == 401:
            self._refresh()
            request.headers["Authorization"] = f"Bearer {self._token}"
            yield request


# --- AI Agents Client ---

class CloudruAiAgentsClient:
    """Client for Cloud.ru AI Agents public API."""

    def __init__(self, key_id: str, key_secret: str):
        self._auth = IAMAuth(key_id, key_secret)
        self._client = httpx.Client(
            base_url=PUBLIC_API_URL,
            auth=self._auth,
            timeout=30.0,
            transport=httpx.HTTPTransport(proxy=None),
        )

    def _headers(self) -> Dict[str, str]:
        return {"X-Request-ID": str(uuid.uuid4())}

    # ---- Agents ----

    def list_agents(self, project_id: str, *, limit: int = 100, offset: int = 0,
                    statuses: Optional[list] = None,
                    not_in_statuses: Optional[list] = None) -> httpx.Response:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if statuses:
            params["statuses"] = statuses
        if not_in_statuses:
            params["notInStatuses"] = not_in_statuses
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/agents",
            params=params, headers=self._headers(),
        )

    def get_agent(self, project_id: str, agent_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/agents/{agent_id}",
            headers=self._headers(),
        )

    def create_agent(self, project_id: str, body: Dict[str, Any]) -> httpx.Response:
        return _request_with_retry(
            self._client, "POST", f"/u-api/ai-agents/v1/{project_id}/agents",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def update_agent(self, project_id: str, agent_id: str, body: Dict[str, Any]) -> httpx.Response:
        return _request_with_retry(
            self._client, "PATCH", f"/u-api/ai-agents/v1/{project_id}/agents/{agent_id}",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def delete_agent(self, project_id: str, agent_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "DELETE", f"/u-api/ai-agents/v1/{project_id}/agents/{agent_id}",
            headers=self._headers(),
        )

    def suspend_agent(self, project_id: str, agent_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "PATCH", f"/u-api/ai-agents/v1/{project_id}/agents/suspend/{agent_id}",
            headers=self._headers(),
        )

    def resume_agent(self, project_id: str, agent_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "PATCH", f"/u-api/ai-agents/v1/{project_id}/agents/resume/{agent_id}",
            headers=self._headers(),
        )

    # ---- Agent Systems ----

    def list_systems(self, project_id: str, *, limit: int = 100, offset: int = 0) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/agentSystems",
            params={"limit": limit, "offset": offset}, headers=self._headers(),
        )

    def get_system(self, project_id: str, system_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/agentSystems/{system_id}",
            headers=self._headers(),
        )

    def create_system(self, project_id: str, body: Dict[str, Any]) -> httpx.Response:
        return _request_with_retry(
            self._client, "POST", f"/u-api/ai-agents/v1/{project_id}/agentSystems",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def update_system(self, project_id: str, system_id: str, body: Dict[str, Any]) -> httpx.Response:
        return _request_with_retry(
            self._client, "PATCH", f"/u-api/ai-agents/v1/{project_id}/agentSystems/{system_id}",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def delete_system(self, project_id: str, system_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "DELETE", f"/u-api/ai-agents/v1/{project_id}/agentSystems/{system_id}",
            headers=self._headers(),
        )

    def suspend_system(self, project_id: str, system_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "PATCH", f"/u-api/ai-agents/v1/{project_id}/agentSystems/suspend/{system_id}",
            headers=self._headers(),
        )

    def resume_system(self, project_id: str, system_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "PATCH", f"/u-api/ai-agents/v1/{project_id}/agentSystems/resume/{system_id}",
            headers=self._headers(),
        )

    # ---- MCP Servers ----

    def list_mcp_servers(self, project_id: str, *, limit: int = 100, offset: int = 0,
                          not_in_statuses: Optional[list] = None) -> httpx.Response:
        params: Dict[str, Any] = {"limit": limit, "offset": offset,
                                   "notInStatuses": not_in_statuses or
                                   ["MCP_SERVER_STATUS_DELETED", "MCP_SERVER_STATUS_ON_DELETION"]}
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/mcpServers",
            params=params, headers=self._headers(),
        )

    def get_mcp_server(self, project_id: str, mcp_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/mcpServers/{mcp_id}",
            headers=self._headers(),
        )

    def create_mcp_server(self, project_id: str, body: Dict[str, Any]) -> httpx.Response:
        return _request_with_retry(
            self._client, "POST", f"/u-api/ai-agents/v1/{project_id}/mcpServers",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def update_mcp_server(self, project_id: str, mcp_id: str, body: Dict[str, Any]) -> httpx.Response:
        return _request_with_retry(
            self._client, "PATCH", f"/u-api/ai-agents/v1/{project_id}/mcpServers/{mcp_id}",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def delete_mcp_server(self, project_id: str, mcp_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "DELETE", f"/u-api/ai-agents/v1/{project_id}/mcpServers/{mcp_id}",
            headers=self._headers(),
        )

    def suspend_mcp_server(self, project_id: str, mcp_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "PATCH", f"/u-api/ai-agents/v1/{project_id}/mcpServers/suspend/{mcp_id}",
            headers=self._headers(),
        )

    def resume_mcp_server(self, project_id: str, mcp_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "PATCH", f"/u-api/ai-agents/v1/{project_id}/mcpServers/resume/{mcp_id}",
            headers=self._headers(),
        )

    # ---- Instance Types ----

    def list_instance_types(self, project_id: str, *, is_active: bool = True,
                             limit: int = 100, offset: int = 0) -> httpx.Response:
        params: Dict[str, Any] = {"limit": limit, "offset": offset, "isActive": str(is_active).lower()}
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/instanceTypes",
            params=params, headers=self._headers(),
        )

    # ---- Marketplace ----

    def list_marketplace_agents(self, project_id: str, *, search: Optional[str] = None,
                                 limit: int = 100, offset: int = 0,
                                 sort: str = "SORT_TYPE_POPULARITY_DESC") -> httpx.Response:
        params: Dict[str, Any] = {"limit": limit, "offset": offset, "name": search or "",
                                   "source": "all", "sortType": sort}
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/marketplace/agents",
            params=params, headers=self._headers(),
        )

    def get_marketplace_agent(self, project_id: str, card_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/marketplace/agents/{card_id}",
            headers=self._headers(),
        )

    def list_marketplace_mcp_servers(self, project_id: str, *, search: Optional[str] = None,
                                      limit: int = 100, offset: int = 0,
                                      sort: str = "SORT_TYPE_POPULARITY_DESC") -> httpx.Response:
        params: Dict[str, Any] = {"limit": limit, "offset": offset, "name": search or "",
                                   "source": "all", "sortType": sort}
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/marketplace/mcpServers",
            params=params, headers=self._headers(),
        )

    def get_marketplace_mcp_server(self, project_id: str, card_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/marketplace/mcpServers/{card_id}",
            headers=self._headers(),
        )

    # ---- Prompts ----

    def list_prompts(self, project_id: str, *, limit: int = 100, offset: int = 0,
                     name: Optional[str] = None,
                     not_in_statuses: Optional[list] = None) -> httpx.Response:
        params: Dict[str, Any] = {"limit": limit, "offset": offset,
                                   "notInStatuses": not_in_statuses or
                                   ["PROMPT_STATUS_DELETED", "PROMPT_STATUS_ON_DELETION"]}
        if name:
            params["name"] = name
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/prompts",
            params=params, headers=self._headers(),
        )

    def get_prompt(self, project_id: str, prompt_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/prompts/{prompt_id}",
            headers=self._headers(),
        )

    def create_prompt(self, project_id: str, body: Dict[str, Any]) -> httpx.Response:
        return _request_with_retry(
            self._client, "POST", f"/u-api/ai-agents/v1/{project_id}/prompts",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def update_prompt(self, project_id: str, prompt_id: str, body: Dict[str, Any]) -> httpx.Response:
        return _request_with_retry(
            self._client, "PATCH", f"/u-api/ai-agents/v1/{project_id}/prompts/{prompt_id}",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def delete_prompt(self, project_id: str, prompt_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "DELETE", f"/u-api/ai-agents/v1/{project_id}/prompts/{prompt_id}",
            headers=self._headers(),
        )

    def list_prompt_versions(self, project_id: str, prompt_id: str, *,
                             limit: int = 100, offset: int = 0) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/prompts/{prompt_id}/versions",
            params={"limit": limit, "offset": offset}, headers=self._headers(),
        )

    def list_marketplace_prompts(self, project_id: str, *, search: Optional[str] = None,
                                  limit: int = 100, offset: int = 0,
                                  sort: str = "SORT_TYPE_POPULARITY_DESC") -> httpx.Response:
        params: Dict[str, Any] = {"limit": limit, "offset": offset, "name": search or "",
                                   "sortType": sort}
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/marketplace/prompts",
            params=params, headers=self._headers(),
        )

    def get_marketplace_prompt(self, project_id: str, card_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/marketplace/prompts/{card_id}",
            headers=self._headers(),
        )

    # ---- Snippets (Фрагменты) ----

    def list_snippets(self, project_id: str, *, limit: int = 100, offset: int = 0,
                      name: Optional[str] = None,
                      block_styles: Optional[list] = None,
                      statuses: Optional[list] = None) -> httpx.Response:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if name:
            params["name"] = name
        if block_styles:
            params["blockStyles"] = block_styles
        if statuses:
            params["statuses"] = statuses
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/snippets",
            params=params, headers=self._headers(),
        )

    def get_snippet(self, project_id: str, snippet_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/snippets/{snippet_id}",
            headers=self._headers(),
        )

    def create_snippet(self, project_id: str, body: Dict[str, Any]) -> httpx.Response:
        return _request_with_retry(
            self._client, "POST", f"/u-api/ai-agents/v1/{project_id}/snippets",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def update_snippet(self, project_id: str, snippet_id: str, body: Dict[str, Any]) -> httpx.Response:
        return _request_with_retry(
            self._client, "PATCH", f"/u-api/ai-agents/v1/{project_id}/snippets/{snippet_id}",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def delete_snippet(self, project_id: str, snippet_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "DELETE", f"/u-api/ai-agents/v1/{project_id}/snippets/{snippet_id}",
            headers=self._headers(),
        )

    def list_marketplace_snippets(self, *, search: Optional[str] = None,
                                   limit: int = 100, offset: int = 0,
                                   block_styles: Optional[list] = None) -> httpx.Response:
        params: Dict[str, Any] = {"limit": limit, "offset": offset, "search": search or ""}
        if block_styles:
            params["blockStyles"] = block_styles
        return _request_with_retry(
            self._client, "GET", "/u-api/ai-agents/v1/marketplace/snippets",
            params=params, headers=self._headers(),
        )

    # ---- Skills (Навыки) ----

    def list_skills(self, project_id: str, *, limit: int = 100, offset: int = 0,
                    name: Optional[str] = None,
                    not_in_statuses: Optional[list] = None) -> httpx.Response:
        params: Dict[str, Any] = {"limit": limit, "offset": offset,
                                   "notInStatuses": not_in_statuses or ["SKILL_STATUS_DELETED"]}
        if name:
            params["name"] = name
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/skills",
            params=params, headers=self._headers(),
        )

    def get_skill(self, project_id: str, skill_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/skills/{skill_id}",
            headers=self._headers(),
        )

    def create_skill(self, project_id: str, body: Dict[str, Any]) -> httpx.Response:
        return _request_with_retry(
            self._client, "POST", f"/u-api/ai-agents/v1/{project_id}/skills",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def delete_skill(self, project_id: str, skill_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "DELETE", f"/u-api/ai-agents/v1/{project_id}/skills/{skill_id}",
            headers=self._headers(),
        )

    def analyze_skill_source(self, project_id: str, body: Dict[str, Any]) -> httpx.Response:
        """Probe git/file source — returns fileTree + skillFolderPaths preview."""
        return _request_with_retry(
            self._client, "POST", f"/u-api/ai-agents/v1/{project_id}/skills/analyze-source",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def list_marketplace_skills(self, *, search: Optional[str] = None,
                                 limit: int = 100, offset: int = 0) -> httpx.Response:
        params: Dict[str, Any] = {"limit": limit, "offset": offset, "search": search or ""}
        return _request_with_retry(
            self._client, "GET", "/u-api/ai-agents/v1/marketplace/skills",
            params=params, headers=self._headers(),
        )

    def get_marketplace_skill(self, card_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/marketplace/skills/{card_id}",
            headers=self._headers(),
        )

    def get_marketplace_snippet(self, card_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/marketplace/snippets/{card_id}",
            headers=self._headers(),
        )

    # ---- Workflows ----

    def list_workflows(self, project_id: str, *, limit: int = 100, offset: int = 0,
                       search: Optional[str] = None,
                       statuses: Optional[list] = None) -> httpx.Response:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if search:
            params["search"] = search
        if statuses:
            params["statuses"] = statuses
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/workflows",
            params=params, headers=self._headers(),
        )

    def get_workflow(self, project_id: str, workflow_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/workflows/{workflow_id}",
            headers=self._headers(),
        )

    def delete_workflow(self, project_id: str, workflow_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "DELETE", f"/u-api/ai-agents/v1/{project_id}/workflows/{workflow_id}",
            headers=self._headers(),
        )

    def create_workflow(self, project_id: str, body: dict) -> httpx.Response:
        return _request_with_retry(
            self._client, "POST", f"/u-api/ai-agents/v1/{project_id}/workflows",
            json=body, headers=self._headers(),
        )

    def update_workflow(self, project_id: str, workflow_id: str, body: dict) -> httpx.Response:
        return _request_with_retry(
            self._client, "PATCH", f"/u-api/ai-agents/v1/{project_id}/workflows/{workflow_id}",
            json=body, headers=self._headers(),
        )

    # ---- Triggers ----

    def list_agent_triggers(self, project_id: str, agent_id: str, *,
                            limit: int = 100, offset: int = 0,
                            not_in_statuses: Optional[list] = None) -> httpx.Response:
        params: Dict[str, Any] = {"limit": limit, "offset": offset,
                                   "notInStatuses": not_in_statuses or ["TRIGGER_STATUS_DELETED"]}
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/agents/{agent_id}/triggers",
            params=params, headers=self._headers(),
        )

    # ---- History (audit log) ----

    def get_agent_history(self, project_id: str, agent_id: str, *,
                          limit: int = 100, offset: int = 0) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/agents/{agent_id}/history",
            params={"limit": limit, "offset": offset}, headers=self._headers(),
        )

    # ---- EvoClaw ----

    def list_evo_claws(self, project_id: str, *, limit: int = 100, offset: int = 0,
                        statuses: Optional[list] = None) -> httpx.Response:
        params: Dict[str, Any] = {"limit": limit, "offset": offset, "projectId": project_id}
        if statuses:
            params["statuses"] = statuses
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/evo-claws",
            params=params, headers=self._headers(),
        )

    def get_evo_claw(self, project_id: str, evoclaw_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/evo-claws/{evoclaw_id}",
            headers=self._headers(),
        )

    def create_evo_claw(self, project_id: str, body: Dict[str, Any]) -> httpx.Response:
        return _request_with_retry(
            self._client, "POST", f"/u-api/ai-agents/v1/{project_id}/evo-claws",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def update_evo_claw(self, project_id: str, evoclaw_id: str,
                        body: Dict[str, Any]) -> httpx.Response:
        return _request_with_retry(
            self._client, "PATCH", f"/u-api/ai-agents/v1/{project_id}/evo-claws/{evoclaw_id}",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def delete_evo_claw(self, project_id: str, evoclaw_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "DELETE", f"/u-api/ai-agents/v1/{project_id}/evo-claws/{evoclaw_id}",
            headers=self._headers(),
        )

    def list_evo_claw_workers(self, project_id: str, evoclaw_id: str) -> httpx.Response:
        """List sub-agents (workers) configured inside an EvoClaw managed gateway."""
        return _request_with_retry(
            self._client, "GET",
            f"/u-api/ai-agents/v1/{project_id}/evo-claws/{evoclaw_id}/options/agents",
            headers=self._headers(),
        )

    def set_evo_claw_workers(self, project_id: str, evoclaw_id: str,
                              workers: list) -> httpx.Response:
        """Replace the full list of workers (PUT — not merge). Send all existing
        workers plus/minus the ones you want to change."""
        return _request_with_retry(
            self._client, "PUT",
            f"/u-api/ai-agents/v1/{project_id}/evo-claws/{evoclaw_id}/options/agents",
            json={"agents": workers}, headers=self._headers(), timeout=60.0,
        )

    # ---- A2A Chat (JSON-RPC protocol) ----

    def a2a_agent_card(self, project_id: str, agent_id: str) -> httpx.Response:
        """Fetch agent card — capabilities, inputModes, description (A2A spec)."""
        return _request_with_retry(
            self._client, "GET", f"/u-api/ai-agents/v1/{project_id}/a2a/.well-known/agent.json",
            params={"agentId": agent_id}, headers=self._headers(),
        )

    def a2a_call(self, project_id: str, agent_id: str, body: Dict[str, Any]) -> httpx.Response:
        """Raw JSON-RPC call to agent A2A endpoint (method can be message/send,
        message/stream, tasks/get, tasks/cancel)."""
        return _request_with_retry(
            self._client, "POST", f"/u-api/ai-agents/v1/{project_id}/a2a",
            params={"agentId": agent_id}, json=body, headers=self._headers(),
            timeout=300.0,
        )

    # ---- Triggers (full CRUD) ----

    def check_trigger_name(self, project_id: str, agent_id: str, name: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET",
            f"/u-api/ai-agents/v1/{project_id}/agents/{agent_id}/triggers/check-exists",
            params={"name": name}, headers=self._headers(),
        )

    def get_agent_trigger(self, project_id: str, agent_id: str, trigger_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "GET",
            f"/u-api/ai-agents/v1/{project_id}/agents/{agent_id}/triggers/{trigger_id}",
            headers=self._headers(),
        )

    def create_agent_trigger(self, project_id: str, agent_id: str,
                              body: Dict[str, Any]) -> httpx.Response:
        return _request_with_retry(
            self._client, "POST",
            f"/u-api/ai-agents/v1/{project_id}/agents/{agent_id}/triggers",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def update_agent_trigger(self, project_id: str, agent_id: str, trigger_id: str,
                              body: Dict[str, Any]) -> httpx.Response:
        return _request_with_retry(
            self._client, "PATCH",
            f"/u-api/ai-agents/v1/{project_id}/agents/{agent_id}/triggers/{trigger_id}",
            json=body, headers=self._headers(), timeout=60.0,
        )

    def delete_agent_trigger(self, project_id: str, agent_id: str, trigger_id: str) -> httpx.Response:
        return _request_with_retry(
            self._client, "DELETE",
            f"/u-api/ai-agents/v1/{project_id}/agents/{agent_id}/triggers/{trigger_id}",
            headers=self._headers(),
        )

