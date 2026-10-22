"""Log in to the WCY e-Dziekanat as one student and fetch their plan.

This is per-user and opt-in. Credentials are passed in by the caller
(from an environment variable or an interactive prompt) and are only
ever sent to the e-Dziekanat over HTTPS - they are never stored, logged
or written to disk by anything here.

The login is a plain HTML form:

  1. GET  /ed1/                     -> the form, whose action carries a
                                       fresh session id: index.php?sid=<SID>
  2. POST /ed1/index.php?sid=<SID>  with formname=login, userid, password,
                                       default_fun (1 = news, 2 = plan),
                                       view_width/height.

The site sits behind Imperva, which hands out cookies on the first GET;
a single requests.Session carries them through the POST, so no challenge
is triggered.
"""
from __future__ import annotations

import re
from typing import Optional

import requests

BASE = "https://s1.wcy.wat.edu.pl/ed1"

# One believable desktop Firefox, matching Accept-Language the site expects.
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64; rv:128.0) "
                   "Gecko/20100101 Firefox/128.0"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl,en-US;q=0.7,en;q=0.3",
}

_SID = re.compile(r'index\.php\?sid=([0-9a-f]{16,})', re.I)
_LOGIN_FORM = re.compile(r'name=["\']userid["\']', re.I)


class LoginError(RuntimeError):
    """Login did not land on a logged-in page (bad credentials, lockout)."""


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_HEADERS)
    return s


def _decode(response: requests.Response) -> str:
    # e-Dziekanat is iso-8859-2; trust that over requests' guess.
    return response.content.decode("iso-8859-2", errors="replace")


def _fresh_sid(session: requests.Session, base: str, timeout: int) -> str:
    r = session.get(base + "/", timeout=timeout)
    r.raise_for_status()
    m = _SID.search(_decode(r))
    if not m:
        raise LoginError("could not find a session id on the login page "
                         "(did the login page change?)")
    return m.group(1)


def login_and_fetch_plan(
    userid: str,
    password: str,
    base: str = BASE,
    timeout: int = 30,
    session: Optional[requests.Session] = None,
) -> str:
    """Log in and return the "Rozkład zajęć" page HTML (iso-8859-2 decoded).

    default_fun=2 asks the login to land straight on the schedule, so no
    extra navigation is needed. Raises LoginError if the result is still
    the login form (wrong credentials, or the 3-strikes 30-min lockout).
    """
    session = session or new_session()
    sid = _fresh_sid(session, base, timeout)

    form = {
        "formname": "login",
        "default_fun": "2",           # 2 = Rozkład zajęć, 1 = Aktualności
        "userid": userid,
        "password": password,
        "view_width": "1280",
        "view_height": "800",
    }
    r = session.post(f"{base}/index.php?sid={sid}", data=form,
                     timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    html = _decode(r)

    if _LOGIN_FORM.search(html):
        raise LoginError("login failed - the response is still the login "
                         "form (wrong identifier/password, or the account "
                         "is locked for 30 min after 3 bad tries)")
    return html


def looks_like_plan(html: str) -> bool:
    """True if the HTML contains a weekday schedule header."""
    from watcalendars.me.parse_edziekanat import _weekday_of
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    return any(_weekday_of(tr) is not None for tr in soup.find_all("tr"))
