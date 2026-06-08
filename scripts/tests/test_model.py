from hygiene.model import Item, Usage, Finding, Kind, Host, Origin, Severity

def test_item_defaults_and_mutability():
    it = Item(host=Host.CLAUDE, kind=Kind.SKILL, name="alpha",
              origin=Origin.PERSONAL, path="/x/SKILL.md", enabled=True)
    assert it.plugin is None and it.est_tokens == 0 and it.cost_band == "low"
    it.est_tokens = 42  # must be mutable (cost.py fills later)
    assert it.est_tokens == 42

def test_enum_values_are_strings():
    assert Severity.GREEN.value == "green"
    assert Kind.MCP.value == "mcp"

def test_finding_holds_reasons_list():
    it = Item(Host.CODEX, Kind.MCP, "neon", Origin.PLUGIN, "/p/.mcp.json", True)
    f = Finding(item=it, severity=Severity.YELLOW, reasons=["stale"])
    assert f.reasons == ["stale"] and f.usage is None
