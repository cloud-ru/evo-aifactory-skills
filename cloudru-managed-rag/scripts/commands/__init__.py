"""CLI command registry."""

from commands.kb import (
    cmd_delete,
    cmd_get,
    cmd_list,
    cmd_reindex,
    cmd_version_detail,
    cmd_versions,
)
from commands.query import cmd_ask, cmd_search
from commands.setup import cmd_setup, cmd_setup_step

COMMANDS = {
    "list": cmd_list,
    "get": cmd_get,
    "versions": cmd_versions,
    "version-detail": cmd_version_detail,
    "delete": cmd_delete,
    "reindex": cmd_reindex,
    "search": cmd_search,
    "ask": cmd_ask,
    "setup": cmd_setup,
    "setup-step": cmd_setup_step,
}
