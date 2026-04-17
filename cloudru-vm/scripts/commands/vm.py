"""VM CRUD, power, floating IP, SSH/SCP commands."""

import base64
import os
import subprocess
import sys
import time

from helpers import build_client, check_response, get_env, print_json


# --- Helpers ---

def _resolve_zone_id(client, zone_name: str) -> str | None:
    """Resolve availability zone name (e.g. ru.AZ-1) to its UUID."""
    res = client.list_zones()
    if not res.is_success:
        return None
    data = res.json()
    zones = data if isinstance(data, list) else data.get("items", [])
    for z in zones:
        if z.get("name") == zone_name:
            return z.get("id")
    return None


def _get_vm_ips(vm: dict) -> tuple[str | None, str | None]:
    """Return (public_ip, private_ip) from VM data."""
    public_ip = None
    private_ip = None
    for iface in vm.get("interfaces", []):
        fip = iface.get("floating_ip")
        if fip and fip.get("ip_address"):
            public_ip = fip["ip_address"]
        ip = iface.get("ip_address")
        if ip and not private_ip:
            private_ip = ip
    return public_ip, private_ip


def _resolve_vm_ip(args):
    """Get the public (floating) or private IP of a VM."""
    client, _ = build_client()
    res = client.get_vm(args.vm_id)
    check_response(res, "getting VM")
    vm = res.json()
    public_ip, private_ip = _get_vm_ips(vm)
    if public_ip:
        return public_ip
    if private_ip:
        return private_ip
    print("Error: VM has no IP address", file=sys.stderr)
    sys.exit(1)


def _wait_vm_state(client, vm_id: str, target: str, timeout: int = 600) -> dict | None:
    """Poll VM until it reaches target state. Returns VM data or None on timeout."""
    deadline = time.time() + timeout
    last_state = None
    vm = None
    while time.time() < deadline:
        res = client.get_vm(vm_id)
        if not res.is_success:
            time.sleep(5)
            continue
        vm = res.json()
        state = vm.get("state", "?")
        if state != last_state:
            print(f"  State: {state}", file=sys.stderr)
            last_state = state
        if state == target:
            return vm
        if state.startswith("error"):
            print(f"Error: VM entered state '{state}'", file=sys.stderr)
            return None
        time.sleep(5)
    print(f"Warning: timed out after {timeout}s waiting for '{target}' (last: {last_state})", file=sys.stderr)
    # Return latest VM data so the chain (floating-ip, wait-ssh) can still try
    return vm


# --- List ---

def cmd_list(args):
    client, project_id = build_client()
    params = {}
    if args.limit:
        params["limit"] = args.limit
    if args.offset:
        params["offset"] = args.offset
    if args.state:
        params["state"] = args.state
    res = client.list_vms(project_id, **params)
    check_response(res, "listing VMs")
    data = res.json()
    print(f"Total: {data.get('total', '?')}")
    for vm in data.get("items", []):
        flavor = vm.get("flavor", {})
        image = vm.get("image", {})
        public_ip, private_ip = _get_vm_ips(vm)
        ip_str = public_ip or private_ip or "-"
        print(
            f"  {vm['id']} | {vm['name']:<25} | {vm.get('state', '?'):<12} "
            f"| {ip_str:<15} "
            f"| {flavor.get('name', '?')} ({flavor.get('cpu', '?')}cpu/{flavor.get('ram', '?')}GB) "
            f"| {image.get('name', '?')}"
        )


# --- Get ---

def cmd_get(args):
    client, _ = build_client()
    res = client.get_vm(args.vm_id)
    check_response(res, "getting VM")
    vm = res.json()

    # --json flag: output raw JSON
    if getattr(args, "json", False):
        print_json(vm)
        return

    # Compact summary
    print(f"Name:       {vm.get('name', '?')}")
    print(f"ID:         {vm.get('id', '?')}")
    print(f"State:      {vm.get('state', '?')}")

    flavor = vm.get("flavor", {})
    print(f"Flavor:     {flavor.get('name', '?')} ({flavor.get('cpu', '?')} vCPU, {flavor.get('ram', '?')} GB RAM)")

    image = vm.get("image", {})
    print(f"Image:      {image.get('name', '?')}")

    zone = vm.get("availability_zone", {})
    print(f"Zone:       {zone.get('name', '?')}")

    public_ip, private_ip = _get_vm_ips(vm)
    ips = []
    if public_ip:
        ips.append(f"{public_ip} (public)")
    if private_ip:
        ips.append(f"{private_ip} (private)")
    print(f"IPs:        {', '.join(ips) if ips else '-'}")

    disks = vm.get("disks", [])
    if disks:
        disk_strs = []
        for d in disks:
            dtype = d.get("disk_type", {}).get("name", d.get("disk_type_name", "?"))
            disk_strs.append(f"{d.get('name', '?')} ({d.get('size', '?')} GB, {dtype})")
        print(f"Disks:      {'; '.join(disk_strs)}")
    else:
        print("Disks:      -")

    sgs = []
    for iface in vm.get("interfaces", []):
        for sg in iface.get("security_groups", []):
            sg_name = sg.get("name", sg.get("id", "?"))
            if sg_name not in sgs:
                sgs.append(sg_name)
    print(f"Sec groups: {', '.join(sgs) if sgs else '-'}")

    print(f"Created:    {vm.get('created_at', '?')}")


# --- Create ---

DEFAULT_FLAVOR = "lowcost10-1-1"
DEFAULT_IMAGE = "ubuntu-22.04"
DEFAULT_ZONE = "ru.AZ-1"
DEFAULT_DISK_TYPE = "SSD"
DEFAULT_DISK_SIZE = 10


def cmd_create(args):
    client, project_id = build_client()

    payload = {
        "project_id": project_id,
        "name": args.name,
    }

    payload["flavor_name"] = args.flavor_name or (args.flavor_id and None) or DEFAULT_FLAVOR
    if args.flavor_id:
        payload.pop("flavor_name", None)
        payload["flavor_id"] = args.flavor_id

    payload["image_name"] = args.image_name or (args.image_id and None) or DEFAULT_IMAGE
    if args.image_id:
        payload.pop("image_name", None)
        payload["image_id"] = args.image_id

    payload["availability_zone_name"] = args.zone_name or (args.zone_id and None) or DEFAULT_ZONE
    if args.zone_id:
        payload.pop("availability_zone_name", None)
        payload["availability_zone_id"] = args.zone_id

    if args.description:
        payload["description"] = args.description

    if args.cloud_init:
        payload["cloud_init"] = base64.b64encode(args.cloud_init.encode()).decode()
    elif args.cloud_init_file:
        path = os.path.expanduser(args.cloud_init_file)
        with open(path, "rb") as f:
            payload["cloud_init"] = base64.b64encode(f.read()).decode()

    # Disks
    disk_name = args.disk_name or f"{args.name}-boot"
    disk_size = args.disk_size or DEFAULT_DISK_SIZE
    disk_item = {"name": disk_name, "size": disk_size}
    disk_type = args.disk_type_name or (args.disk_type_id and None) or DEFAULT_DISK_TYPE
    if args.disk_type_id:
        disk_item["disk_type_id"] = args.disk_type_id
    else:
        disk_item["disk_type_name"] = disk_type
    payload["disks"] = [disk_item]

    # Interfaces
    if args.subnet_id:
        payload["interfaces"] = [{"subnet_id": args.subnet_id}]
    elif args.subnet_name:
        payload["interfaces"] = [{"subnet_name": args.subnet_name}]

    if args.security_group_id:
        if "interfaces" in payload:
            payload["interfaces"][0]["security_groups"] = [{"id": args.security_group_id}]

    # Image metadata (login, password/ssh-key)
    if args.login or args.password or args.ssh_key or args.ssh_key_file:
        image_meta = {}
        image_meta["name"] = args.login or "user1"
        image_meta["hostname"] = args.name
        ssh_key = None
        if args.ssh_key:
            ssh_key = args.ssh_key
        elif args.ssh_key_file:
            path = os.path.expanduser(args.ssh_key_file)
            if not os.path.isfile(path):
                print(
                    f"Error: SSH key file not found: {path}\n"
                    f"Use --password instead, or generate a key with: ssh-keygen -t ed25519",
                    file=sys.stderr,
                )
                sys.exit(1)
            with open(path) as f:
                ssh_key = f.read().strip()
        if ssh_key:
            image_meta["public_key"] = ssh_key
        elif args.password:
            image_meta["linux_password"] = args.password
        payload["image_metadata"] = image_meta

    zone_name = payload.get("availability_zone_name", args.zone_name or DEFAULT_ZONE)

    print(f"Creating VM '{args.name}' (flavor={payload.get('flavor_name', payload.get('flavor_id'))}, "
          f"image={payload.get('image_name', payload.get('image_id'))}, zone={zone_name}, "
          f"disk={disk_size}GB {disk_type})")

    res = client.create_vm(payload)
    check_response(res, "creating VM")
    data = res.json()

    # v1.1 returns array
    vm_id = None
    if isinstance(data, list):
        for vm in data:
            vm_id = vm.get("id")
            print(f"Created VM: {vm_id}")
            task_id = vm.get("task_id")
            if task_id:
                print(f"Task ID: {task_id}")
    else:
        vm_id = data.get("id")
        print(f"Created VM: {vm_id}")

    if not vm_id:
        return

    # --wait: poll until running
    if args.wait and vm_id:
        wait_timeout = getattr(args, "wait_timeout", 600) or 600
        print(f"Waiting for VM to become running (timeout: {wait_timeout}s)...")
        vm = _wait_vm_state(client, vm_id, "running", timeout=wait_timeout)
        if vm and vm.get("state") == "running":
            public_ip, private_ip = _get_vm_ips(vm)
            print(f"VM is running! (private IP: {private_ip or '?'})")
        else:
            # Timeout — re-fetch to get latest state for the chain
            print("Timeout reached, but continuing with --floating-ip/--wait-ssh if requested...")
            r = client.get_vm(vm_id)
            vm = r.json() if r.is_success else {}

        # --floating-ip: auto-create floating IP (try even after timeout — VM may be running by now)
        if args.floating_ip and vm:
            _auto_create_fip(client, project_id, vm_id, vm, zone_name)

        # --wait-ssh: retry SSH until cloud-init is done
        if args.wait_ssh:
            _wait_ssh_ready(args, vm_id, timeout=args.wait_ssh_timeout or 300)


def _auto_create_fip(client, project_id, vm_id, vm, zone_name):
    """Create a floating IP and attach to the VM's first interface."""
    interfaces = vm.get("interfaces", [])
    if not interfaces:
        print("Warning: VM has no interfaces, cannot create floating IP", file=sys.stderr)
        return
    interface_id = interfaces[0].get("id")
    if not interface_id:
        print("Warning: VM interface has no ID", file=sys.stderr)
        return

    zone_id = _resolve_zone_id(client, zone_name)
    if not zone_id:
        print(f"Warning: could not resolve zone '{zone_name}' to ID", file=sys.stderr)
        return

    fip_payload = {
        "name": f"fip-{vm.get('name', vm_id)[:50]}",
        "project_id": project_id,
        "availability_zone_id": zone_id,
        "interface_id": interface_id,
    }
    res = client.create_floating_ip(fip_payload)
    if res.is_success:
        fip = res.json()
        print(f"Floating IP: {fip.get('ip_address')} (id: {fip.get('id')})")
    else:
        print(f"Warning: floating IP creation failed: {res.status_code} {res.text}", file=sys.stderr)


def _wait_ssh_ready(args, vm_id, timeout=300):
    """Retry SSH connection until it succeeds (cloud-init done)."""
    host = args.ip if hasattr(args, 'ip') and args.ip else _resolve_vm_ip(type('A', (), {'vm_id': vm_id})())
    user = args.login or "user1"
    key_args = ["-i", args.ssh_key_file.replace(".pub", "")] if args.ssh_key_file else []
    if args.key_file if hasattr(args, 'key_file') else None:
        key_args = ["-i", args.key_file]

    print(f"Waiting for SSH to become ready ({timeout}s timeout)...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        ssh_cmd = [
            "ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
        ] + key_args + [f"{user}@{host}", "echo ready"]
        result = subprocess.run(ssh_cmd, capture_output=True, text=True)
        if result.returncode == 0 and "ready" in result.stdout:
            print("SSH is ready!")
            return
        time.sleep(10)
    print(f"Warning: SSH not ready after {timeout}s (cloud-init may still be running)", file=sys.stderr)


# --- Update, Delete, Power ---

def cmd_update(args):
    client, _ = build_client()
    payload = {}
    if args.name:
        payload["name"] = args.name
    if args.description is not None:
        payload["description"] = args.description
    if args.flavor_name:
        payload["flavor_name"] = args.flavor_name
    elif args.flavor_id:
        payload["flavor_id"] = args.flavor_id

    res = client.update_vm(args.vm_id, payload)
    check_response(res, "updating VM")
    print("Updated successfully")


def cmd_delete(args):
    client, _ = build_client()

    # Check for floating IPs on the VM
    res = client.get_vm(args.vm_id)
    check_response(res, "getting VM")
    vm = res.json()

    fip_ids = []
    for iface in vm.get("interfaces", []):
        fip = iface.get("floating_ip")
        if fip and fip.get("id"):
            fip_ids.append((fip["id"], fip.get("ip_address", "?")))

    if fip_ids and getattr(args, "force", False):
        # Auto-delete floating IPs first
        for fip_id, fip_ip in fip_ids:
            print(f"Deleting floating IP {fip_ip} ({fip_id})...")
            fip_res = client.delete_floating_ip(fip_id)
            if not fip_res.is_success:
                print(f"Warning: failed to delete floating IP {fip_id}: {fip_res.status_code}", file=sys.stderr)
            else:
                print(f"  Floating IP deleted")
        print("Waiting 3 seconds for floating IP cleanup...")
        time.sleep(3)
    elif fip_ids and not getattr(args, "force", False):
        fip_list = ", ".join(f"{ip} ({fid})" for fid, ip in fip_ids)
        print(f"Warning: VM has floating IPs: {fip_list}", file=sys.stderr)
        print("Use --force to auto-delete floating IPs before deleting the VM.", file=sys.stderr)
        sys.exit(1)

    res = client.delete_vm(args.vm_id)
    check_response(res, "deleting VM")
    print("Deleted successfully")


def cmd_start(args):
    client, _ = build_client()
    res = client.set_power(args.vm_id, "power_on")
    check_response(res, "starting VM")
    print("Start initiated")


def cmd_stop(args):
    client, _ = build_client()
    res = client.set_power(args.vm_id, "power_off")
    check_response(res, "stopping VM")
    print("Stop initiated")


def cmd_reboot(args):
    client, _ = build_client()
    res = client.set_power(args.vm_id, "reboot")
    check_response(res, "rebooting VM")
    print("Reboot initiated")


def cmd_vnc(args):
    client, _ = build_client()
    res = client.remote_console(args.vm_id, protocol=args.protocol or "vnc")
    check_response(res, "getting console URL")
    if not res.content:
        print(f"Error: empty response from console API (HTTP {res.status_code})", file=sys.stderr)
        sys.exit(1)
    data = res.json()
    print(f"Console URL: {data.get('url', data)}")


# --- Floating IP ---

def cmd_fip_list(args):
    client, project_id = build_client()
    res = client.list_floating_ips(project_id)
    check_response(res, "listing floating IPs")
    data = res.json()
    items = data.get("items", [])
    print(f"Floating IPs ({len(items)}):")
    for fip in items:
        iface = fip.get("interface_id", "-")
        print(f"  {fip['id']} | {fip.get('ip_address', '?'):<15} | {fip.get('name', ''):<30} | interface: {iface}")


def cmd_fip_create(args):
    client, project_id = build_client()

    # Resolve VM interface ID
    res = client.get_vm(args.vm_id)
    check_response(res, "getting VM")
    vm = res.json()
    interfaces = vm.get("interfaces", [])
    if not interfaces:
        print("Error: VM has no network interfaces", file=sys.stderr)
        sys.exit(1)
    interface_id = interfaces[0]["id"]
    vm_zone = vm.get("availability_zone", {}).get("name", args.zone_name or DEFAULT_ZONE)

    fip_name = args.name or f"fip-{vm.get('name', args.vm_id)[:50]}"

    zone_name = args.zone_name or vm_zone
    zone_id = _resolve_zone_id(client, zone_name)
    if not zone_id:
        print(f"Error: could not resolve zone '{zone_name}' to ID", file=sys.stderr)
        sys.exit(1)

    payload = {
        "name": fip_name,
        "project_id": project_id,
        "availability_zone_id": zone_id,
        "interface_id": interface_id,
    }
    res = client.create_floating_ip(payload)
    check_response(res, "creating floating IP")
    fip = res.json()
    print(f"Created floating IP: {fip.get('ip_address')} (id: {fip.get('id')})")


def cmd_fip_delete(args):
    client, _ = build_client()
    res = client.delete_floating_ip(args.fip_id)
    check_response(res, "deleting floating IP")
    print("Deleted successfully")


# --- SSH / SCP ---

def cmd_ssh(args):
    """Execute a command on VM via SSH."""
    if args.ip:
        host = args.ip
    else:
        host = _resolve_vm_ip(args)

    user = args.login or "user1"

    ssh_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
    ]

    if args.key_file:
        ssh_cmd += ["-i", args.key_file]

    ssh_cmd.append(f"{user}@{host}")

    if args.wait_ready:
        timeout = args.wait_ready
        print(f"Waiting for SSH to become ready ({timeout}s timeout)...")
        deadline = time.time() + timeout
        while time.time() < deadline:
            test_cmd = ssh_cmd + ["-o", "ConnectTimeout=5", "-o", "BatchMode=yes", "echo ready"]
            result = subprocess.run(test_cmd, capture_output=True, text=True)
            if result.returncode == 0 and "ready" in result.stdout:
                print("SSH is ready!")
                break
            time.sleep(10)
        else:
            print(f"Warning: SSH not ready after {timeout}s", file=sys.stderr)

    if args.remote_cmd:
        ssh_cmd.append(args.remote_cmd)
        result = subprocess.run(ssh_cmd, capture_output=False)
        sys.exit(result.returncode)
    else:
        os.execvp("ssh", ssh_cmd)


def cmd_scp(args):
    """Copy files to/from VM via SCP."""
    if args.ip:
        host = args.ip
    else:
        host = _resolve_vm_ip(args)

    user = args.login or "user1"

    scp_cmd = [
        "scp",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
    ]

    if args.key_file:
        scp_cmd += ["-i", args.key_file]

    if args.recursive:
        scp_cmd.append("-r")

    remote_prefix = f"{user}@{host}:"
    if args.direction == "upload":
        scp_cmd += [args.local_path, f"{remote_prefix}{args.remote_path}"]
    else:
        scp_cmd += [f"{remote_prefix}{args.remote_path}", args.local_path]

    result = subprocess.run(scp_cmd, capture_output=False)
    sys.exit(result.returncode)
