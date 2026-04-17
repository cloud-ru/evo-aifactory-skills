#!/usr/bin/env python3
"""Cloud.ru AI Agents CLI.

Manage Agents, Agent Systems, MCP Servers on Cloud.ru AI Agents API.

Requires environment variables:
  CP_CONSOLE_KEY_ID    IAM access key ID
  CP_CONSOLE_SECRET    IAM access key secret
  PROJECT_ID           Cloud.ru project ID

Run `ai_agents.py <group> --help` to see subcommands.
"""

import argparse
import os
import sys

from commands import COMMANDS
from commands._shared import (add_common_scaling_flags, add_common_integration_flags,
                               add_environment_flags)


def _add_limit_offset(p):
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--offset", type=int, default=0)


def _add_config_source(p):
    p.add_argument("--config-json", help="Inline JSON body")
    p.add_argument("--config-file", help="Path to JSON file with body")


def _add_agent_option_flags(p):
    """Register high-level flags that mirror UI's Create Agent form.
    Used by `agents create`, `agents update`, `systems create`, `systems update`.
    """
    p.add_argument("--system-prompt", help="Inline system prompt text")
    p.add_argument("--system-prompt-file", help="Path to file with system prompt")
    p.add_argument("--model-name", help="FM model name (e.g. zai-org/GLM-4.7)")
    p.add_argument("--temperature", type=float, help="LLM temperature (0..2)")
    p.add_argument("--max-tokens", type=int, help="Max tokens per reply")
    p.add_argument("--thinking", choices=["off", "low", "medium", "high"],
                    help="Extended thinking mode")
    p.add_argument("--thinking-budget", type=int, help="Thinking token budget")
    p.add_argument("--min-scale", type=int, help="Minimum replicas")
    p.add_argument("--max-scale", type=int, help="Maximum replicas")
    p.add_argument("--keep-alive-min", type=int,
                    help="Keep warm N minutes after last request (0 disables)")
    p.add_argument("--rps", type=int, help="RPS scaling threshold per replica")
    p.add_argument("--max-llm-calls", type=int, help="Max LLM calls per task")
    p.add_argument("--memory-enabled", type=lambda v: v.lower() == "true",
                    help="true|false — agent memory")
    p.add_argument("--session-enabled", type=lambda v: v.lower() == "true",
                    help="true|false — conversation sessions")
    p.add_argument("--log-group-id", help="Cloud Logging group ID")
    p.add_argument("--neighbors",
                    help="Comma-separated agent IDs to link as neighbors (related agents)")
    p.add_argument("--mcp-servers",
                    help="Comma-separated MCP server IDs to attach")


def build_parser():
    parser = argparse.ArgumentParser(prog="ai_agents", description="Cloud.ru AI Agents CLI")
    parser.add_argument("--project-id",
        help="Project UUID; overrides PROJECT_ID env var for this invocation")
    top = parser.add_subparsers(dest="group", required=True)

    # ---- agents ----
    agents = top.add_parser("agents", help="Manage agents")
    agsub = agents.add_subparsers(dest="subcommand", required=True)

    p = agsub.add_parser("list", help="List agents")
    p.add_argument("--statuses",
        help="Comma-separated AGENT_STATUS_* to include")
    p.add_argument("--not-in-statuses",
        help="Comma-separated AGENT_STATUS_* to exclude")
    _add_limit_offset(p)

    p = agsub.add_parser("get", help="Get agent details")
    p.add_argument("agent_id")

    p = agsub.add_parser("create", help="Create agent")
    p.add_argument("--name")
    p.add_argument("--description")
    p.add_argument("--instance-type-id")
    p.add_argument("--mcp-server-id",
        help="[deprecated, use --mcp-servers] single MCP id to attach")
    p.add_argument("--from-marketplace", help="Create from marketplace card ID")
    p.add_argument("--cascade-mcp", action="store_true",
        help="When used with --from-marketplace: auto-install MCP servers referenced "
             "in card.suitableCatalogMcpServersIds (reusing existing project MCPs by card id)")
    _add_agent_option_flags(p)
    _add_config_source(p)

    p = agsub.add_parser("update", help="Update agent")
    p.add_argument("agent_id")
    p.add_argument("--name")
    p.add_argument("--description")
    p.add_argument("--instance-type-id")
    _add_agent_option_flags(p)
    _add_config_source(p)

    p = agsub.add_parser("delete", help="Delete agent")
    p.add_argument("agent_id")
    p.add_argument("--yes", action="store_true", help="Skip confirmation")

    p = agsub.add_parser("suspend", help="Suspend agent")
    p.add_argument("agent_id")

    p = agsub.add_parser("resume", help="Resume agent")
    p.add_argument("agent_id")

    p = agsub.add_parser("wait", help="Poll until agent reaches RUNNING/COOLED")
    p.add_argument("agent_id")
    p.add_argument("--timeout", type=int, default=600)

    p = agsub.add_parser("history", help="List agent edit history")
    p.add_argument("agent_id")
    _add_limit_offset(p)

    # ---- systems ----
    systems = top.add_parser("systems", help="Manage agent systems")
    ssub = systems.add_subparsers(dest="subcommand", required=True)

    p = ssub.add_parser("list"); _add_limit_offset(p)
    p = ssub.add_parser("get"); p.add_argument("system_id")
    def _system_flags(p):
        p.add_argument("--system-prompt", help="Orchestrator system prompt")
        p.add_argument("--system-prompt-file")
        p.add_argument("--model-name", help="Orchestrator LLM model")
        p.add_argument("--temperature", type=float)
        p.add_argument("--max-tokens", type=int)
        p.add_argument("--agent-ids", help="Comma-separated agent UUIDs to include as members")
        p.add_argument("--child-system-ids",
            help="Comma-separated child agent-system UUIDs (nested systems)")
        p.add_argument("--context-storage", type=lambda v: v.lower() == "true",
            help="true|false — persistent context storage")
        p.add_argument("--observability", type=lambda v: v.lower() == "true",
            help="true|false — observability tracing")
        add_common_scaling_flags(p)
        add_common_integration_flags(p)

    p = ssub.add_parser("create")
    p.add_argument("--name"); p.add_argument("--description"); p.add_argument("--instance-type-id")
    _system_flags(p)
    _add_config_source(p)

    p = ssub.add_parser("update"); p.add_argument("system_id")
    p.add_argument("--name"); p.add_argument("--description"); p.add_argument("--instance-type-id")
    _system_flags(p)
    _add_config_source(p)
    p = ssub.add_parser("delete"); p.add_argument("system_id"); p.add_argument("--yes", action="store_true")
    p = ssub.add_parser("suspend"); p.add_argument("system_id")
    p = ssub.add_parser("resume"); p.add_argument("system_id")
    p = ssub.add_parser("wait"); p.add_argument("system_id"); p.add_argument("--timeout", type=int, default=600)

    # ---- mcp-servers ----
    mcp = top.add_parser("mcp-servers", help="Manage MCP servers")
    msub = mcp.add_subparsers(dest="subcommand", required=True)

    p = msub.add_parser("list")
    p.add_argument("--not-in-statuses",
        help="Comma-separated MCP_SERVER_STATUS_* to exclude (default: DELETED, ON_DELETION)")
    _add_limit_offset(p)
    p = msub.add_parser("get"); p.add_argument("mcp_id")
    p = msub.add_parser("create")
    p.add_argument("--name"); p.add_argument("--description"); p.add_argument("--instance-type-id")
    p.add_argument("--from-marketplace", help="Marketplace MCP card ID")
    p.add_argument("--image-uri", help="Container image URI (Artifact Registry) — alternative to marketplace")
    p.add_argument("--ports", help="Comma-separated exposed TCP ports (e.g. 8000,9000)")
    add_environment_flags(p)
    add_common_scaling_flags(p)
    add_common_integration_flags(p)
    _add_config_source(p)

    p = msub.add_parser("update"); p.add_argument("mcp_id")
    p.add_argument("--name"); p.add_argument("--description"); p.add_argument("--instance-type-id")
    p.add_argument("--image-uri"); p.add_argument("--ports")
    add_environment_flags(p)
    add_common_scaling_flags(p)
    add_common_integration_flags(p)
    _add_config_source(p)
    p = msub.add_parser("delete"); p.add_argument("mcp_id"); p.add_argument("--yes", action="store_true")
    p = msub.add_parser("suspend"); p.add_argument("mcp_id")
    p = msub.add_parser("resume"); p.add_argument("mcp_id")
    p = msub.add_parser("wait"); p.add_argument("mcp_id"); p.add_argument("--timeout", type=int, default=600)

    # ---- instance-types ----
    it = top.add_parser("instance-types", help="Instance types catalog")
    itsub = it.add_subparsers(dest="subcommand", required=True)
    itsub.add_parser("list", help="List instance types")

    # ---- marketplace ----
    mp = top.add_parser("marketplace", help="Marketplace catalog")
    mpsub = mp.add_subparsers(dest="subcommand", required=True)

    _sort_help = "SORT_TYPE_POPULARITY_DESC (default) | SORT_TYPE_POPULARITY_ASC | SORT_TYPE_UNKNOWN"

    p = mpsub.add_parser("list-agents")
    p.add_argument("--search"); p.add_argument("--sort-type", help=_sort_help)
    _add_limit_offset(p)

    p = mpsub.add_parser("get-agent"); p.add_argument("card_id")

    p = mpsub.add_parser("list-mcp")
    p.add_argument("--search"); p.add_argument("--sort-type", help=_sort_help)
    _add_limit_offset(p)

    p = mpsub.add_parser("get-mcp"); p.add_argument("card_id")

    p = mpsub.add_parser("list-prompts")
    p.add_argument("--search"); p.add_argument("--sort-type", help=_sort_help)
    _add_limit_offset(p)

    p = mpsub.add_parser("get-prompt"); p.add_argument("card_id")

    p = mpsub.add_parser("list-skills")
    p.add_argument("--search"); _add_limit_offset(p)

    p = mpsub.add_parser("get-skill"); p.add_argument("card_id")

    p = mpsub.add_parser("list-snippets")
    p.add_argument("--search"); p.add_argument("--block-styles",
        help="Comma-separated PREDEFINED_SNIPPET_BLOCK_STYLE_* values")
    _add_limit_offset(p)

    p = mpsub.add_parser("get-snippet"); p.add_argument("card_id")

    # ---- prompts ----
    prompts = top.add_parser("prompts", help="Manage prompts (system prompts library)")
    psub = prompts.add_subparsers(dest="subcommand", required=True)

    p = psub.add_parser("list", help="List prompts")
    p.add_argument("--search", help="Filter by name substring")
    p.add_argument("--not-in-statuses",
        help="Comma-separated PROMPT_STATUS_* to exclude (default: DELETED, ON_DELETION)")
    _add_limit_offset(p)

    p = psub.add_parser("get"); p.add_argument("prompt_id")

    p = psub.add_parser("create", help="Create prompt (manual or from marketplace card)")
    p.add_argument("--name")
    p.add_argument("--description")
    p.add_argument("--prompt", help="Inline prompt text")
    p.add_argument("--prompt-file", help="Path to file with prompt text")
    p.add_argument("--target", choices=["agent", "mcp", "agentSystem"], default="agent",
        help="Prompt target — controls promptOptions.{agent|mcp|agentSystem}")
    p.add_argument("--from-marketplace", help="Marketplace prompt card ID")
    _add_config_source(p)

    p = psub.add_parser("update", help="Update prompt (full-body PATCH; merges with current state)")
    p.add_argument("prompt_id")
    p.add_argument("--name")
    p.add_argument("--description")
    p.add_argument("--prompt")
    p.add_argument("--prompt-file")
    p.add_argument("--target", choices=["agent", "mcp", "agentSystem"],
        help="Prompt target (agent|mcp|agentSystem)")
    _add_config_source(p)

    p = psub.add_parser("delete"); p.add_argument("prompt_id"); p.add_argument("--yes", action="store_true")

    p = psub.add_parser("versions", help="List prompt versions")
    p.add_argument("prompt_id")
    _add_limit_offset(p)

    # ---- snippets (Фрагменты) ----
    snippets = top.add_parser("snippets", help="Manage snippets (prompt fragments)")
    snsub = snippets.add_subparsers(dest="subcommand", required=True)

    p = snsub.add_parser("list", help="List snippets")
    p.add_argument("--search")
    p.add_argument("--block-styles",
        help="Comma-separated SNIPPET_BLOCK_STYLE_* (PERSONALITY/TASK/CONTEXT/CONSTRAINTS/TONE_OF_VOICE/ANSWER_EXAMPLES)")
    p.add_argument("--statuses", help="Comma-separated SNIPPET_STATUS_* values")
    _add_limit_offset(p)

    p = snsub.add_parser("get"); p.add_argument("snippet_id")

    p = snsub.add_parser("create")
    p.add_argument("--name")
    p.add_argument("--description")
    p.add_argument("--content", help="Inline snippet body")
    p.add_argument("--content-file", help="Path to file with snippet body")
    p.add_argument("--block-style", help="SNIPPET_BLOCK_STYLE_PERSONALITY|TASK|CONTEXT|CONSTRAINTS|TONE_OF_VOICE|ANSWER_EXAMPLES")
    p.add_argument("--from-marketplace", help="Marketplace snippet card ID — clones name/content/blockStyle")
    _add_config_source(p)

    p = snsub.add_parser("update")
    p.add_argument("snippet_id")
    p.add_argument("--name"); p.add_argument("--description")
    p.add_argument("--content"); p.add_argument("--content-file")
    p.add_argument("--block-style")
    _add_config_source(p)

    p = snsub.add_parser("delete"); p.add_argument("snippet_id"); p.add_argument("--yes", action="store_true")

    # ---- skills (Навыки) ----
    skills = top.add_parser("skills", help="Manage skills (Anthropic-style markdown skills)")
    sksub = skills.add_subparsers(dest="subcommand", required=True)

    p = sksub.add_parser("list")
    p.add_argument("--search")
    p.add_argument("--not-in-statuses",
        help="Comma-separated SKILL_STATUS_* to exclude (default: DELETED)")
    _add_limit_offset(p)
    p = sksub.add_parser("get"); p.add_argument("skill_id")

    p = sksub.add_parser("create", help="Create skill (plaintext or from git)")
    p.add_argument("--name")
    p.add_argument("--description")
    p.add_argument("--compatibility", help="Compatibility note (e.g. 'Python 3.11+')")
    p.add_argument("--prompt", help="Inline skill body (plaintext source)")
    p.add_argument("--prompt-file", help="Path to .md file with skill body")
    p.add_argument("--git-url", help="Import from git URL (sets gitSource)")
    p.add_argument("--git-token", help="Git access token if private repo")
    p.add_argument("--git-folder-paths", help="Comma-separated paths inside repo")
    p.add_argument("--from-marketplace",
        help="Marketplace skill card ID — auto-fills gitSource from card metadata")
    # Requirements & artifacts (UI's "Добавить ограничения и требования" block)
    p.add_argument("--requirements-os", help="OS/runtime requirements (e.g. 'Python 3.11')")
    p.add_argument("--requirements-apps", help="Required apps/tools (free-form text)")
    p.add_argument("--requirements-secrets",
        help="JSON array of required secret IDs, e.g. '[\"API_KEY\"]'")
    p.add_argument("--artifact-paths",
        help="JSON array of output artifact paths, e.g. '[\"out/\"]'")
    p.add_argument("--resources-url", help="Git URL for resources (objectStorage source)")
    p.add_argument("--allowed-tools",
        help="Comma-separated tool names agent can invoke (read_file,grep,run_terminal_cmd,...)")
    _add_config_source(p)

    p = sksub.add_parser("delete"); p.add_argument("skill_id"); p.add_argument("--yes", action="store_true")

    p = sksub.add_parser("analyze", help="Analyze git source — preview fileTree before create")
    p.add_argument("--git-url"); p.add_argument("--git-token")
    _add_config_source(p)

    # ---- workflows (Preview) ----
    workflows = top.add_parser("workflows",
        help="AI Workflows (low-code) — create-container/delete here, edit graph in IDE")
    wsub = workflows.add_subparsers(dest="subcommand", required=True)
    p = wsub.add_parser("list")
    p.add_argument("--search")
    p.add_argument("--statuses",
        help="Comma-separated WORKFLOW_* statuses to include (ACTIVE/SUSPENDED/ON_CREATION/...)")
    _add_limit_offset(p)
    p = wsub.add_parser("get"); p.add_argument("workflow_id")
    p = wsub.add_parser("create",
        help="Create empty workflow container (edit graph afterwards in IDE)")
    p.add_argument("--name", help="Workflow name")
    p.add_argument("--description")
    p.add_argument("--log-group-id", help="Cloud Logging group ID (default: project default)")
    _add_config_source(p)
    p = wsub.add_parser("update"); p.add_argument("workflow_id")
    p.add_argument("--name"); p.add_argument("--description")
    p.add_argument("--log-group-id")
    _add_config_source(p)
    p = wsub.add_parser("delete"); p.add_argument("workflow_id"); p.add_argument("--yes", action="store_true")

    # ---- triggers ----
    triggers = top.add_parser("triggers", help="Agent triggers (Telegram/Schedule)")
    tsub = triggers.add_subparsers(dest="subcommand", required=True)

    p = tsub.add_parser("list", help="List triggers attached to an agent")
    p.add_argument("agent_id")
    p.add_argument("--not-in-statuses",
        help="Comma-separated TRIGGER_STATUS_* to exclude (default: DELETED)")
    _add_limit_offset(p)

    p = tsub.add_parser("get")
    p.add_argument("agent_id"); p.add_argument("trigger_id")

    p = tsub.add_parser("check-name", help="Check if a trigger name is free")
    p.add_argument("agent_id"); p.add_argument("--name", required=True)

    p = tsub.add_parser("create",
        help="Create trigger (schedule and telegram via flags; email via --config-json)")
    p.add_argument("agent_id")
    p.add_argument("--name", help="Trigger name (letters+digits+hyphen, 5-50 chars)")
    p.add_argument("--trigger-type", choices=["schedule", "telegram", "email"],
        help="Schedule (cron), Telegram (bot token) or Email (IMAP credentials)")
    # Schedule flags
    p.add_argument("--cron", help="Cron expression, e.g. '0 10 * * 2,4' (Tue,Thu at 10:00)")
    p.add_argument("--timezone", help="Timezone for cron (default: Europe/Moscow)")
    p.add_argument("--message-template",
        help="Message template with {{textMessage}} placeholder")
    # Telegram flags
    p.add_argument("--bot-name",
        help="Telegram bot username (5-32 chars, e.g. 'my_bot')")
    p.add_argument("--bot-token-secret-id",
        help="Secret Manager secret UUID that stores @BotFather token")
    p.add_argument("--bot-token-secret-version", type=int, default=1,
        help="Secret version (default: 1)")
    p.add_argument("--tg-events",
        help="Comma-separated enabled events (default: messageReceived). "
             "Valid: messageReceived,messageDeleted,messageEdited,newChatCreated,"
             "userJoined,userLeft,callbackQuery,channelPost,editedChannelPost")
    # Email flags
    p.add_argument("--email-server", help="IMAP server address (e.g. imap.mail.ru)")
    p.add_argument("--email-port", type=int, help="IMAP port (default: 993)")
    p.add_argument("--email-security",
        help="Security: SSL/TLS (default), STARTTLS, or none")
    p.add_argument("--email-user", help="Mailbox username/email")
    p.add_argument("--email-password-secret-id",
        help="Secret Manager UUID holding mailbox password")
    p.add_argument("--email-password-secret-version", type=int, default=1,
        help="Password secret version (default: 1)")
    p.add_argument("--email-events",
        help="Comma-separated enabled events (default: emailReceived). "
             "Valid: emailReceived,emailRead,emailDeleted,emailReplied,"
             "emailForwarded,emailMarkedImportant,emailMoved")
    _add_config_source(p)

    p = tsub.add_parser("update")
    p.add_argument("agent_id"); p.add_argument("trigger_id")
    _add_config_source(p)

    p = tsub.add_parser("delete")
    p.add_argument("agent_id"); p.add_argument("trigger_id")
    p.add_argument("--yes", action="store_true")

    # ---- evo-claws (Preview) ----
    ec = top.add_parser("evo-claws", help="Evo Claw managed OpenClaw gateways")
    ecsub = ec.add_subparsers(dest="subcommand", required=True)

    p = ecsub.add_parser("list")
    p.add_argument("--statuses",
        help="Comma-separated EVOCLAW_STATUS_* to include (RUNNING/ON_CREATION/FAILED/...)")
    _add_limit_offset(p)

    p = ecsub.add_parser("get"); p.add_argument("evoclaw_id")

    p = ecsub.add_parser("create", help="Create an EvoClaw gateway")
    p.add_argument("--name")
    p.add_argument("--instance-type-id", help="Instance type UUID")
    p.add_argument("--model-name", help="Default LLM model name (e.g. zai-org/GLM-4.7)")
    p.add_argument("--log-group-id", help="Cloud Logging group ID (empty string disables)")
    p.add_argument("--enable-tracing", action="store_true")
    _add_config_source(p)

    p = ecsub.add_parser("update")
    p.add_argument("evoclaw_id")
    p.add_argument("--description")
    p.add_argument("--instance-type-id")
    p.add_argument("--model-name")
    _add_config_source(p)

    p = ecsub.add_parser("delete")
    p.add_argument("evoclaw_id"); p.add_argument("--yes", action="store_true")

    p = ecsub.add_parser("wait", help="Poll until RUNNING")
    p.add_argument("evoclaw_id"); p.add_argument("--timeout", type=int, default=600)

    # Workers (sub-agents inside the claw)
    p = ecsub.add_parser("list-workers", help="List sub-agents (workers) inside the claw")
    p.add_argument("evoclaw_id")

    p = ecsub.add_parser("set-workers",
        help="Replace full workers list (PUT — send {\"agents\":[...]} via --config-json)")
    p.add_argument("evoclaw_id")
    _add_config_source(p)

    p = ecsub.add_parser("add-worker",
        help="Fetch current workers, append one with sensible defaults, PUT back")
    p.add_argument("evoclaw_id")
    p.add_argument("--name", help="Worker name (unique inside the claw)")
    p.add_argument("--description")
    p.add_argument("--system-prompt")
    p.add_argument("--workspace", help="Workspace folder (default ./workspace/{name})")
    p.add_argument("--model-name", help="LLM model for this worker")
    _add_config_source(p)

    p = ecsub.add_parser("remove-worker", help="Remove worker by name (GET + PUT)")
    p.add_argument("evoclaw_id"); p.add_argument("--name", required=True)

    # ---- chat (A2A JSON-RPC) ----
    chat = top.add_parser("chat", help="Chat with an agent via A2A protocol")
    chsub = chat.add_subparsers(dest="subcommand", required=True)

    p = chsub.add_parser("card", help="Get A2A agent card (capabilities, inputModes)")
    p.add_argument("agent_id")

    p = chsub.add_parser("send", help="Send a user message to the agent, print reply")
    p.add_argument("agent_id")
    p.add_argument("--message", help="Message text")
    p.add_argument("--message-file", help="Read message from file")
    p.add_argument("--context-id", help="Continue an existing conversation (reuse from previous reply)")
    p.add_argument("--task-id", help="Reply into existing task")
    p.add_argument("--raw", action="store_true", help="Print full JSON-RPC response instead of just text")

    p = chsub.add_parser("raw", help="Raw JSON-RPC call to /a2a")
    p.add_argument("agent_id")
    p.add_argument("--method", required=True,
        help="agent/card | message/send | message/stream | tasks/get | tasks/cancel")
    p.add_argument("--params-json", help="JSON for params field")
    p.add_argument("--context-id")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.project_id:
        os.environ["PROJECT_ID"] = args.project_id
    key = f"{args.group}.{args.subcommand}"
    handler = COMMANDS.get(key)
    if handler is None:
        print(f"Error: unknown command: {key}", file=sys.stderr)
        sys.exit(1)
    handler(args)


if __name__ == "__main__":
    main()
