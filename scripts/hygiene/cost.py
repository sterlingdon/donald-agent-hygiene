from .model import Item, Kind
from .normalize import norm_mcp_server

_HEAVY = {"github", "playwright", "playwrightextension", "framelinkfigmamcp", "figma",
          "postgres", "firecrawl", "browser", "puppeteer", "supabase"}

def estimate(item: Item) -> Item:
    if item.kind == Kind.SKILL:
        item.est_tokens = (len(item.name) + len(item.description)) // 4
        item.cost_band = "low"
    elif item.kind == Kind.MCP:
        key = norm_mcp_server(item.name)
        item.cost_band = "high" if any(h in key for h in _HEAVY) else "med"
        item.est_tokens = {"high": 15000, "med": 3000, "low": 800}[item.cost_band]
    elif item.kind == Kind.MEMORY:
        # est_tokens holds the line count; oversized memory files are flagged.
        try:
            with open(item.path, "r", encoding="utf-8", errors="replace") as f:
                item.est_tokens = sum(1 for _ in f)
        except (OSError, IsADirectoryError):
            item.est_tokens = 0
        item.cost_band = "high" if item.est_tokens > 200 else "low"
    return item
