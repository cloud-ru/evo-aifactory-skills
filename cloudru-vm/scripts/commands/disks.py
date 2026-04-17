"""Disk management commands."""

from helpers import build_client, check_response


def cmd_disks(args):
    client, project_id = build_client()
    params = {}
    if args.limit:
        params["limit"] = args.limit
    res = client.list_disks(project_id, **params)
    check_response(res, "listing disks")
    data = res.json()
    print(f"Disks ({data.get('total', '?')} total):\n")
    for d in data.get("items", []):
        attached = f" -> VM {d['vm_id']}" if d.get("vm_id") else " (detached)"
        dt = d.get("disk_type", {})
        print(
            f"  {d['id']} | {d['name']:<25} | {d.get('size_gb', '?')}GB "
            f"| {dt.get('name', '?')}{attached}"
        )


def cmd_disk_create(args):
    client, project_id = build_client()
    payload = {
        "project_id": project_id,
        "name": args.name,
        "size": args.size,
    }
    if args.zone_name:
        payload["availability_zone_name"] = args.zone_name
    elif args.zone_id:
        payload["availability_zone_id"] = args.zone_id
    disk_type_name = args.disk_type_name or (None if args.disk_type_id else "SSD")
    if disk_type_name:
        payload["disk_type_name"] = disk_type_name
    elif args.disk_type_id:
        payload["disk_type_id"] = args.disk_type_id

    res = client.create_disk(payload)
    check_response(res, "creating disk")
    data = res.json()
    print(f"Created disk: {data.get('id', data)}")


def cmd_disk_delete(args):
    client, _ = build_client()
    res = client.delete_disk(args.disk_id)
    check_response(res, "deleting disk")
    print("Deleted successfully")


def cmd_disk_attach(args):
    client, _ = build_client()
    payload = {"vm_id": args.vm_id}
    res = client.attach_disk(args.disk_id, payload)
    check_response(res, "attaching disk")
    print("Attached successfully")


def cmd_disk_detach(args):
    client, _ = build_client()
    payload = {"vm_id": args.vm_id}
    res = client.detach_disk(args.disk_id, payload)
    check_response(res, "detaching disk")
    print("Detached successfully")
