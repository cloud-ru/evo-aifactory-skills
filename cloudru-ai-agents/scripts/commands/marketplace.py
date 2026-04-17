"""CLI handlers for `marketplace` subcommand."""

from helpers import build_client, check_response, print_json


def cmd_list_agents(args):
    client, project_id = build_client()
    sort = getattr(args, "sort_type", None) or "SORT_TYPE_POPULARITY_DESC"
    resp = client.list_marketplace_agents(project_id, search=args.search,
                                           limit=args.limit, offset=args.offset, sort=sort)
    check_response(resp, "listing marketplace agents")
    print_json(resp.json())


def cmd_get_agent(args):
    client, project_id = build_client()
    resp = client.get_marketplace_agent(project_id, args.card_id)
    check_response(resp, f"getting marketplace agent {args.card_id}")
    print_json(resp.json())


def cmd_list_mcp(args):
    client, project_id = build_client()
    sort = getattr(args, "sort_type", None) or "SORT_TYPE_POPULARITY_DESC"
    resp = client.list_marketplace_mcp_servers(project_id, search=args.search,
                                                limit=args.limit, offset=args.offset, sort=sort)
    check_response(resp, "listing marketplace mcp-servers")
    print_json(resp.json())


def cmd_get_mcp(args):
    client, project_id = build_client()
    resp = client.get_marketplace_mcp_server(project_id, args.card_id)
    check_response(resp, f"getting marketplace mcp-server {args.card_id}")
    print_json(resp.json())


def cmd_list_prompts(args):
    client, project_id = build_client()
    sort = getattr(args, "sort_type", None) or "SORT_TYPE_POPULARITY_DESC"
    resp = client.list_marketplace_prompts(project_id, search=args.search,
                                            limit=args.limit, offset=args.offset, sort=sort)
    check_response(resp, "listing marketplace prompts")
    print_json(resp.json())


def cmd_get_prompt(args):
    client, project_id = build_client()
    resp = client.get_marketplace_prompt(project_id, args.card_id)
    check_response(resp, f"getting marketplace prompt {args.card_id}")
    print_json(resp.json())


def cmd_list_skills(args):
    client, _ = build_client()
    resp = client.list_marketplace_skills(search=args.search, limit=args.limit, offset=args.offset)
    check_response(resp, "listing marketplace skills")
    print_json(resp.json())


def cmd_get_skill(args):
    client, _ = build_client()
    resp = client.get_marketplace_skill(args.card_id)
    check_response(resp, f"getting marketplace skill {args.card_id}")
    print_json(resp.json())


def cmd_get_snippet(args):
    client, _ = build_client()
    resp = client.get_marketplace_snippet(args.card_id)
    check_response(resp, f"getting marketplace snippet {args.card_id}")
    print_json(resp.json())


def cmd_list_snippets(args):
    client, _ = build_client()
    block_styles = args.block_styles.split(",") if args.block_styles else None
    resp = client.list_marketplace_snippets(search=args.search, limit=args.limit,
                                             offset=args.offset, block_styles=block_styles)
    check_response(resp, "listing marketplace snippets")
    print_json(resp.json())


COMMANDS = {
    "marketplace.list-agents": cmd_list_agents,
    "marketplace.get-agent": cmd_get_agent,
    "marketplace.list-mcp": cmd_list_mcp,
    "marketplace.get-mcp": cmd_get_mcp,
    "marketplace.list-prompts": cmd_list_prompts,
    "marketplace.get-prompt": cmd_get_prompt,
    "marketplace.list-skills": cmd_list_skills,
    "marketplace.get-skill": cmd_get_skill,
    "marketplace.list-snippets": cmd_list_snippets,
    "marketplace.get-snippet": cmd_get_snippet,
}
