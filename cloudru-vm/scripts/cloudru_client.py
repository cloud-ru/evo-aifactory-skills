"""Lightweight Cloud.ru Compute (VM) API client.

Only requires: httpx.
"""

import re
import time
import uuid
from functools import wraps

import httpx

IAM_URL = "https://iam.api.cloud.ru"
COMPUTE_URL = "https://compute.api.cloud.ru"
API_PREFIX = "/api/v1"

MAX_RETRIES = 3
RETRY_STATUSES = (502, 503, 504)
RETRY_BACKOFF_BASE = 1


def with_retry(func):
    """Retry on connection errors and 502/503/504."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        last_exc = None
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
        return response

    return wrapper


class IAMAuth(httpx.Auth):
    """httpx Auth handler that auto-obtains and refreshes Cloud.ru IAM tokens."""

    def __init__(self, key_id: str, key_secret: str):
        self.key_id = key_id
        self.key_secret = key_secret
        self._token: str | None = None

    def _fetch_token(self):
        resp = httpx.post(
            f"{IAM_URL}/api/v1/auth/token",
            json={"keyId": self.key_id, "secret": self.key_secret},
            timeout=30,
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]

    def sync_auth_flow(self, request):
        if not self._token:
            self._fetch_token()
        request.headers["Authorization"] = f"Bearer {self._token}"
        response = yield request
        if response.status_code in (401, 403):
            self._fetch_token()
            request.headers["Authorization"] = f"Bearer {self._token}"
            yield request


_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _validate_uuid(value: str, label: str) -> str:
    if not _UUID_RE.match(value):
        raise ValueError(f"{label} must be a valid UUID, got: {value}")
    return value


class CloudruComputeClient:
    """Client for Cloud.ru Compute API (Virtual Machines service)."""

    def __init__(self, key_id: str, key_secret: str, timeout: float = 60):
        self.auth = IAMAuth(key_id, key_secret)
        self._client = httpx.Client(
            base_url=COMPUTE_URL,
            auth=self.auth,
            timeout=timeout,
        )

    def _headers(self):
        return {"X-Request-ID": str(uuid.uuid4())}

    # --- VMs ---

    @with_retry
    def list_vms(self, project_id: str, **params):
        params["project_id"] = project_id
        return self._client.get(f"{API_PREFIX}/vms", params=params, headers=self._headers())

    @with_retry
    def get_vm(self, vm_id: str):
        _validate_uuid(vm_id, "vm_id")
        return self._client.get(f"{API_PREFIX}/vms/{vm_id}", headers=self._headers())

    @with_retry
    def create_vm(self, payload: dict):
        return self._client.post(f"{API_PREFIX}.1/vms", json=[payload], headers=self._headers())

    @with_retry
    def update_vm(self, vm_id: str, payload: dict):
        _validate_uuid(vm_id, "vm_id")
        return self._client.put(f"{API_PREFIX}/vms/{vm_id}", json=payload, headers=self._headers())

    @with_retry
    def delete_vm(self, vm_id: str):
        _validate_uuid(vm_id, "vm_id")
        return self._client.delete(f"{API_PREFIX}/vms/{vm_id}", headers=self._headers())

    @with_retry
    def set_power(self, vm_id: str, state: str):
        _validate_uuid(vm_id, "vm_id")
        return self._client.post(
            f"{API_PREFIX}/vms/{vm_id}/set-power",
            json={"state": state},
            headers=self._headers(),
        )

    @with_retry
    def get_vnc(self, vm_id: str):
        _validate_uuid(vm_id, "vm_id")
        return self._client.post(f"{API_PREFIX}/vms/{vm_id}/get-vnc", headers=self._headers())

    @with_retry
    def remote_console(self, vm_id: str, protocol: str = "vnc"):
        _validate_uuid(vm_id, "vm_id")
        return self._client.post(
            f"{API_PREFIX}/vms/{vm_id}/remote-console",
            json={"protocol": protocol},
            headers=self._headers(),
        )

    # --- Disks ---

    @with_retry
    def list_disks(self, project_id: str, **params):
        params["project_id"] = project_id
        return self._client.get(f"{API_PREFIX}/disks", params=params, headers=self._headers())

    @with_retry
    def get_disk(self, disk_id: str):
        _validate_uuid(disk_id, "disk_id")
        return self._client.get(f"{API_PREFIX}/disks/{disk_id}", headers=self._headers())

    @with_retry
    def create_disk(self, payload: dict):
        return self._client.post(f"{API_PREFIX}/disks", json=payload, headers=self._headers())

    @with_retry
    def delete_disk(self, disk_id: str):
        _validate_uuid(disk_id, "disk_id")
        return self._client.delete(f"{API_PREFIX}/disks/{disk_id}", headers=self._headers())

    @with_retry
    def attach_disk(self, disk_id: str, payload: dict):
        _validate_uuid(disk_id, "disk_id")
        return self._client.post(f"{API_PREFIX}/disks/{disk_id}/attach", json=payload, headers=self._headers())

    @with_retry
    def detach_disk(self, disk_id: str, payload: dict):
        _validate_uuid(disk_id, "disk_id")
        return self._client.post(f"{API_PREFIX}/disks/{disk_id}/detach", json=payload, headers=self._headers())

    # --- Flavors ---

    @with_retry
    def list_flavors(self, **params):
        return self._client.get(f"{API_PREFIX}/flavors", params=params, headers=self._headers())

    @with_retry
    def get_flavor(self, flavor_id: str):
        return self._client.get(f"{API_PREFIX}/flavors/{flavor_id}", headers=self._headers())

    # --- Images ---

    @with_retry
    def list_images(self, project_id: str, **params):
        params["project_id"] = project_id
        return self._client.get(f"{API_PREFIX}/images", params=params, headers=self._headers())

    @with_retry
    def get_image(self, image_id: str):
        return self._client.get(f"{API_PREFIX}/images/{image_id}", headers=self._headers())

    # --- Subnets ---

    @with_retry
    def list_subnets(self, project_id: str, **params):
        params["project_id"] = project_id
        return self._client.get(f"{API_PREFIX}/subnets", params=params, headers=self._headers())

    # --- Security Groups ---

    @with_retry
    def list_security_groups(self, project_id: str, **params):
        params["project_id"] = project_id
        return self._client.get(f"{API_PREFIX}/security-groups", params=params, headers=self._headers())

    @with_retry
    def create_security_group(self, payload: dict):
        return self._client.post(f"{API_PREFIX}/security-groups", json=payload, headers=self._headers())

    @with_retry
    def get_security_group(self, sg_id: str):
        return self._client.get(f"{API_PREFIX}/security-groups/{sg_id}", headers=self._headers())

    @with_retry
    def delete_security_group(self, sg_id: str):
        return self._client.delete(f"{API_PREFIX}/security-groups/{sg_id}", headers=self._headers())

    # --- Security Group Rules ---

    @with_retry
    def list_sg_rules(self, sg_id: str, **params):
        return self._client.get(f"{API_PREFIX}/security-groups/{sg_id}/rules", params=params, headers=self._headers())

    @with_retry
    def create_sg_rule(self, sg_id: str, payload: dict):
        return self._client.post(f"{API_PREFIX}/security-groups/{sg_id}/rules", json=payload, headers=self._headers())

    @with_retry
    def delete_sg_rule(self, sg_id: str, rule_id: str):
        return self._client.delete(f"{API_PREFIX}/security-groups/{sg_id}/rules/{rule_id}", headers=self._headers())

    # --- Availability Zones ---

    @with_retry
    def list_zones(self, **params):
        return self._client.get(f"{API_PREFIX}/availability-zones", params=params, headers=self._headers())

    # --- Disk Types ---

    @with_retry
    def list_disk_types(self, **params):
        return self._client.get(f"{API_PREFIX}/disk-types", params=params, headers=self._headers())

    # --- Floating IPs ---

    @with_retry
    def list_floating_ips(self, project_id: str, **params):
        params["project_id"] = project_id
        return self._client.get(f"{API_PREFIX}/floating-ips", params=params, headers=self._headers())

    @with_retry
    def create_floating_ip(self, payload: dict):
        return self._client.post(f"{API_PREFIX}/floating-ips", json=payload, headers=self._headers())

    @with_retry
    def delete_floating_ip(self, floating_ip_id: str):
        return self._client.delete(f"{API_PREFIX}/floating-ips/{floating_ip_id}", headers=self._headers())

    # --- Tasks ---

    @with_retry
    def get_task(self, task_id: str):
        return self._client.get(f"{API_PREFIX}/tasks/{task_id}", headers=self._headers())
