"""Aggregate COMMANDS dict from all submodules."""

from commands.agents import COMMANDS as AGENTS_COMMANDS
from commands.systems import COMMANDS as SYSTEMS_COMMANDS
from commands.mcp_servers import COMMANDS as MCP_COMMANDS
from commands.instance_types import COMMANDS as IT_COMMANDS
from commands.marketplace import COMMANDS as MP_COMMANDS
from commands.prompts import COMMANDS as PROMPTS_COMMANDS
from commands.snippets import COMMANDS as SNIPPETS_COMMANDS
from commands.skills import COMMANDS as SKILLS_COMMANDS
from commands.workflows import COMMANDS as WORKFLOWS_COMMANDS
from commands.triggers import COMMANDS as TRIGGERS_COMMANDS
from commands.evo_claws import COMMANDS as EVOCLAW_COMMANDS
from commands.chat import COMMANDS as CHAT_COMMANDS


COMMANDS = {}
COMMANDS.update(AGENTS_COMMANDS)
COMMANDS.update(SYSTEMS_COMMANDS)
COMMANDS.update(MCP_COMMANDS)
COMMANDS.update(IT_COMMANDS)
COMMANDS.update(MP_COMMANDS)
COMMANDS.update(PROMPTS_COMMANDS)
COMMANDS.update(SNIPPETS_COMMANDS)
COMMANDS.update(SKILLS_COMMANDS)
COMMANDS.update(WORKFLOWS_COMMANDS)
COMMANDS.update(TRIGGERS_COMMANDS)
COMMANDS.update(EVOCLAW_COMMANDS)
COMMANDS.update(CHAT_COMMANDS)
