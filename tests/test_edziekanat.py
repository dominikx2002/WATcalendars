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
    assert steg[0].type == "Laboratorium"


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
    def __init__(self, get_body, post_body):
        self.get_body, self.post_body = get_body, post_body
        self.posted = None
        self.headers = {}

    def get(self, url, timeout=None):
        return FakeResp(self.get_body)

    def post(self, url, data=None, timeout=None, allow_redirects=True):
        self.posted = (url, data)
        return FakeResp(self.post_body)


LOGIN_PAGE = ('<form action="index.php?sid=abcdef0123456789abcdef0123456789" '
              'method="post"><input name="userid"><input name="password"></form>')


def test_fresh_sid_extracted_from_form_action():
    fs = FakeSession(LOGIN_PAGE, "")
    assert S._fresh_sid(fs, S.BASE, 10) == "abcdef0123456789abcdef0123456789"


def test_login_failure_when_response_is_login_form():
    fs = FakeSession(LOGIN_PAGE, LOGIN_PAGE)  # POST returns the form again
    with pytest.raises(S.LoginError):
        S.login_and_fetch_plan("u", "p", session=fs)


def test_login_success_returns_plan_html_and_posts_default_fun_2():
    fs = FakeSession(LOGIN_PAGE, FIXTURE)
    html = S.login_and_fetch_plan("u", "p", session=fs)
    assert "CZWARTEK" in html
    assert fs.posted[1]["default_fun"] == "2"
    assert fs.posted[1]["userid"] == "u"
    assert S.looks_like_plan(html)
