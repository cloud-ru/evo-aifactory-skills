"""Security group and rule management commands."""

import sys

from helpers import build_client, check_response, print_json


def cmd_sg_create(args):
    client, project_id = build_client()
    payload = {
        "project_id": project_id,
        "name": args.name,
    }
    if args.zone_name:
        payload["availability_zone_name"] = args.zone_name
    elif args.zone_id:
        payload["availability_zone_id"] = args.zone_id
    if args.description:
        payload["description"] = args.description

    # Create with initial rules if provided
    rules = []
    if args.open_ports:
        for port_spec in args.open_ports:
            rules.append({
                "direction": "ingress",
                "ether_type": "IPv4",
                "ip_protocol": "tcp",
                "port_range": port_spec,
                "remote_ip_prefix": "0.0.0.0/0",
            })
    if rules:
        payload["security_group_rules"] = rules

    res = client.create_security_group(payload)
    check_response(res, "creating security group")
    data = res.json()
    print(f"Created security group: {data['id']} ({data['name']})")
    for rule in data.get("rules", []):
        print(f"  Rule {rule['id']}: {rule['direction']} {rule['ip_protocol']} {rule['port_range']} {rule.get('remote_ip_prefix', '')}")


def cmd_sg_delete(args):
    client, _ = build_client()
    res = client.delete_security_group(args.sg_id)
    check_response(res, "deleting security group")
    print("Deleted successfully")


def cmd_sg_rules(args):
    client, _ = build_client()
    res = client.list_sg_rules(args.sg_id)
    check_response(res, "listing rules")
    data = res.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    if not items:
        print("No rules")
        return
    for r in items:
        remote = r.get("remote_ip_prefix", "")
        remote_sg = r.get("remote_security_group")
        if remote_sg:
            remote = f"sg:{remote_sg.get('name', remote_sg.get('id', ''))}"
        desc = f" ({r['description']})" if r.get("description") else ""
        print(
            f"  {r['id']} | {r['direction']:<7} | {r['ip_protocol']:<4} | "
            f"ports {r['port_range']:<11} | {r.get('ether_type', '?')} | "
            f"from {remote or 'any'}{desc}"
        )


def cmd_sg_rule_add(args):
    client, _ = build_client()
    payload = {
        "direction": args.direction,
        "ether_type": args.ether_type or "IPv4",
        "ip_protocol": args.protocol,
        "port_range": args.ports,
    }
    if args.remote_ip:
        payload["remote_ip_prefix"] = args.remote_ip
    if args.description:
        payload["description"] = args.description

    res = client.create_sg_rule(args.sg_id, payload)
    check_response(res, "adding rule")
    data = res.json()
    print(f"Added rule: {data['id']} ({data['direction']} {data['ip_protocol']} {data['port_range']})")


def cmd_sg_rule_delete(args):
    client, _ = build_client()
    res = client.delete_sg_rule(args.sg_id, args.rule_id)
    check_response(res, "deleting rule")
    print("Deleted successfully")
