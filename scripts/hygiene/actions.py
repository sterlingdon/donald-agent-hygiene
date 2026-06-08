import json, os, shutil
from datetime import datetime
from .model import Finding, Kind, Origin, ActionResult, Host


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


def execute(finding, backups, dry_run=True, home=None):
    """Route a Finding to the right mutation. Dry-run by default; every real
    mutation backs up first. Codex config.toml is never auto-edited (command only)."""
    it = finding.item
    home = home or os.path.expanduser("~")
    # CC / Codex personal/project skill -> archive the directory
    if it.kind == Kind.SKILL and it.origin in (Origin.PERSONAL, Origin.PROJECT):
        cmd = archive_skill(it.path, backups=backups, dry_run=True)
        if dry_run:
            return ActionResult("archive_skill", it.path, cmd, False)
        dest_parent = backup_path(backups)
        dest = os.path.join(dest_parent, os.path.basename(it.path.rstrip("/")))
        shutil.copytree(it.path, dest, dirs_exist_ok=True)
        shutil.rmtree(it.path)
        return ActionResult("archive_skill", it.path, cmd, True, dest_parent)
    # CC user-config MCP -> remove from ~/.claude.json
    if it.kind == Kind.MCP and it.origin == Origin.USER_CONFIG and it.host == Host.CLAUDE:
        claude_json = os.path.join(home, ".claude.json")
        target = it.path if os.path.basename(it.path) == ".claude.json" else claude_json
        cmd = f"claude mcp remove '{it.name}'  (edits {target})"
        if dry_run:
            return ActionResult("remove_user_mcp", it.name, cmd, False)
        disable_mcp_user(target, it.name, backups=backups, dry_run=False)
        return ActionResult("remove_user_mcp", it.name, cmd, True, backups)
    # Codex MCP -> command only (no safe stdlib TOML writer)
    if it.kind == Kind.MCP and it.host == Host.CODEX:
        return ActionResult("command_only", it.name, f"codex mcp remove '{it.name}'", False)
    # plugin-owned item -> disable the whole plugin via settings.json
    if it.plugin:
        settings = os.path.join(home, ".claude/settings.json")
        cmd = f"disable plugin {it.plugin} in {settings}"
        if dry_run:
            return ActionResult("disable_plugin", it.plugin, cmd, False)
        disable_plugin(settings, it.plugin, backups=backups, dry_run=False)
        return ActionResult("disable_plugin", it.plugin, cmd, True, backups)
    return ActionResult("skip", it.name, f"# no automatic action for {it.name}", False)
