import time
from hygiene.classify import classify
from hygiene.model import Item, Kind, Host, Origin, Severity
from hygiene.normalize import skill_match_keys

NOW = time.time()


def _skill(host, name):
    return Item(host, Kind.SKILL, name, Origin.PERSONAL, "/p", True,
                match_keys=frozenset(skill_match_keys(name)))


def test_codex_never_used_skill_is_yellow_not_green():
    it = _skill(Host.CODEX, "somecxskill")
    f = [x for x in classify([it], {}, {}, NOW, 90) if x.item is it][0]
    assert f.severity == Severity.YELLOW   # Codex usage is unreliable -> never auto-clean


def test_cc_never_used_skill_is_yellow():
    it = _skill(Host.CLAUDE, "someccskill")
    f = [x for x in classify([it], {}, {}, NOW, 90) if x.item is it][0]
    assert f.severity == Severity.YELLOW   # B: review-only — usage detection is limited
