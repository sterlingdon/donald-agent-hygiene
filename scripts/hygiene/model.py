from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class Kind(str, Enum):
    SKILL = "skill"; MCP = "mcp"; PLUGIN = "plugin"

class Host(str, Enum):
    CLAUDE = "claude"; CODEX = "codex"

class Origin(str, Enum):
    PERSONAL = "personal"; PROJECT = "project"; PLUGIN = "plugin"
    CATALOG = "catalog"; USER_CONFIG = "user_config"

class Severity(str, Enum):
    GREEN = "green"; YELLOW = "yellow"; RED = "red"; KEEP = "keep"

@dataclass
class Item:
    host: Host
    kind: Kind
    name: str
    origin: Origin
    path: str
    enabled: bool
    plugin: Optional[str] = None
    description: str = ""
    est_tokens: int = 0
    cost_band: str = "low"            # low | med | high
    match_keys: frozenset = field(default_factory=frozenset)

@dataclass
class Usage:
    name: str
    count: int
    last_used: Optional[float]        # epoch seconds

@dataclass
class Finding:
    item: Item
    severity: Severity
    reasons: list                     # list[str]
    usage: Optional[Usage] = None
    suggested_cmd: Optional[str] = None


@dataclass
class ActionResult:
    kind: str            # archive_skill | remove_user_mcp | disable_plugin | command_only | skip
    target: str          # path or name acted on
    command: str         # human-readable description / shell command
    applied: bool        # True if a mutation actually happened
    backup: str = ""     # backup dir/file if any
