"""CLI handlers for `chat` — send messages to an AI agent over A2A JSON-RPC.

The Chat UI in Cloud.ru console uses the Agent-to-Agent protocol (jsonrpc 2.0)
with methods `agent/card`, `message/send`, `message/stream`, `tasks/get`,
`tasks/cancel`. The agent must be in `AGENT_STATUS_RUNNING` to accept messages.
"""

import json
import sys
import uuid

from helpers import build_client, check_response, print_json


def cmd_card(args):
    """Fetch agent card: capabilities, streaming support, inputModes."""
    client, project_id = build_client()
    resp = client.a2a_agent_card(project_id, args.agent_id)
    check_response(resp, f"fetching A2A card for agent {args.agent_id}")
    print_json(resp.json())


def _build_send_body(message_text: str, context_id: str = None,
                     task_id: str = None, method: str = "message/send") -> dict:
    msg: dict = {
        "role": "user",
        "parts": [{"kind": "text", "text": message_text}],
        "messageId": str(uuid.uuid4()),
    }
    if task_id:
        msg["taskId"] = task_id
    body = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": {"message": msg},
    }
    if context_id:
        body["contextId"] = context_id
    return body


def cmd_send(args):
    """Send a message to the agent and print the reply artifacts."""
    if not args.message and not args.message_file:
        print("Error: --message or --message-file required", file=sys.stderr)
        sys.exit(1)
    text = args.message
    if args.message_file:
        with open(args.message_file) as f:
            text = f.read()
    client, project_id = build_client()
    body = _build_send_body(text, context_id=args.context_id, task_id=args.task_id)
    resp = client.a2a_call(project_id, args.agent_id, body)
    check_response(resp, f"sending A2A message to agent {args.agent_id}")
    data = resp.json()
    if args.raw:
        print_json(data)
        return
    # Pretty-print artifacts[].parts[].text
    result = data.get("result", {})
    artifacts = result.get("artifacts") or []
    for art in artifacts:
        for part in art.get("parts") or []:
            if part.get("kind") == "text":
                print(part.get("text", ""))
    if not artifacts:
        print_json(data)


def cmd_raw(args):
    """Raw JSON-RPC call (method=<anything>, params from --params-json)."""
    client, project_id = build_client()
    body = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": args.method,
        "params": json.loads(args.params_json) if args.params_json else None,
    }
    if args.context_id:
        body["contextId"] = args.context_id
    resp = client.a2a_call(project_id, args.agent_id, body)
    check_response(resp, f"A2A {args.method}")
    print_json(resp.json())


COMMANDS = {
    "chat.card": cmd_card,
    "chat.send": cmd_send,
    "chat.raw": cmd_raw,
}
