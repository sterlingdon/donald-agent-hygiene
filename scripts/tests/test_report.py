from hygiene.report import render_html
from hygiene.model import Item, Finding, Severity, Kind, Host, Origin


def _f(name, sev, cmd=None):
    it = Item(Host.CLAUDE, Kind.SKILL, name, Origin.PERSONAL, "/p", True)
    return Finding(item=it, severity=sev, reasons=["never used"], suggested_cmd=cmd)


def test_html_has_sections_and_counts():
    html = render_html([_f("z1", Severity.GREEN), _f("z2", Severity.GREEN), _f("k", Severity.KEEP)],
                       meta={"host": "claude+codex", "generated": "2026-06-08"})
    assert "<html" in html and "🟢" in html
    assert "z1" in html and "z2" in html
    assert "2" in html  # green count


def test_escapes_html():
    html = render_html([_f("<script>", Severity.YELLOW)], meta={})
    assert "<script>" not in html.split("</head>")[-1] or "&lt;script&gt;" in html
