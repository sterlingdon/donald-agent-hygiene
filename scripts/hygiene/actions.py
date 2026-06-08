import json, os, shutil
from datetime import datetime
from .model import Finding, Kind, Origin


def backup_path(backups: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    p = os.path.join(backups, stamp)
    os.makedirs(p, exist_ok=True)
    return p


def archive_skill(skill_dir: str, backups: str, dry_run: bool = True) -> str:
    dest = os.path.join(backup_path(backups), os.path.basename(skill_dir.rstrip("/")))
    plan = f"mv {skill_dir} {dest}"
    if dry_run:
        return plan
    shutil.copytree(skill_dir, dest, dirs_exist_ok=True)
    shutil.rmtree(skill_dir)
    return plan


def disable_mcp_user(claude_json: str, server: str, backups: str, dry_run: bool = True) -> str:
    plan = f"remove mcpServers['{server}'] from {claude_json}"
    if dry_run:
        return plan
    bk = backup_path(backups)
    shutil.copy2(claude_json, os.path.join(bk, os.path.basename(claude_json)))
    with open(claude_json) as f:
        data = json.load(f)
    (data.get("mcpServers") or {}).pop(server, None)
    with open(claude_json, "w") as f:
        json.dump(data, f, indent=2)
    return plan


def disable_plugin(claude_settings: str, plugin_id: str, backups: str, dry_run: bool = True) -> str:
    plan = f"set enabledPlugins['{plugin_id}']=false in {claude_settings}"
    if dry_run:
        return plan
    bk = backup_path(backups)
    shutil.copy2(claude_settings, os.path.join(bk, os.path.basename(claude_settings)))
    with open(claude_settings) as f:
        data = json.load(f)
    data.setdefault("enabledPlugins", {})[plugin_id] = False
    with open(claude_settings, "w") as f:
        json.dump(data, f, indent=2)
    return plan


def suggest_command(f: Finding) -> str:
    it = f.item
    if it.kind == Kind.SKILL and it.origin in (Origin.PERSONAL, Origin.PROJECT):
        return f"# archive unused skill\nmv '{it.path}' ~/.agent-hygiene-backups/"
    if it.kind == Kind.SKILL and it.origin in (Origin.PLUGIN, Origin.CATALOG) and it.plugin:
        return f"# disable owning plugin\nclaude  # then /plugin disable {it.plugin}"
    if it.kind == Kind.MCP and it.origin == Origin.USER_CONFIG and it.host.value == "claude":
        return f"claude mcp remove '{it.name}'"
    if it.kind == Kind.MCP and it.host.value == "codex":
        return f"codex mcp remove '{it.name}'"
    return f"# review: {it.name}"
