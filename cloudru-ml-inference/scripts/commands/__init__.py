"""CLI command registry."""

from commands.catalog import cmd_catalog, cmd_catalog_detail, cmd_deploy
from commands.crud import (
    cmd_create,
    cmd_delete,
    cmd_get,
    cmd_list,
    cmd_resume,
    cmd_suspend,
    cmd_update,
)
from commands.inference import cmd_call, cmd_embed, cmd_ping, cmd_rerank
from commands.info import cmd_frameworks, cmd_history, cmd_quotas

COMMANDS = {
    "list": cmd_list,
    "get": cmd_get,
    "create": cmd_create,
    "update": cmd_update,
    "delete": cmd_delete,
    "suspend": cmd_suspend,
    "resume": cmd_resume,
    "call": cmd_call,
    "embed": cmd_embed,
    "rerank": cmd_rerank,
    "ping": cmd_ping,
    "history": cmd_history,
    "quotas": cmd_quotas,
    "frameworks": cmd_frameworks,
    "catalog": cmd_catalog,
    "catalog-detail": cmd_catalog_detail,
    "deploy": cmd_deploy,
}
