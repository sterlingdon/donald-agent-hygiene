import tomllib
from hygiene.actions import remove_toml_server


def test_removes_table_and_subtable():
    text = ('[mcp_servers.a]\ncommand = "x"\n[mcp_servers.a.env]\nK = "v"\n\n'
            '[mcp_servers.b]\ncommand = "y"\n')
    data = tomllib.loads(remove_toml_server(text, "a"))
    assert "a" not in data["mcp_servers"] and data["mcp_servers"]["b"]["command"] == "y"


def test_remove_nonexistent_is_noop():
    text = '[mcp_servers.b]\ncommand = "y"\n'
    data = tomllib.loads(remove_toml_server(text, "a"))
    assert data["mcp_servers"]["b"]["command"] == "y"


def test_preserves_other_top_level_tables():
    text = '[model]\nname = "x"\n[mcp_servers.a]\ncommand = "z"\n[other]\nk = 1\n'
    data = tomllib.loads(remove_toml_server(text, "a"))
    assert "a" not in data.get("mcp_servers", {})
    assert data["model"]["name"] == "x" and data["other"]["k"] == 1
