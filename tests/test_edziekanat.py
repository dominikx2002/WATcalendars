"""e-Dziekanat parser + login flow, on synthetic HTML (no personal data)."""
from datetime import datetime

import pytest

from watcalendars.me import parse_edziekanat as P
from watcalendars.me import session as S


# A minimal plan: one weekday (Czwartek) with 5 week-date columns and a
# few block rows. iso-8859-2 details don't matter here - ASCII only.
FIXTURE = """
<html><body><table>
<tr>
  <td>CZWARTEK</td><td>nr bloku</td>
  <td>01X</td><td>08X</td><td>15X</td><td>22X</td><td>29X</td>
</tr>
<tr>
  <td>1</td><td>08:00 09:35</td>
  <td title="Steganografia - dr Kowalski (Laboratorium)">St</td>
  <td title="Analiza - dr Nowak (Wyklad)" rowspan="2">An</td>
  <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
</tr>
<tr>
  <td>2</td><td>09:50 11:25</td>
  <td title="Steganografia - dr Kowalski (Laboratorium)">St</td>
  <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
</tr>
<tr>
  <td>3</td><td>11:40 13:15</td>
  <td title="- (Studium Szkol. Wojs.)">-</td>
  <td title="Sieci - dr Lis; dr Mak (Projekt)">Si</td>
  <td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>
</tr>
</table></body></html>
"""


def _by(lessons):
    return sorted(lessons, key=lambda x: (x.start, x.subject))


SRODA_FIXTURE = """
<html><body><table>
<tr><td>ŚRODA</td><td>nr</td><td>01X</td><td>08X</td><td>15X</td><td>22X</td><td>29X</td></tr>
<tr><td>1</td><td>08:00 09:35</td>
<td title="Kryptologia - dr Lis (Wyklad)">K</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
</table>
<table>
<tr><td>PIĄTEK</td><td>nr</td><td>03X</td><td>10X</td><td>17X</td><td>24X</td><td>31X</td></tr>
<tr><td>1</td><td>08:00 09:35</td>
<td title="Sieci - dr Mak (Lab)">S</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
</table></body></html>
"""


def test_polish_weekday_names_sroda_piatek_are_parsed():
    # regression: 'ŚRODA' and 'PIĄTEK' headers were missed because of their
    # diacritics, so those whole sections were dropped (and in real data
    # their classes piled onto the previous day). Both must now be read.
    lessons = P.parse(SRODA_FIXTURE, academic_start_year=2026)
    subs = {x.subject for x in lessons}
    assert "Kryptologia" in subs   # from the ŚRODA section
    assert "Sieci" in subs         # from the PIĄTEK section


def test_norm_strips_diacritics():
    from bs4 import BeautifulSoup
    cell = BeautifulSoup("<td>ŚRODA</td>", "html.parser").td
    assert P._norm(cell) == "RODA"
    cell = BeautifulSoup("<td>PIĄTEK</td>", "html.parser").td
    assert P._norm(cell) == "PITEK"


def test_dates_use_roman_months_and_year_rollover():
    # IX-XII -> start year; I-II -> next year
    assert P._col_date("28IX", 2026).isoformat() == "2026-09-28"
    assert P._col_date("04I", 2026).isoformat() == "2027-01-04"
    assert P._col_date("22II", 2026).isoformat() == "2027-02-22"
    assert P._col_date("notadate", 2026) is None


def test_title_split():
    assert P._split_title("Steg - dr Kowalski (Lab)") == ("Steg", ["dr Kowalski"], "Lab")
    s, people, t = P._split_title("Sieci - dr Lis; dr Mak (Projekt)")
    assert s == "Sieci" and people == ["dr Lis", "dr Mak"] and t == "Projekt"


def test_parse_extracts_lessons_with_dates_and_times():
    lessons = _by(P.parse(FIXTURE, academic_start_year=2026))
    # Steganografia on 1 Oct spans block 1+2 -> merged 08:00-11:25
    steg = [x for x in lessons if x.subject == "Steganografia"]
    assert len(steg) == 1
    assert steg[0].start == datetime(2026, 10, 1, 8, 0)
    assert steg[0].end == datetime(2026, 10, 1, 11, 25)
    assert steg[0].type_full == "Laboratorium"
    assert steg[0].type == "(L)"


def _cell(title, code, typ, room):
    """A filled cell as the real page renders it: a nested table whose
    inner <td>s repeat the title."""
    return (f'<td title="{title}"><center><table title="{title}">'
            f'<tr><td title="{title}">{code}<br>({typ})<br>{room}</td></tr>'
            f'<tr><td title="{title}">X</td></tr>'
            f'<tr><td title="{title}">[1]</td></tr></center></table></td>')


_E = "<td>&nbsp;</td>"
_PSBI_C = _cell("Projektowanie - mgr Czer (Wykład)", "PsbI", "w", "307 S")
_PSBI_G = _cell("Projektowanie - mgr Giro (Wykład)", "PsbI", "w", "307 S")
_WF = _cell("Wychowanie - mgr Ol (Ćwiczenia)", "WF", "ć", "-")

# Regression: the inner <tr>s of those nested tables were counted as
# schedule rows, so cells slid onto the wrong block (a lecture twice).
NESTED_FIXTURE = (
    '<html><body><table>'
    '<tr><th rowspan="6">PIĄTEK</th><td>nr</td><td>czas</td>'
    '<td>02X</td><td>09X</td><td>16X</td><td>23X</td><td>30X</td></tr>'
    '<tr><td>2</td><td>09:50 11:25</td>' + _E + _PSBI_C + _E * 3 + '</tr>'
    '<tr><td>3</td><td>11:40 13:15</td>' + _WF + _E * 2 + _WF + _E + '</tr>'
    '<tr><td>4</td><td>13:30 15:05</td>' + _E * 5 + '</tr>'
    '<tr><td>5</td><td>16:00 17:35</td>' + _PSBI_G + _E * 2 + _PSBI_G + _E + '</tr>'
    '<tr><td>6</td><td>17:50 19:25</td>' + _E * 5 + '</tr>'
    '</table></body></html>'
)


def test_nested_cell_tables_keep_cells_on_their_row():
    lessons = P.parse(NESTED_FIXTURE, academic_start_year=2026)
    got = sorted((x.start, x.end, x.subject, x.type) for x in lessons)
    assert got == [
        (datetime(2026, 10, 2, 11, 40), datetime(2026, 10, 2, 13, 15), "WF", "(ć)"),
        (datetime(2026, 10, 2, 16, 0), datetime(2026, 10, 2, 17, 35), "PsbI", "(w)"),
        (datetime(2026, 10, 9, 9, 50), datetime(2026, 10, 9, 11, 25), "PsbI", "(w)"),
        (datetime(2026, 10, 23, 11, 40), datetime(2026, 10, 23, 13, 15), "WF", "(ć)"),
        (datetime(2026, 10, 23, 16, 0), datetime(2026, 10, 23, 17, 35), "PsbI", "(w)"),
    ]
    psbi = [x for x in lessons if x.subject == "PsbI"][0]
    assert psbi.full_subject == "Projektowanie" and psbi.type_full == "Wykład"


def test_type_abbr():
    assert P._type_abbr("Wykład") == "w"
    assert P._type_abbr("Ćwiczenia") == "ć"
    assert P._type_abbr("Egzamin poprawkowy") == "Ep"
    assert P._type_abbr("Laboratorium") == "L"


def test_rowspan_class_spans_two_blocks():
    lessons = P.parse(FIXTURE, academic_start_year=2026)
    an = [x for x in lessons if x.subject == "Analiza"]
    assert len(an) == 1
    # the rowspan=2 cell sits in the 08X column -> 8 Oct, blocks 1+2
    assert an[0].start == datetime(2026, 10, 8, 8, 0)
    assert an[0].end == datetime(2026, 10, 8, 11, 25)


def test_military_placeholder_is_skipped():
    lessons = P.parse(FIXTURE, academic_start_year=2026)
    assert all(x.subject != "-" for x in lessons)
    assert all(x.subject for x in lessons)


def test_multiple_teachers_become_a_list():
    lessons = P.parse(FIXTURE, academic_start_year=2026)
    sieci = [x for x in lessons if x.subject == "Sieci"][0]
    assert sieci.lecturers == ["dr Lis", "dr Mak"]
    assert sieci.start == datetime(2026, 10, 8, 11, 40)  # second date column


def test_rooms_off_by_default():
    lessons = P.parse(FIXTURE, academic_start_year=2026)
    assert all(x.room == "" for x in lessons)


# --- login flow (mocked, no network) ---------------------------------------

class FakeResp:
    def __init__(self, body, status=200):
        self.content = body.encode("iso-8859-2")
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self, get_body, post_body, nav_body=None):
        self.get_body, self.post_body = get_body, post_body
        self.nav_body = nav_body
        self.posted = None
        self.gets = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.gets.append((url, params))
        # first GET is the login page; a later GET with params is the nav
        if params is not None and self.nav_body is not None:
            return FakeResp(self.nav_body)
        return FakeResp(self.get_body)

    def post(self, url, data=None, timeout=None, allow_redirects=True):
        self.posted = (url, data)
        return FakeResp(self.post_body)


LOGIN_PAGE = ('<form action="index.php?sid=abcdef0123456789abcdef0123456789" '
              'method="post"><input name="userid"><input name="password"></form>')


MENU = ("prefix '2026/2027 zimowy', 'javascript:executeCmm(328, 20264, 1, \\'\\');' "
        "and '2025/2026 letni', 'javascript:executeCmm(328, 20255, 1, \\'\\');' "
        "and '2025/2026 zimowy', 'javascript:executeCmm(328, 20254, 1, \\'\\');' "
        "and group menu '2026/2027 zimowy', 'javascript:executeCmm(327, 20261, 1, \\'\\');'")


def test_discover_picks_my_schedule_newest_winter_term():
    assert S.discover_plan_command(MENU, "zima") == (328, 20264)


def test_discover_picks_summer_term():
    assert S.discover_plan_command(MENU, "lato") == (328, 20255)


def test_discover_returns_none_when_absent():
    assert S.discover_plan_command("no menu here", "zima") is None


def test_fetch_logged_retries_on_connection_error(monkeypatch):
    import requests as _rq
    calls = {"n": 0}
    class Resp:
        content = "<html>CZWARTEK</html>".encode("utf-8")
        def raise_for_status(self): pass
    class Sess:
        def get(self, url, params=None, timeout=None):
            calls["n"] += 1
            if calls["n"] < 3:
                raise _rq.ConnectionError("Remote end closed connection")
            return Resp()
    monkeypatch.setattr(S.time if hasattr(S, "time") else __import__("time"),
                        "sleep", lambda s: None)
    html = S.fetch_logged(Sess(), S.BASE, "sid", 328, 20264, retries=3)
    assert "CZWARTEK" in html and calls["n"] == 3


def test_derive_exv():
    assert S.derive_exv("WCY22KC2S0") == "K2C2S0"
    assert S.derive_exv("WCY22KB1S0") == "K2B1S0"
    assert S.derive_exv("WME23BE1S1") == "B3E1S1"


def test_group_codes_from_chooser():
    chooser = ("x <a href=\"javascript:showGroupPlan('WCY22KC2S0');\">g</a> "
               "<a href=\"javascript:showGroupPlan('WME26BX4S1');\">g</a> "
               "<a href=\"javascript:showGroupPlan('WCY22KC2S0');\">dup</a>")
    assert S.group_codes(chooser) == ["WCY22KC2S0", "WME26BX4S1"]


def test_decode_prefers_utf8_then_iso88592():
    class R:
        def __init__(self, raw): self.content = raw
    # 'ą' in UTF-8
    assert S._decode(R("Zarz\u0105dzanie".encode("utf-8"))) == "Zarz\u0105dzanie"
    # 'ł' (0xB3) in iso-8859-2 is invalid UTF-8 -> falls back
    assert S._decode(R("rozk\u0142ad".encode("iso-8859-2"))) == "rozk\u0142ad"


def test_fresh_sid_extracted_from_form_action():
    fs = FakeSession(LOGIN_PAGE, "")
    assert S._fresh_sid(fs, S.BASE, 10) == "abcdef0123456789abcdef0123456789"


def test_login_failure_when_response_is_login_form():
    fs = FakeSession(LOGIN_PAGE, LOGIN_PAGE)  # POST returns the form again
    with pytest.raises(S.LoginError):
        S.login_and_fetch_plan("u", "p", session=fs)


def test_login_landing_is_plan_returned_directly():
    # if login lands straight on the schedule, no navigation GET is made
    fs = FakeSession(LOGIN_PAGE, FIXTURE)
    html = S.login_and_fetch_plan("u", "p", session=fs)
    assert "CZWARTEK" in html
    assert fs.posted[1]["default_fun"] == "2"
    assert S.looks_like_plan(html)


def test_login_then_navigates_to_plan_via_menu():
    landing = "<html>news " + MENU + "</html>"   # not a plan, has the menu
    fs = FakeSession(LOGIN_PAGE, landing, nav_body=FIXTURE)
    html = S.login_and_fetch_plan("u", "p", semester="zima", session=fs)
    assert S.looks_like_plan(html)
    # navigation GET carried the discovered mid/iid
    nav = [g for g in fs.gets if g[1] is not None][0]
    assert nav[1]["mid"] == 328 and nav[1]["iid"] == 20264
