import glob, os
from typing import List, Set
from .model import Item, Kind, Host, Origin
from .util import read_frontmatter, read_json
from .normalize import skill_match_keys

def _skill_item(skill_dir: str, origin: Origin, enabled: bool, plugin=None, ns=None) -> Item:
    fm = read_frontmatter(os.path.join(skill_dir, "SKILL.md"))
    base = fm.get("name") or os.path.basename(skill_dir)
    name = f"{ns}:{base}" if ns else base
    return Item(host=Host.CLAUDE, kind=Kind.SKILL, name=name, origin=origin,
                path=skill_dir, enabled=enabled, plugin=plugin,
                description=fm.get("description", ""),
                match_keys=frozenset(skill_match_keys(name)))

def _enabled_plugins(home: str) -> dict:
    # enabledPlugins lives in ~/.claude/settings.json (NOT ~/.claude.json)
    data = read_json(os.path.join(home, ".claude/settings.json"))
    return data.get("enabledPlugins") or {}

def _plugin_id_from_cache_path(path: str) -> str:
    # .../plugins/cache/<marketplace>/<plugin>/<version>/...
    parts = path.split(os.sep)
    try:
        i = parts.index("cache")
        return f"{parts[i+2]}@{parts[i+1]}"   # <plugin>@<marketplace>
    except (ValueError, IndexError):
        return ""

def collect(home: str, cwd: str) -> List[Item]:
    items: List[Item] = []
    enabled = _enabled_plugins(home)

    # S1 personal skills
    for d in glob.glob(os.path.join(home, ".claude/skills/*/")):
        items.append(_skill_item(d.rstrip("/"), Origin.PERSONAL, True))

    # S2 project skills
    for d in glob.glob(os.path.join(cwd, ".claude/skills/*/")):
        items.append(_skill_item(d.rstrip("/"), Origin.PROJECT, True))

    # S3/S4 plugin cache skills (active only if owning plugin enabled)
    for md in glob.glob(os.path.join(home, ".claude/plugins/cache/**/SKILL.md"), recursive=True):
        sd = os.path.dirname(md)
        pid = _plugin_id_from_cache_path(md)         # e.g. superpowers@off
        ns = pid.split("@", 1)[0] if pid else None
        is_on = bool(enabled.get(pid, False))
        items.append(_skill_item(sd, Origin.PLUGIN if is_on else Origin.CATALOG,
                                 is_on, plugin=pid, ns=ns))

    # S4 marketplace catalog skills (browseable, never active)
    for md in glob.glob(os.path.join(home, ".claude/plugins/marketplaces/**/SKILL.md"), recursive=True):
        items.append(_skill_item(os.path.dirname(md), Origin.CATALOG, False))

    # M1 user MCP
    cj = read_json(os.path.join(home, ".claude.json"))
    for name in (cj.get("mcpServers") or {}):
        items.append(Item(Host.CLAUDE, Kind.MCP, name, Origin.USER_CONFIG,
                          os.path.join(home, ".claude.json"), True))

    # M2 project MCP
    proj_mcp = read_json(os.path.join(cwd, ".mcp.json")).get("mcpServers") or {}
    settings = read_json(os.path.join(home, ".claude/settings.json"))
    dis = set(settings.get("disabledMcpjsonServers") or [])
    ena = set(settings.get("enabledMcpjsonServers") or [])
    all_on = bool(settings.get("enableAllProjectMcpServers"))
    for name in proj_mcp:
        on = (all_on or name in ena) and name not in dis
        items.append(Item(Host.CLAUDE, Kind.MCP, name, Origin.PROJECT,
                          os.path.join(cwd, ".mcp.json"), on))

    # M3 plugin-bundled MCP (active only if owning plugin enabled)
    for mj in glob.glob(os.path.join(home, ".claude/plugins/cache/**/.mcp.json"), recursive=True):
        pid = _plugin_id_from_cache_path(mj)
        is_on = bool(enabled.get(pid, False))
        for name in (read_json(mj).get("mcpServers") or {}):
            items.append(Item(Host.CLAUDE, Kind.MCP, name, Origin.PLUGIN, mj, is_on, plugin=pid))

    # P1 plugins themselves
    for pid, on in enabled.items():
        items.append(Item(Host.CLAUDE, Kind.PLUGIN, pid, Origin.PLUGIN,
                          os.path.join(home, ".claude/plugins"), bool(on), plugin=pid))
    return items
