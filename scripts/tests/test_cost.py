from hygiene.cost import estimate
from hygiene.model import Item, Kind, Host, Origin

def _skill(desc):
    return Item(Host.CLAUDE, Kind.SKILL, "x", Origin.PERSONAL, "/p", True, description=desc)

def test_skill_tokens_from_metadata_len():
    it = _skill("a" * 200)
    estimate(it)
    assert it.est_tokens >= 50  # ~ (name+desc)/4

def test_mcp_band_known_heavy():
    it = Item(Host.CLAUDE, Kind.MCP, "Framelink Figma MCP", Origin.USER_CONFIG, "/p", True)
    estimate(it)
    assert it.cost_band == "high"

def test_mcp_band_default_med():
    it = Item(Host.CLAUDE, Kind.MCP, "obscure-thing", Origin.USER_CONFIG, "/p", True)
    estimate(it)
    assert it.cost_band == "med"
