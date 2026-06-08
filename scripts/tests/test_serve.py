import os, threading, urllib.request, urllib.error
from hygiene.serve import actionable_index, apply_one, render_interactive_html, build_server
from hygiene.model import Item, Finding, Severity, Kind, Host, Origin


def _f(name, sev, kind=Kind.SKILL, origin=Origin.PERSONAL, path="/p", host=Host.CLAUDE, plugin=None):
    it = Item(host, kind, name, origin, path, True, plugin=plugin)
    return Finding(item=it, severity=sev, reasons=["x"])


def test_actionable_index_filters():
    findings = [_f("g", Severity.GREEN), _f("y", Severity.YELLOW),
                _f("k", Severity.KEEP), _f("mem", Severity.YELLOW, kind=Kind.MEMORY)]
    idx = actionable_index(findings)
    names = [f.item.name for _, f in idx]
    assert names == ["g", "y"]                  # keep + memory excluded


def test_render_has_buttons_token_and_apply():
    html = render_interactive_html([_f("g", Severity.GREEN)], token="TOK123", meta={})
    assert "execute" in html and "TOK123" in html and "/apply?i=" in html
    assert "一键处置" in html


def test_apply_one_archives_temp_skill(tmp_path):
    sd = tmp_path / "skills" / "z"; sd.mkdir(parents=True); (sd / "SKILL.md").write_text("x")
    f = _f("z", Severity.GREEN, path=str(sd))
    r = apply_one([f], 0, backups=str(tmp_path / "bk"), home=str(tmp_path), dry_run=False)
    assert r.applied and not os.path.exists(sd)


def test_server_binds_localhost_get_200_post_needs_token():
    httpd, token = build_server([_f("g", Severity.GREEN)], backups="/tmp/x", home="/tmp")
    assert httpd.server_address[0] == "127.0.0.1"
    t = threading.Thread(target=httpd.serve_forever, daemon=True); t.start()
    port = httpd.server_address[1]
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as r:
            assert r.status == 200 and "处置" in r.read().decode()
        req = urllib.request.Request(f"http://127.0.0.1:{port}/apply?i=0", method="POST")
        try:
            urllib.request.urlopen(req)
            assert False, "POST without token should 403"
        except urllib.error.HTTPError as e:
            assert e.code == 403
    finally:
        httpd.shutdown()
