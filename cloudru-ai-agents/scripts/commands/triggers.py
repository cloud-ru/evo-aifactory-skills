"""CLI handlers for `triggers` — attach event sources to an agent.

Two trigger types in UI: Telegram (bot pulls messages from @BotFather bot and
passes them into agent chat) and Schedule (cron-like periodic invocation).

The body schema is complex (variant type + whitelist + secret refs). CLI does
not hand-hold each shape — users pass a full body via `--config-json` or
`--config-file`. Use `triggers check-name` first; creation fails with 409 if
name is taken.
"""

import sys

from helpers import (build_client, check_response, print_json, load_config_from_args,
                     confirm_destructive)


def cmd_list(args):
    client, project_id = build_client()
    not_in = args.not_in_statuses.split(",") if getattr(args, "not_in_statuses", None) else None
    resp = client.list_agent_triggers(project_id, args.agent_id,
                                       limit=args.limit, offset=args.offset,
                                       not_in_statuses=not_in)
    check_response(resp, f"listing triggers for agent {args.agent_id}")
    print_json(resp.json())


def cmd_get(args):
    client, project_id = build_client()
    resp = client.get_agent_trigger(project_id, args.agent_id, args.trigger_id)
    check_response(resp, f"getting trigger {args.trigger_id}")
    print_json(resp.json())


def cmd_check_name(args):
    client, project_id = build_client()
    resp = client.check_trigger_name(project_id, args.agent_id, args.name)
    check_response(resp, f"checking trigger name {args.name}")
    print_json(resp.json() if resp.text else {"available": True})


TELEGRAM_EVENTS = [
    "messageReceived", "messageDeleted", "messageEdited", "newChatCreated",
    "userJoined", "userLeft", "callbackQuery", "channelPost", "editedChannelPost",
]
EMAIL_EVENTS = [
    "emailReceived", "emailRead", "emailDeleted", "emailReplied",
    "emailForwarded", "emailMarkedImportant", "emailMoved",
]


def _event_block(event_name: str, template: str, enabled: bool) -> dict:
    if enabled:
        return {
            "eventLabel": event_name, "isEnabled": True,
            "messageRenderTemplate": template,
            "messageVariables": [
                {"variableLabel": "textMessage", "description": "Текст сообщения"},
            ],
        }
    return {"eventLabel": "", "isEnabled": False,
            "messageRenderTemplate": "", "messageVariables": []}


def _build_schedule_body(args) -> dict:
    """Build options.providerOptions.schedule from --cron/--timezone/--message-template."""
    template = args.message_template or "Пользователь прислал сообщение: {{textMessage}}"
    return {
        "schedule": {
            "config": {
                "cronExpression": args.cron,
                "timezone": args.timezone or "Europe/Moscow",
            },
            "events": {
                "scheduleTriggered": {
                    "eventLabel": "scheduleTriggered",
                    "isEnabled": True,
                    "messageRenderTemplate": template,
                    "messageVariables": [
                        {"variableLabel": "textMessage",
                         "description": "Текст сообщения"},
                    ],
                },
            },
        }
    }


def _build_telegram_body(args) -> dict:
    """Build options.providerOptions.telegram from --bot-name/--bot-token-secret-id/--events.

    Shape captured from UI POST: credentials.{botName, botToken.{id,version}} +
    events.{messageReceived, messageDeleted, ...} where each unchecked event still
    appears with isEnabled=false (server rejects missing event keys). Only one
    event — messageReceived — is enabled by default, mirroring the UI.
    """
    template = args.message_template or "Пользователь прислал сообщение: {{textMessage}}"
    enabled = {e.strip() for e in (args.tg_events or "messageReceived").split(",") if e.strip()}
    for e in enabled:
        if e not in TELEGRAM_EVENTS:
            print(f"Error: unknown telegram event '{e}'. Valid: {','.join(TELEGRAM_EVENTS)}",
                  file=sys.stderr)
            sys.exit(1)
    events = {e: _event_block(e, template, e in enabled) for e in TELEGRAM_EVENTS}
    return {
        "telegram": {
            "events": events,
            "credentials": {
                "botName": args.bot_name,
                "botToken": {
                    "id": args.bot_token_secret_id,
                    "version": args.bot_token_secret_version or 1,
                },
            },
        }
    }


def _build_email_body(args) -> dict:
    """Build options.providerOptions.email from --email-server/--email-port/--email-user/
    --email-password-secret-id/--email-events.

    Shape: credentials.{serverAddress, port, securityCertificate, username,
    password.{id,version}} + events.{emailReceived, emailRead, ...}.
    """
    template = args.message_template or "Пользователь прислал сообщение: {{textMessage}}"
    enabled = {e.strip() for e in (args.email_events or "emailReceived").split(",") if e.strip()}
    for e in enabled:
        if e not in EMAIL_EVENTS:
            print(f"Error: unknown email event '{e}'. Valid: {','.join(EMAIL_EVENTS)}",
                  file=sys.stderr)
            sys.exit(1)
    events = {e: _event_block(e, template, e in enabled) for e in EMAIL_EVENTS}
    return {
        "email": {
            "events": events,
            "credentials": {
                "serverAddress": args.email_server,
                "port": args.email_port or 993,
                "securityCertificate": args.email_security or "SSL/TLS",
                "username": args.email_user,
                "password": {
                    "id": args.email_password_secret_id,
                    "version": args.email_password_secret_version or 1,
                },
            },
        }
    }


def cmd_create(args):
    body = load_config_from_args(args)
    if args.name:
        body["name"] = args.name
    trig_type = getattr(args, "trigger_type", None)
    # High-level schedule flags
    if trig_type == "schedule" or getattr(args, "cron", None):
        if not args.cron:
            print("Error: --cron required for schedule trigger (e.g. '0 10 * * 2,4')",
                  file=sys.stderr)
            sys.exit(1)
        body.setdefault("options", {}).setdefault("providerOptions", {}).update(
            _build_schedule_body(args))
    # High-level telegram flags
    elif trig_type == "telegram":
        if not args.bot_name or not args.bot_token_secret_id:
            print("Error: --bot-name and --bot-token-secret-id required for telegram trigger",
                  file=sys.stderr)
            sys.exit(1)
        body.setdefault("options", {}).setdefault("providerOptions", {}).update(
            _build_telegram_body(args))
    # High-level email flags
    elif trig_type == "email":
        required = ["email_server", "email_user", "email_password_secret_id"]
        missing = [f"--{r.replace('_', '-')}" for r in required if not getattr(args, r, None)]
        if missing:
            print(f"Error: {', '.join(missing)} required for email trigger", file=sys.stderr)
            sys.exit(1)
        body.setdefault("options", {}).setdefault("providerOptions", {}).update(
            _build_email_body(args))
    if "name" not in body:
        print("Error: 'name' is required (letters+digits+hyphen, 5-50 chars)",
              file=sys.stderr)
        sys.exit(1)
    if not body.get("options", {}).get("providerOptions"):
        print("Error: trigger options required — pass --trigger-type schedule|telegram|email "
              "(+flags) or full body via --config-json", file=sys.stderr)
        sys.exit(1)
    client, project_id = build_client()
    resp = client.create_agent_trigger(project_id, args.agent_id, body)
    check_response(resp, f"creating trigger on agent {args.agent_id}")
    print_json(resp.json())


def cmd_update(args):
    body = load_config_from_args(args)
    if not body:
        print("Error: --config-json or --config-file required", file=sys.stderr)
        sys.exit(1)
    client, project_id = build_client()
    resp = client.update_agent_trigger(project_id, args.agent_id, args.trigger_id, body)
    check_response(resp, f"updating trigger {args.trigger_id}")
    print_json(resp.json() if resp.text else {})


def cmd_delete(args):
    confirm_destructive("delete", f"trigger {args.trigger_id}", args.yes)
    client, project_id = build_client()
    resp = client.delete_agent_trigger(project_id, args.agent_id, args.trigger_id)
    check_response(resp, f"deleting trigger {args.trigger_id}")
    print_json(resp.json() if resp.text else {"status": "deleted"})


COMMANDS = {
    "triggers.list": cmd_list,
    "triggers.get": cmd_get,
    "triggers.check-name": cmd_check_name,
    "triggers.create": cmd_create,
    "triggers.update": cmd_update,
    "triggers.delete": cmd_delete,
}
