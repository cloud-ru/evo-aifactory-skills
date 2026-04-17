# Cloud.ru Compute API Reference

## Overview

Base URL: `https://compute.api.cloud.ru`
Auth: Bearer token from `https://iam.api.cloud.ru/api/v1/auth/token`

All endpoints require `Authorization: Bearer <token>` header.

## VM Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/vms?project_id=...` | List VMs |
| GET | `/api/v1/vms/{vm_id}` | Get VM by ID |
| POST | `/api/v1.1/vms` | Create VM (v1.1 — current) |
| PUT | `/api/v1/vms/{vm_id}` | Update VM |
| DELETE | `/api/v1/vms/{vm_id}` | Delete VM |
| POST | `/api/v1/vms/{vm_id}/set-power` | Power control (start/stop/reboot) |
| POST | `/api/v1/vms/{vm_id}/get-vnc` | Get VNC URL |
| POST | `/api/v1/vms/{vm_id}/remote-console` | Get remote console URL |
| POST | `/api/v1/vms/{vm_id}/rebuild` | Rebuild VM (change OS) |

## Disk Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/disks?project_id=...` | List disks |
| GET | `/api/v1/disks/{disk_id}` | Get disk |
| POST | `/api/v1/disks` | Create disk |
| PUT | `/api/v1/disks/{disk_id}` | Update disk |
| DELETE | `/api/v1/disks/{disk_id}` | Delete disk |
| POST | `/api/v1/disks/{disk_id}/attach` | Attach to VM |
| POST | `/api/v1/disks/{disk_id}/detach` | Detach from VM |

## Infrastructure Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/flavors` | List flavors |
| GET | `/api/v1/flavors/{id}` | Get flavor |
| GET | `/api/v1/images?project_id=...` | List images |
| GET | `/api/v1/images/{id}` | Get image |
| GET | `/api/v1/subnets?project_id=...` | List subnets |
| GET | `/api/v1/availability-zones` | List zones |
| GET | `/api/v1/disk-types` | List disk types |
| GET | `/api/v1/security-groups?project_id=...` | List security groups |
| GET | `/api/v1/floating-ips?project_id=...` | List floating IPs |
| GET | `/api/v1/tasks/{task_id}` | Get task status |

## Create VM Request (POST /api/v1.1/vms)

```json
{
    "project_id": "<uuid>",
    "name": "my-vm",
    "flavor_name": "m1.medium",
    "image_name": "Ubuntu-22.04",
    "availability_zone_name": "ru-9a",
    "description": "",
    "disks": [
        {"name": "boot-disk", "size": 20, "disk_type_name": "ssd"}
    ],
    "interfaces": [
        {"subnet_name": "default"}
    ],
    "cloud_init": "#cloud-config\n..."
}

```

### Fields

**Required:** `project_id`, `name`, `disks` (at least 1 boot disk)

**Choose one of each pair:**
- `flavor_id` OR `flavor_name`
- `image_id` OR `image_name`
- `availability_zone_id` OR `availability_zone_name`

**Disk options (new disk):** `name` (required), `size` (required, 1-16384 GB), `disk_type_id` OR `disk_type_name`

**Disk options (existing disk):** `disk_id` OR `disk_name`

## Power Control (POST /api/v1/vms/{vm_id}/set-power)

```json
{"state": "power_on"}
```

Values: `power_on`, `power_off`, `reboot`

## VM States

| State | Description |
|-------|-------------|
| `running` | VM is running |
| `stopped` | VM is stopped |
| `creating` | Being created |
| `starting` | Starting up |
| `stopping` | Shutting down |
| `rebooting` | Rebooting |
| `deleting` | Being deleted |
| `updating` | Being updated |
| `rebuilding` | Changing OS image |
| `error` | General error |
| `error_creating` | Creation failed |
| `error_deleting` | Deletion failed |

## Common Query Parameters (list endpoints)

- `project_id` (required for most)
- `limit` (default: 50, max: 100)
- `offset` (default: 0)
- `order_by` (e.g. `created_time`)
- `order_desc` (bool, default: true)
- `state` (filter VMs by state)
- `name` (filter by name)
