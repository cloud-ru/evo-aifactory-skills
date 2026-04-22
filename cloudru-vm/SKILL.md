---
name: cloudru-vm
description: Create and manage Cloud.ru virtual machines — full VM lifecycle, disks, networking, security groups, SSH/SCP. Uses the Cloud.ru Compute API via lightweight httpx-based client.
compatibility: Requires httpx and CP_CONSOLE_KEY_ID, CP_CONSOLE_SECRET, PROJECT_ID environment variables
---

# Cloud.ru Virtual Machines

Manage virtual machines on Cloud.ru: create, start/stop/reboot, resize, delete VMs. Also manage disks, view flavors, images, subnets, security groups, and availability zones.

## When to use

Use this skill when the user:
- Wants to create, manage, or delete virtual machines on Cloud.ru
- Needs to list flavors, images, subnets, or availability zones
- Wants to manage disks (create, attach, detach, delete)
- Needs to start, stop, or reboot a VM
- Asks about Cloud.ru compute/VM infrastructure

## Prerequisites

### Environment variables
- `CP_CONSOLE_KEY_ID` — Cloud.ru service account key ID
- `CP_CONSOLE_SECRET` — Cloud.ru service account secret
- `PROJECT_ID` — Cloud.ru project UUID

If these are not set, guide the user to the `cloudru-account-setup` skill.

### Dependencies

The only external dependency is `httpx`. Install if not present:
```bash
pip install httpx
```

## How to use

### CLI script

The main script is `scripts/vm.py`. It can be run from any directory (sys.path is set automatically).

**Environment variables** can be provided via a `.env` file in the current working directory. The file is loaded automatically at startup. Variables already set in the environment are NOT overwritten. Format:
```
CP_CONSOLE_KEY_ID=your-key-id
CP_CONSOLE_SECRET=your-secret
PROJECT_ID=your-project-uuid
```

### VM lifecycle

```bash
# List VMs
python vm.py list
python vm.py list --state running

# Get VM details
python vm.py get <vm_id>

# Create VM with SSH key auth (recommended — avoids exposing secrets in process list)
python vm.py create \
  --name my-vm \
  --flavor-name lowcost10-2-4 \
  --image-name ubuntu-22.04 \
  --zone-name ru.AZ-1 \
  --disk-size 20 \
  --disk-type-name SSD \
  --login user1 \
  --ssh-key-file ~/.ssh/id_ed25519.pub

# Create VM, wait for it, auto-assign public IP, wait for SSH
python vm.py create \
  --name my-vm \
  --login user1 \
  --ssh-key-file ~/.ssh/id_ed25519.pub \
  --wait --floating-ip --wait-ssh

# Start / Stop / Reboot
python vm.py start <vm_id>
python vm.py stop <vm_id>
python vm.py reboot <vm_id>

# Update VM (rename, resize — VM must be stopped for resize)
python vm.py update <vm_id> --name new-name
python vm.py update <vm_id> --flavor-name lowcost10-4-8

# Delete VM (warns if floating IPs are attached)
python vm.py delete <vm_id>

# Delete VM with auto-cleanup of floating IPs
python vm.py delete <vm_id> --force

# Get VNC console URL
python vm.py vnc <vm_id>
```

### SSH and SCP (remote execution)

Execute commands on a VM or copy files. The `ssh`/`scp` commands auto-resolve the VM's public IP from its floating IP.

```bash
# Execute a command on VM
python vm.py ssh <vm_id> -i ~/.ssh/key -c "uname -a"

# Run multiple commands
python vm.py ssh <vm_id> -i ~/.ssh/key -c "apt update && apt install -y nginx"

# Upload a file to VM
python vm.py scp <vm_id> -i ~/.ssh/key --local-path ./app.py --remote-path /home/user1/app.py

# Download a file from VM
python vm.py scp <vm_id> -i ~/.ssh/key --direction download --local-path ./logs.tar.gz --remote-path /var/log/logs.tar.gz

# Upload a directory
python vm.py scp <vm_id> -i ~/.ssh/key -r --local-path ./my-project --remote-path /home/user1/my-project

# Override IP (if auto-resolve doesn't work)
python vm.py ssh <vm_id> -i ~/.ssh/key --ip 1.2.3.4 -c "hostname"
```

### Infrastructure info

```bash
# List flavors (CPU/RAM/GPU configs)
python vm.py flavors
python vm.py flavors --cpu 4 --ram 8

# List OS images
python vm.py images

# List subnets, zones, disk types, security groups
python vm.py subnets
python vm.py zones
python vm.py disk-types
python vm.py security-groups
```

### Security groups and port management

```bash
# List security groups
python vm.py security-groups

# Create a security group with ports open immediately
python vm.py sg-create --name my-sg --zone-name ru.AZ-1 --open-ports 22 80 443

# Create an empty security group
python vm.py sg-create --name my-sg --zone-name ru.AZ-1 --description "My firewall rules"

# List rules of a security group
python vm.py sg-rules <sg_id>

# Open a port (add ingress rule)
python vm.py sg-rule-add <sg_id> --ports 8080
python vm.py sg-rule-add <sg_id> --ports 8080 --description "App server"

# Open a port range
python vm.py sg-rule-add <sg_id> --ports 3000-3100

# Open a UDP port
python vm.py sg-rule-add <sg_id> --ports 53 --protocol udp

# Restrict to specific IP/CIDR
python vm.py sg-rule-add <sg_id> --ports 22 --remote-ip 203.0.113.0/24

# Close a port (delete a rule)
python vm.py sg-rule-delete <sg_id> <rule_id>

# Delete entire security group
python vm.py sg-delete <sg_id>
```

**Port format:** single port (`22`), range (`3000-3100`). The API normalizes to `port:port` format (e.g. `22:22`, `3000:3100`).

**Protocols:** `tcp` (default), `udp`, `icmp`, `any`.

**Direction:** `ingress` (default, incoming traffic), `egress` (outgoing traffic).

**To assign a security group to a VM:** specify `--security-group-id` when creating the VM, or assign it to the VM's network interface.

### Floating IP (public IP address)

Floating IPs are managed via `vm.py` CLI commands:

```bash
# List all floating IPs
python vm.py fip-list

# Create a floating IP for a VM (auto-detects zone and interface)
python vm.py fip-create <vm_id>
python vm.py fip-create <vm_id> --name my-public-ip

# Delete a floating IP
python vm.py fip-delete <fip_id>
```

You can also auto-create a floating IP during VM creation with `--floating-ip` (see below).

### Disk management

```bash
# List disks
python vm.py disks

# Create standalone disk
python vm.py disk-create --name data-disk --size 100 --zone-name ru.AZ-1 --disk-type-name SSD

# Attach / Detach
python vm.py disk-attach <disk_id> --vm-id <vm_id>
python vm.py disk-detach <disk_id> --vm-id <vm_id>

# Delete disk
python vm.py disk-delete <disk_id>
```

### Task tracking

Many operations are async. Track them:
```bash
python vm.py task <task_id>
```

## Typical workflow for creating a VM with public IP

1. Pick an availability zone: `python vm.py zones`
   - Available: `ru.AZ-1`, `ru.AZ-2`, `ru.AZ-3`
2. Pick a flavor: `python vm.py flavors`
   - Cheapest: `lowcost10-1-1` (1 vCPU, 1 GB RAM)
   - Common: `lowcost10-2-4` (2 vCPU, 4 GB RAM)
3. Pick an OS image: `python vm.py images`
   - Common: `ubuntu-22.04`, `Ubuntu-24.04`
4. Pick a disk type: `python vm.py disk-types`
   - Available: `SSD`, `HDD`
5. Create the VM with `--wait`, `--floating-ip`, and optionally `--wait-ssh`:
   ```bash
   python vm.py create --name my-vm \
     --flavor-name lowcost10-2-4 \
     --image-name ubuntu-22.04 \
     --zone-name ru.AZ-1 \
     --disk-size 20 --disk-type-name SSD \
     --login user1 --ssh-key-file ~/.ssh/id_ed25519.pub \
     --wait --floating-ip --wait-ssh
   ```
   This will create the VM, wait for it to reach `running`, auto-create a floating IP, and wait for SSH to become ready.
6. Connect: `python vm.py ssh <vm_id> -i ~/.ssh/id_ed25519`

**Shortcut with defaults:** If you omit `--flavor-name`, `--image-name`, `--zone-name`, `--disk-size`, `--disk-type-name`, the following defaults apply:
- Flavor: `lowcost10-1-1` (1 vCPU, 1 GB RAM)
- Image: `ubuntu-22.04`
- Zone: `ru.AZ-1`
- Disk: 10 GB SSD
So the minimal create command is:
```bash
python vm.py create --name my-vm --login user1 --ssh-key-file ~/.ssh/id_ed25519.pub --wait --floating-ip
```

## Important notes and gotchas

### VM creation

- **Authentication is required** for most Cloud.ru images — use either `--password` or `--ssh-key-file` (not both). They set `image_metadata`. Without auth the API returns `image_metadata_required` error. For agent use, **SSH key is preferred** — no password in command line.
- `--login` sets the username (default: `user1`).
- **`--disk-type-name`** (`SSD` or `HDD`) is required. Without it the API returns `disk_type_id or disk_type_name should be set` error.
- **Minimum boot disk size is ~8-10 GB** for Ubuntu images. Smaller values (e.g. 5 GB) return `vm_root_disk_too_small` error. Maximum disk size is 16384 GB.
- Zone names use dots: `ru.AZ-1`, `ru.AZ-2`, `ru.AZ-3` (not `ru-9a`).
- The API (v1.1) creates VMs asynchronously — the VM starts in `creating` state and transitions through `creating` -> `running` (typically 30-90 seconds).
- VM names must match pattern: `^[a-zA-Z][a-zA-Z0-9.\-_]*$` (1-64 chars, must start with a letter).

### Stop / Start

- `stop` sends `power_off` — VM transitions `running` -> `stopping` -> `stopped` (~15 seconds).
- `start` sends `power_on` — VM transitions `stopped` -> `starting` -> `running` (~30-40 seconds).
- `reboot` sends `reboot` — VM restarts without full shutdown.
- Resize (changing flavor) requires the VM to be `stopped` first.

### Deletion

- **If a floating IP is attached, delete it FIRST** before deleting the VM. Otherwise the API returns `floating_ip_can_not_be_detached_from_vm_in_current_state` (HTTP 422).
- Use `python vm.py delete <vm_id> --force` to auto-delete floating IPs before deleting the VM.
- Without `--force`, the CLI will warn about attached floating IPs and exit.
- VM deletion is asynchronous — the VM goes through `deleting` state before being fully removed.

### Floating IP (public IP)

- Floating IPs are created separately and attached to a VM's network interface.
- The floating IP's availability zone **must match** the VM's zone.
- One interface can have only one floating IP. Assigning another returns `interface_connected_another_floating_ip` error.
- After creating a floating IP, the VM is accessible at the assigned public IP via SSH: `ssh <login>@<public_ip>`.

### Network and cloud-init

- **Cloud-init takes 2-5 minutes** on lowcost VMs after the VM reaches `running` state. During this time:
  - SSH is not available (user/keys not yet configured)
  - **Outbound internet may not work** (network configuration is part of cloud-init)
  - `apt`, `curl`, `docker pull` will fail until cloud-init finishes
- On `lowcost10-1-1` VMs, cloud-init can take up to **5 minutes** due to dpkg locks and slow CPU.
- **Recommended:** after `--wait-ssh` succeeds, wait an additional **30-60 seconds** before running `apt update` or network-dependent commands. Or check with: `cloud-init status --wait`
- The `--wait-ssh` flag only checks that SSH port accepts connections. It does NOT guarantee that cloud-init has fully completed or that internet is available.

### SSH connectivity

- The `vm.py ssh` command auto-resolves the VM's floating IP. If no floating IP is assigned, it falls back to the private IP (only works from within the same network).
- Use `--ssh-key-file` when creating a VM and `-i <private_key>` when connecting with `vm.py ssh`.
- Use `--wait-ready` to retry SSH connections until cloud-init sets up sshd.
- The SSH commands disable strict host key checking (`StrictHostKeyChecking=no`) for convenience — VMs are ephemeral and IPs get reused.

### Disk sizes (tested)

| Size | Type | Result |
|------|------|--------|
| 5 GB | SSD | Error: `vm_root_disk_too_small` |
| 10 GB | SSD | OK (minimum for Ubuntu) |
| 50 GB | SSD | OK |
| 200 GB | HDD | OK |

### Flavors (pricing tiers)

- `lowcost10-*` — cheapest tier, 10% guaranteed vCPU share (e.g. `lowcost10-1-1` = 1 vCPU, 1 GB RAM)
- `low-*` — low tier (e.g. `low-1-2` = 1 vCPU, 2 GB RAM)
- `gen-*` — general purpose, 100% guaranteed vCPU (e.g. `gen-2-8` = 2 vCPU, 8 GB RAM)
- `gpa100-*` — GPU flavors with A100 GPUs
- `free-tier-*` — free tier (limited availability)

### API response format

- List endpoints return `{"items": [...], "total": N}`.
- Exception: `zones` and `disk-types` return a plain array `[...]`.
- VM create (v1.1) accepts and returns an array (batch create support).
- Many operations are async — use `python vm.py task <task_id>` to track progress.

## Cloud-init templates

Ready-to-use cloud-init templates are in `assets/`:

- **`cloud-init-docker.yaml`** — installs Docker + Docker Compose from official repo. Usage:
  ```bash
  python vm.py create --name docker-vm --cloud-init-file assets/cloud-init-docker.yaml \
    --login user1 --ssh-key-file ~/.ssh/id_ed25519.pub --wait --floating-ip --wait-ssh
  ```
  Note: Docker installation takes 3-5 minutes after cloud-init starts. After `--wait-ssh` succeeds, wait for cloud-init to finish:
  ```bash
  python vm.py ssh <vm_id> -i ~/.ssh/id_ed25519 -c "cloud-init status --wait"
  ```

## Building custom Python code

When the user needs custom code beyond what the script provides, use the patterns from `references/examples.md` to construct Python code with the `CloudruComputeClient` from `scripts/cloudru_client.py`.

For full API reference, see `references/api-reference.md`.

## Limitations

- Do not output secrets (CP_CONSOLE_KEY_ID, CP_CONSOLE_SECRET) to the user
- Do not run destructive commands (delete, stop) without user confirmation
- API base URL: `https://compute.api.cloud.ru`
