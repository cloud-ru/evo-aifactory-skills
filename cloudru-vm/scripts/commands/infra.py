"""Infrastructure info commands: flavors, images, subnets, zones, disk-types, security-groups."""

from helpers import build_client, check_response


def cmd_flavors(args):
    client, project_id = build_client()
    params = {"project_id": project_id}
    if args.limit:
        params["limit"] = args.limit
    if args.cpu:
        params["cpu"] = args.cpu
    if args.ram:
        params["ram"] = args.ram
    if args.name:
        params["name"] = args.name
    res = client.list_flavors(**params)
    check_response(res, "listing flavors")
    data = res.json()
    print(f"Flavors ({data.get('total', '?')} total):\n")
    for f in data.get("items", []):
        gpu_str = f" gpu={f['gpu']}" if f.get("gpu") else ""
        print(f"  {f['id']} | {f['name']:<25} | {f['cpu']}cpu {f['ram']}GB RAM{gpu_str}")


def cmd_images(args):
    client, project_id = build_client()
    params = {}
    if args.limit:
        params["limit"] = args.limit
    if args.name:
        params["name"] = args.name
    res = client.list_images(project_id, **params)
    check_response(res, "listing images")
    data = res.json()
    print(f"Images ({data.get('total', '?')} total):\n")
    for img in data.get("items", []):
        print(f"  {img['id']} | {img['name']:<40} | {img.get('os_type', '?')} | {img.get('size_gb', '?')}GB")


def cmd_subnets(args):
    client, project_id = build_client()
    params = {}
    if args.limit:
        params["limit"] = args.limit
    res = client.list_subnets(project_id, **params)
    check_response(res, "listing subnets")
    data = res.json()
    print(f"Subnets ({data.get('total', '?')} total):\n")
    for s in data.get("items", []):
        print(f"  {s['id']} | {s['name']:<30} | {s.get('cidr', '?')}")


def cmd_zones(args):
    client, _ = build_client()
    res = client.list_zones()
    check_response(res, "listing availability zones")
    data = res.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    for z in items:
        print(f"  {z['id']} | {z['name']}")


def cmd_disk_types(args):
    client, _ = build_client()
    res = client.list_disk_types()
    check_response(res, "listing disk types")
    data = res.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    for dt in items:
        ft = " [free-tier]" if dt.get("free_tier") else ""
        print(f"  {dt['id']} | {dt['name']}{ft}")


def cmd_security_groups(args):
    client, project_id = build_client()
    params = {}
    if args.limit:
        params["limit"] = args.limit
    res = client.list_security_groups(project_id, **params)
    check_response(res, "listing security groups")
    data = res.json()
    print(f"Security groups ({data.get('total', '?')} total):\n")
    for sg in data.get("items", []):
        rule_count = sg.get("rule_count", len(sg.get("rules", [])))
        # If API doesn't return rules in list, fetch them
        if rule_count == 0 and not sg.get("rules"):
            try:
                r = client.list_sg_rules(sg["id"])
                if r.is_success:
                    rd = r.json()
                    items = rd.get("items", rd) if isinstance(rd, dict) else rd
                    rule_count = len(items) if isinstance(items, list) else 0
            except Exception:
                pass
        print(f"  {sg['id']} | {sg['name']:<30} | rules: {rule_count}")
