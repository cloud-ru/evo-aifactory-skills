# Cloud.ru VM — Python Examples

## Setup

```python
import os
from cloudru_client import CloudruComputeClient

client = CloudruComputeClient(
    os.environ["CP_CONSOLE_KEY_ID"],
    os.environ["CP_CONSOLE_SECRET"],
)
PROJECT_ID = os.environ["PROJECT_ID"]
```

## 1. List VMs

```python
res = client.list_vms(PROJECT_ID, limit=10)
assert res.is_success
for vm in res.json()["items"]:
    print(f"{vm['id']} | {vm['name']} | {vm['state']}")
```

## 2. Create VM

```python
payload = {
    "project_id": PROJECT_ID,
    "name": "my-test-vm",
    "flavor_name": "m1.medium",
    "image_name": "Ubuntu-22.04",
    "availability_zone_name": "ru-9a",
    "disks": [{"name": "my-test-vm-boot", "size": 20}],
}
res = client.create_vm(payload)
assert res.is_success
print(f"VM ID: {res.json()['id']}")
```

## 3. Create VM with cloud-init

```python
cloud_init = """#cloud-config
users:
  - name: admin
    ssh_authorized_keys:
      - ssh-rsa AAAA...
    sudo: ALL=(ALL) NOPASSWD:ALL
packages:
  - docker.io
  - nginx
"""

payload = {
    "project_id": PROJECT_ID,
    "name": "web-server",
    "flavor_name": "m1.large",
    "image_name": "Ubuntu-22.04",
    "availability_zone_name": "ru-9a",
    "disks": [{"name": "web-server-boot", "size": 50}],
    "cloud_init": cloud_init,
}
res = client.create_vm(payload)
assert res.is_success
```

## 4. Power Control

```python
vm_id = "..."

# Start
client.set_power(vm_id, "power_on")

# Stop
client.set_power(vm_id, "power_off")

# Reboot
client.set_power(vm_id, "reboot")
```

## 5. Delete VM

```python
res = client.delete_vm(vm_id)
assert res.is_success
```

## 6. List Flavors

```python
res = client.list_flavors(project_id=PROJECT_ID)
assert res.is_success
for f in res.json()["items"]:
    print(f"{f['name']}: {f['cpu']}cpu, {f['ram']}GB RAM")
```

## 7. List Images

```python
res = client.list_images(PROJECT_ID, limit=20)
assert res.is_success
for img in res.json()["items"]:
    print(f"{img['name']}: {img.get('os_type', '?')}")
```

## 8. Create and Attach Disk

```python
# Create
res = client.create_disk({
    "project_id": PROJECT_ID,
    "name": "data-disk",
    "size": 100,
    "availability_zone_name": "ru-9a",
})
disk_id = res.json()["id"]

# Attach to VM
client.attach_disk(disk_id, {"vm_id": vm_id})
```

## 9. Get Remote Console

```python
res = client.remote_console(vm_id, protocol="vnc")
assert res.is_success
print(f"VNC URL: {res.json()['url']}")
```

## 10. Poll VM Until Running

```python
import time

for _ in range(30):
    res = client.get_vm(vm_id)
    state = res.json().get("state", "?")
    print(f"State: {state}")
    if state == "running":
        break
    time.sleep(10)
```
