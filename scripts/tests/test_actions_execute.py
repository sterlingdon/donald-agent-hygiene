import os, json
from hygiene.actions import execute
from hygiene.model import Item, Finding, Severity, Kind, Host, Origin


def _find(it, sev=Severity.GREEN):
    return Finding(item=it, severity=sev, reasons=["never used"])


def test_archive_cc_personal_skill_apply(tmp_path):
    sd = tmp_path / "skills" / "z"; sd.mkdir(parents=True); (sd / "SKILL.md").write_text("x")
    it = Item(Host.CLAUDE, Kind.SKILL, "z", Origin.PERSONAL, str(sd), True)
    r = execute(_find(it), backups=str(tmp_path / "bk"), dry_run=False)
    assert r.kind == "archive_skill" and r.applied and not os.path.exists(sd) and r.backup


def test_archive_dry_run_noop(tmp_path):
    sd = tmp_path / "skills" / "z"; sd.mkdir(parents=True); (sd / "SKILL.md").write_text("x")
    it = Item(Host.CLAUDE, Kind.SKILL, "z", Origin.PERSONAL, str(sd), True)
    r = execute(_find(it), backups=str(tmp_path / "bk"), dry_run=True)
    assert r.applied is False and os.path.exists(sd)


def test_remove_user_mcp_apply(tmp_path):
    cj = tmp_path / ".claude.json"; cj.write_text(json.dumps({"mcpServers": {"drop": {}, "keep": {}}}))
    it = Item(Host.CLAUDE, Kind.MCP, "drop", Origin.USER_CONFIG, str(cj), True)
    r = execute(_find(it), backups=str(tmp_path / "bk"), dry_run=False)
    assert r.kind == "remove_user_mcp" and r.applied
    assert "drop" not in json.loads(cj.read_text())["mcpServers"]


def test_codex_mcp_is_command_only(tmp_path):
    it = Item(Host.CODEX, Kind.MCP, "node_repl", Origin.USER_CONFIG, str(tmp_path / "config.toml"), True)
    r = execute(_find(it), backups=str(tmp_path / "bk"), dry_run=False)
    assert r.kind == "command_only" and r.applied is False and "codex mcp remove" in r.command


def test_disable_plugin_apply(tmp_path):
    st = tmp_path / ".claude" / "settings.json"; st.parent.mkdir(parents=True)
    st.write_text(json.dumps({"enabledPlugins": {"foo@mp": True}}))
    it = Item(Host.CLAUDE, Kind.SKILL, "s", Origin.PLUGIN, "/p", False, plugin="foo@mp")
    r = execute(_find(it, Severity.YELLOW), backups=str(tmp_path / "bk"),
                dry_run=False, home=str(tmp_path))
    assert r.kind == "disable_plugin" and r.applied
    assert json.loads(st.read_text())["enabledPlugins"]["foo@mp"] is False
