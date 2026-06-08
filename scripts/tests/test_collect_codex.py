from hygiene.collect_codex import collect
from hygiene.model import Kind, Origin

def test_codex_skills_and_mcp(fake_home):
    items = collect(str(fake_home / ".codex"))
    sk = {i.name: i for i in items if i.kind == Kind.SKILL}
    mc = {i.name: i for i in items if i.kind == Kind.MCP}
    assert sk["codexalpha"].origin == Origin.PERSONAL and sk["codexalpha"].enabled is True
    assert sk["sentry"].origin == Origin.CATALOG and sk["sentry"].enabled is False   # curated
    assert mc["node_repl"].origin == Origin.USER_CONFIG

def test_missing_codex_dir(tmp_path):
    assert collect(str(tmp_path / "nope")) == []
