from hygiene.normalize import skill_match_keys, parse_mcp_tool, norm_mcp_server

def test_skill_keys_plugin_namespaced():        # N1
    assert skill_match_keys("superpowers:brainstorming") == {"superpowers:brainstorming", "brainstorming"}

def test_skill_keys_bare():
    assert skill_match_keys("alpha") == {"alpha"}

def test_parse_mcp_tool():                        # N2
    assert parse_mcp_tool("mcp__playwright-extension__browser_click") == ("playwright-extension", "browser_click")
    assert parse_mcp_tool("Bash") is None
    assert parse_mcp_tool("mcp__noTool") is None

def test_norm_mcp_server_tolerates_space_and_case():   # N2 (Framelink Figma MCP)
    assert norm_mcp_server("Framelink Figma MCP") == norm_mcp_server("framelink_figma_mcp")
    assert norm_mcp_server("playwright-extension") == "playwrightextension"
