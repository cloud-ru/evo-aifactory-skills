#!/usr/bin/env python3
"""Cloud.ru VM CLI — create and manage virtual machines.

Usage:
    python vm.py <command> [options]

Commands:
    list            List virtual machines
    get             Get VM details
    create          Create a VM (sensible defaults: ubuntu-22.04, ru.AZ-1, 10GB SSD, lowcost10-1-1)
    update          Update a VM
    delete          Delete a VM
    start           Start a VM
    stop            Stop a VM
    reboot          Reboot a VM
    vnc             Get remote console URL
    ssh             Execute command on VM via SSH (--wait-ready to retry until cloud-init done)
    scp             Copy files to/from VM
    fip-list        List floating IPs (public IPs)
    fip-create      Create floating IP for a VM
    fip-delete      Delete a floating IP
    flavors         List available flavors (CPU/RAM configs)
    images          List available OS images
    subnets         List available subnets
    zones           List availability zones
    disk-types      List disk types
    security-groups List security groups
    disks           List disks
    disk-create     Create a disk
    disk-delete     Delete a disk
    disk-attach     Attach a disk to VM
    disk-detach     Detach a disk from VM
    task            Get async task status

Environment variables required:
    CP_CONSOLE_KEY_ID   — Cloud.ru service account key ID
    CP_CONSOLE_SECRET   — Cloud.ru service account secret
    PROJECT_ID          — Cloud.ru project UUID
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse

from commands import COMMANDS


def build_parser():
    parser = argparse.ArgumentParser(
        description="Cloud.ru VM CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- VM commands ---

    p_list = subparsers.add_parser("list", help="List VMs (shows IP addresses)")
    p_list.add_argument("--limit", type=int, help="Max results")
    p_list.add_argument("--offset", type=int, help="Offset")
    p_list.add_argument("--state", help="Filter by state (running, stopped, etc.)")

    p_get = subparsers.add_parser("get", help="Get VM details")
    p_get.add_argument("vm_id", help="VM UUID")
    p_get.add_argument("--json", action="store_true", help="Output raw JSON instead of compact summary")

    p_create = subparsers.add_parser("create", help="Create a VM (defaults: ubuntu-22.04, ru.AZ-1, 10GB SSD, lowcost10-1-1)")
    p_create.add_argument("--name", required=True, help="VM name (alphanumeric, starts with letter)")
    p_create.add_argument("--flavor-name", help="Flavor name (default: lowcost10-1-1)")
    p_create.add_argument("--flavor-id", help="Flavor UUID")
    p_create.add_argument("--image-name", help="OS image name (default: ubuntu-22.04)")
    p_create.add_argument("--image-id", help="OS image UUID")
    p_create.add_argument("--zone-name", help="Availability zone (default: ru.AZ-1)")
    p_create.add_argument("--zone-id", help="Availability zone UUID")
    p_create.add_argument("--description", help="VM description")
    p_create.add_argument("--disk-name", help="Boot disk name (default: <vm-name>-boot)")
    p_create.add_argument("--disk-size", type=int, help="Boot disk size in GB (default: 10)")
    p_create.add_argument("--disk-type-name", help="Disk type name (default: SSD)")
    p_create.add_argument("--disk-type-id", help="Disk type UUID")
    p_create.add_argument("--subnet-id", help="Subnet UUID")
    p_create.add_argument("--subnet-name", help="Subnet name")
    p_create.add_argument("--security-group-id", help="Security group UUID")
    p_create.add_argument("--login", help="VM user login (default: user1)")
    p_create.add_argument("--password", help="VM user password (auth option 1)")
    p_create.add_argument("--ssh-key", help="SSH public key string (auth option 2)")
    p_create.add_argument("--ssh-key-file", help="Path to SSH public key file (e.g. ~/.ssh/id_ed25519.pub)")
    p_create.add_argument("--cloud-init", help="Cloud-init script (inline)")
    p_create.add_argument("--cloud-init-file", help="Path to cloud-init file")
    p_create.add_argument("--wait", action="store_true", help="Wait for VM to reach 'running' state")
    p_create.add_argument("--wait-timeout", type=int, default=600, help="Max seconds to wait for running (default: 600)")
    p_create.add_argument("--floating-ip", action="store_true", help="Auto-create floating IP after VM is running (implies --wait)")
    p_create.add_argument("--wait-ssh", action="store_true", help="After --wait, also wait for SSH to become ready (cloud-init)")
    p_create.add_argument("--wait-ssh-timeout", type=int, default=300, help="SSH readiness timeout in seconds (default: 300)")
    p_create.add_argument("--key-file", help="SSH private key for --wait-ssh check")

    p_update = subparsers.add_parser("update", help="Update a VM")
    p_update.add_argument("vm_id", help="VM UUID")
    p_update.add_argument("--name", help="New name")
    p_update.add_argument("--description", help="New description")
    p_update.add_argument("--flavor-name", help="New flavor name (requires stopped VM)")
    p_update.add_argument("--flavor-id", help="New flavor UUID (requires stopped VM)")

    p_delete = subparsers.add_parser("delete", help="Delete a VM")
    p_delete.add_argument("vm_id", help="VM UUID")
    p_delete.add_argument("--force", action="store_true", help="Auto-delete floating IPs before deleting the VM")

    p_start = subparsers.add_parser("start", help="Start a VM")
    p_start.add_argument("vm_id", help="VM UUID")

    p_stop = subparsers.add_parser("stop", help="Stop a VM")
    p_stop.add_argument("vm_id", help="VM UUID")

    p_reboot = subparsers.add_parser("reboot", help="Reboot a VM")
    p_reboot.add_argument("vm_id", help="VM UUID")

    p_vnc = subparsers.add_parser("vnc", help="Get remote console URL")
    p_vnc.add_argument("vm_id", help="VM UUID")
    p_vnc.add_argument("--protocol", choices=["vnc", "serial"], default="vnc", help="Console type")

    # --- SSH/SCP commands ---

    p_ssh = subparsers.add_parser("ssh", help="Execute command on VM via SSH")
    p_ssh.add_argument("vm_id", help="VM UUID (used to resolve IP)")
    p_ssh.add_argument("--cmd", "-c", dest="remote_cmd", help="Command to execute (omit for interactive shell)")
    p_ssh.add_argument("--login", "-l", default="user1", help="SSH user (default: user1)")
    p_ssh.add_argument("--key-file", "-i", help="Path to SSH private key")
    p_ssh.add_argument("--ip", help="Use this IP instead of auto-resolving from VM")
    p_ssh.add_argument("--wait-ready", type=int, nargs="?", const=300, default=0,
                        help="Retry SSH until ready (cloud-init done). Optional: timeout in seconds (default: 300)")

    p_scp = subparsers.add_parser("scp", help="Copy files to/from VM via SCP")
    p_scp.add_argument("vm_id", help="VM UUID (used to resolve IP)")
    p_scp.add_argument("--direction", choices=["upload", "download"], default="upload", help="Transfer direction")
    p_scp.add_argument("--local-path", required=True, help="Local file/dir path")
    p_scp.add_argument("--remote-path", required=True, help="Remote file/dir path")
    p_scp.add_argument("--login", "-l", default="user1", help="SSH user (default: user1)")
    p_scp.add_argument("--key-file", "-i", help="Path to SSH private key")
    p_scp.add_argument("--ip", help="Use this IP instead of auto-resolving from VM")
    p_scp.add_argument("--recursive", "-r", action="store_true", help="Copy directories recursively")

    # --- Floating IP commands ---

    subparsers.add_parser("fip-list", help="List floating IPs (public IPs)")

    p_fip_c = subparsers.add_parser("fip-create", help="Create floating IP for a VM")
    p_fip_c.add_argument("vm_id", help="VM UUID")
    p_fip_c.add_argument("--name", help="Floating IP name (default: fip-<vm-name>)")
    p_fip_c.add_argument("--zone-name", help="Availability zone (auto-detected from VM if omitted)")

    p_fip_d = subparsers.add_parser("fip-delete", help="Delete a floating IP")
    p_fip_d.add_argument("fip_id", help="Floating IP UUID")

    # --- Infrastructure commands ---

    p_flavors = subparsers.add_parser("flavors", help="List flavors")
    p_flavors.add_argument("--limit", type=int, help="Max results")
    p_flavors.add_argument("--cpu", type=int, help="Filter by CPU count")
    p_flavors.add_argument("--ram", type=int, help="Filter by RAM (GB)")
    p_flavors.add_argument("--name", help="Filter by name")

    p_images = subparsers.add_parser("images", help="List OS images")
    p_images.add_argument("--limit", type=int, help="Max results")
    p_images.add_argument("--name", help="Filter by name")

    p_subnets = subparsers.add_parser("subnets", help="List subnets")
    p_subnets.add_argument("--limit", type=int, help="Max results")

    subparsers.add_parser("zones", help="List availability zones")
    subparsers.add_parser("disk-types", help="List disk types")

    p_sg = subparsers.add_parser("security-groups", help="List security groups")
    p_sg.add_argument("--limit", type=int, help="Max results")

    # --- Security group management ---

    p_sgc = subparsers.add_parser("sg-create", help="Create a security group")
    p_sgc.add_argument("--name", required=True, help="Security group name")
    p_sgc.add_argument("--zone-name", help="Availability zone name")
    p_sgc.add_argument("--zone-id", help="Availability zone UUID")
    p_sgc.add_argument("--description", help="Description")
    p_sgc.add_argument("--open-ports", nargs="+", help="Ports to open immediately (e.g. 22 80 443 8080-8090)")

    p_sgd = subparsers.add_parser("sg-delete", help="Delete a security group")
    p_sgd.add_argument("sg_id", help="Security group UUID")

    p_sgr = subparsers.add_parser("sg-rules", help="List rules of a security group")
    p_sgr.add_argument("sg_id", help="Security group UUID")

    p_sra = subparsers.add_parser("sg-rule-add", help="Add a rule (open port)")
    p_sra.add_argument("sg_id", help="Security group UUID")
    p_sra.add_argument("--ports", required=True, help="Port or range (e.g. 22, 8080-8090, 1-65535)")
    p_sra.add_argument("--protocol", default="tcp", choices=["tcp", "udp", "icmp", "any"], help="IP protocol (default: tcp)")
    p_sra.add_argument("--direction", default="ingress", choices=["ingress", "egress"], help="Traffic direction (default: ingress)")
    p_sra.add_argument("--remote-ip", default="0.0.0.0/0", help="Source CIDR (default: 0.0.0.0/0 = any)")
    p_sra.add_argument("--ether-type", default="IPv4", choices=["IPv4", "IPv6"], help="Ether type (default: IPv4)")
    p_sra.add_argument("--description", help="Rule description")

    p_srd = subparsers.add_parser("sg-rule-delete", help="Delete a rule (close port)")
    p_srd.add_argument("sg_id", help="Security group UUID")
    p_srd.add_argument("rule_id", help="Rule UUID")

    # --- Disk commands ---

    p_disks = subparsers.add_parser("disks", help="List disks")
    p_disks.add_argument("--limit", type=int, help="Max results")

    p_dc = subparsers.add_parser("disk-create", help="Create a disk")
    p_dc.add_argument("--name", required=True, help="Disk name")
    p_dc.add_argument("--size", type=int, required=True, help="Size in GB")
    p_dc.add_argument("--zone-name", help="Availability zone name")
    p_dc.add_argument("--zone-id", help="Availability zone UUID")
    p_dc.add_argument("--disk-type-name", help="Disk type name")
    p_dc.add_argument("--disk-type-id", help="Disk type UUID")

    p_dd = subparsers.add_parser("disk-delete", help="Delete a disk")
    p_dd.add_argument("disk_id", help="Disk UUID")

    p_da = subparsers.add_parser("disk-attach", help="Attach disk to VM")
    p_da.add_argument("disk_id", help="Disk UUID")
    p_da.add_argument("--vm-id", required=True, help="VM UUID")

    p_dt = subparsers.add_parser("disk-detach", help="Detach disk from VM")
    p_dt.add_argument("disk_id", help="Disk UUID")
    p_dt.add_argument("--vm-id", required=True, help="VM UUID")

    # --- Task commands ---

    p_task = subparsers.add_parser("task", help="Get async task status")
    p_task.add_argument("task_id", help="Task UUID")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # --floating-ip implies --wait
    if hasattr(args, 'floating_ip') and args.floating_ip:
        args.wait = True

    COMMANDS[args.command](args)


if __name__ == "__main__":
    main()
