"""Command registry for Cloud.ru VM CLI."""

from commands.vm import (
    cmd_list, cmd_get, cmd_create, cmd_update, cmd_delete,
    cmd_start, cmd_stop, cmd_reboot, cmd_vnc, cmd_ssh, cmd_scp,
    cmd_fip_list, cmd_fip_create, cmd_fip_delete,
)
from commands.infra import cmd_flavors, cmd_images, cmd_subnets, cmd_zones, cmd_disk_types, cmd_security_groups
from commands.disks import cmd_disks, cmd_disk_create, cmd_disk_delete, cmd_disk_attach, cmd_disk_detach
from commands.security import cmd_sg_create, cmd_sg_delete, cmd_sg_rules, cmd_sg_rule_add, cmd_sg_rule_delete
from commands.tasks import cmd_task

COMMANDS = {
    "list": cmd_list,
    "get": cmd_get,
    "create": cmd_create,
    "update": cmd_update,
    "delete": cmd_delete,
    "start": cmd_start,
    "stop": cmd_stop,
    "reboot": cmd_reboot,
    "vnc": cmd_vnc,
    "ssh": cmd_ssh,
    "scp": cmd_scp,
    "fip-list": cmd_fip_list,
    "fip-create": cmd_fip_create,
    "fip-delete": cmd_fip_delete,
    "flavors": cmd_flavors,
    "images": cmd_images,
    "subnets": cmd_subnets,
    "zones": cmd_zones,
    "disk-types": cmd_disk_types,
    "security-groups": cmd_security_groups,
    "sg-create": cmd_sg_create,
    "sg-delete": cmd_sg_delete,
    "sg-rules": cmd_sg_rules,
    "sg-rule-add": cmd_sg_rule_add,
    "sg-rule-delete": cmd_sg_rule_delete,
    "disks": cmd_disks,
    "disk-create": cmd_disk_create,
    "disk-delete": cmd_disk_delete,
    "disk-attach": cmd_disk_attach,
    "disk-detach": cmd_disk_detach,
    "task": cmd_task,
}
