import os
from hygiene.cli import run, _dedup
from hygiene.model import Item, Kind, Host, Origin


def test_run_scan_writes_html(fake_home, tmp_path):
    out = tmp_path / "report.html"
    rc = run(["scan", "--home", str(fake_home), "--codex-home", str(fake_home / ".codex"),
              "--projects", str(fake_home / ".claude" / "projects"),
              "--sessions", str(fake_home / ".codex" / "sessions"),
              "--cwd", str(fake_home / "noproject"), "--out", str(out)])
    assert rc == 0 and out.exists()
    text = out.read_text()
    assert "Agent Hygiene" in text
    # never-used personal skill should be flagged somewhere
    assert "never-used" in text


def test_scan_never_mutates(fake_home, tmp_path):
    rc = run(["scan", "--home", str(fake_home), "--codex-home", str(fake_home / ".codex"),
              "--projects", str(fake_home / "p"), "--sessions", str(fake_home / "s"),
              "--cwd", str(fake_home), "--out", str(tmp_path / "r.html")])
    assert rc == 0  # scan never mutates


def test_dedup_collapses_identical_plugin_mcp():
    def mcp(path):
        return Item(Host.CLAUDE, Kind.MCP, "supabase", Origin.PLUGIN, path, False)
    items = [mcp("/a/.mcp.json"), mcp("/b/.mcp.json"), mcp("/c/.mcp.json")]
    assert len(_dedup(items)) == 1


def test_dedup_keeps_personal_vs_plugin_distinct():
    a = Item(Host.CLAUDE, Kind.SKILL, "dup", Origin.PERSONAL, "/p1", True)
    b = Item(Host.CLAUDE, Kind.SKILL, "dup", Origin.PLUGIN, "/p2", True)
    assert len(_dedup([a, b])) == 2
