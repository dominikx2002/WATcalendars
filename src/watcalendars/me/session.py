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

# The left menu is a JS data structure; the schedule entries look like
#   '2026/2027 zimowy', 'javascript:executeCmm(328, 20264, 1, \'\');'
# mid is the "my schedule" menu (328), iid is the term - which changes
# every semester, so it is discovered, not hard-coded.
_MENU_CMD = re.compile(
    r"'([^']*?(\d{4})/\d{4}[^']*?(zimowy|letni)[^']*)'\s*,\s*"
    r"'javascript:executeCmm\((\d+),\s*(\d+)", re.I)

# "My schedule" vs "group schedule" etc.; the student's own plan is 328.
_MY_SCHEDULE_MID = 328


class LoginError(RuntimeError):
    """Login did not land on a logged-in page (bad credentials, lockout)."""


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_HEADERS)
    return s


def _decode(response: requests.Response) -> str:
    """Decode a response, UTF-8 first then iso-8859-2.

    The e-Dziekanat is inconsistent: the login page is iso-8859-2 but the
    logged-in schedule page (logged_inc.php) is UTF-8. Real Polish text
    in iso-8859-2 almost always contains byte sequences that are invalid
    UTF-8, so a strict UTF-8 attempt that succeeds means the page really
    was UTF-8; otherwise fall back to iso-8859-2.
    """
    body = response.content
    for charset in ("utf-8", "iso-8859-2"):
        try:
            return body.decode(charset)
        except UnicodeDecodeError:
            continue
    return body.decode("iso-8859-2", errors="replace")


def _fresh_sid(session: requests.Session, base: str, timeout: int) -> str:
    r = session.get(base + "/", timeout=timeout)
    r.raise_for_status()
    m = _SID.search(_decode(r))
    if not m:
        raise LoginError("could not find a session id on the login page "
                         "(did the login page change?)")
    return m.group(1)


def discover_plan_command(html: str, semester: str,
                          mid_pref: int = _MY_SCHEDULE_MID):
    """Find (mid, iid) for the newest term of the wanted semester.

    semester is "zima" or "lato"; the menu labels say "zimowy"/"letni".
    Returns (mid, iid) or None if the menu has no matching entry.
    """
    want = "zimowy" if semester == "zima" else "letni"
    candidates = []
    for m in _MENU_CMD.finditer(html):
        label, year, sem, mid, iid = m.groups()
        if sem.lower() != want:
            continue
        candidates.append((int(year), int(mid), int(iid)))
    if not candidates:
        return None
    # Prefer the "my schedule" menu; newest academic year within it.
    preferred = [c for c in candidates if c[1] == mid_pref] or candidates
    year, mid, iid = max(preferred, key=lambda c: c[0])
    return mid, iid


def login_and_fetch_plan(
    userid: str,
    password: str,
    base: str = BASE,
    timeout: int = 30,
    semester: str = "zima",
    mid: Optional[int] = None,
    iid: Optional[int] = None,
    exv: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> str:
    """Log in and return the schedule page HTML (iso-8859-2 decoded).

    Logs in, then opens "Mój rozkład zajęć" for the given semester. The
    menu ids (mid/iid) are discovered from the logged-in page unless
    passed explicitly; exv (group) defaults server-side to the student's
    own group. Raises LoginError on bad credentials or a lockout.
    """
    session = session or new_session()
    sid = _fresh_sid(session, base, timeout)

    form = {
        "formname": "login",
        "default_fun": "2",
        "userid": userid,
        "password": password,
        "view_width": "1280",
        "view_height": "800",
    }
    r = session.post(f"{base}/index.php?sid={sid}", data=form,
                     timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    landing = _decode(r)

    if _LOGIN_FORM.search(landing):
        raise LoginError("login failed - the response is still the login "
                         "form (wrong identifier/password, or the account "
                         "is locked for 30 min after 3 bad tries)")

    if looks_like_plan(landing):
        return landing  # already there

    if mid is None or iid is None:
        found = discover_plan_command(landing, semester)
        if not found:
            raise LoginError("logged in, but could not find the 'Mój "
                             "rozkład zajęć' entry in the menu for semester "
                             f"'{semester}'. Pass --mid/--iid explicitly.")
        d_mid, d_iid = found
        mid = mid if mid is not None else d_mid
        iid = iid if iid is not None else d_iid

    params = {"sid": sid, "mid": mid, "iid": iid, "pos": 0, "rdo": 1}
    if exv:
        params["exv"] = exv
    r = session.get(f"{base}/logged_inc.php", params=params, timeout=timeout)
    r.raise_for_status()
    return _decode(r)


def looks_like_plan(html: str) -> bool:
    """True if the HTML contains a weekday schedule header."""
    from watcalendars.me.parse_edziekanat import _weekday_of
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    return any(_weekday_of(tr) is not None for tr in soup.find_all("tr"))


_SHOW_GROUP = re.compile(r"showGroupPlan\('([A-Z0-9]{6,12})'\)")


def derive_exv(group_code: str) -> str:
    """Map a group code to the e-Dziekanat exv selector.

    The site builds it by dropping the 4-char prefix ("WCY2", "WME2")
    and swapping the next two chars:
      WCY22KC2S0 -> K2C2S0,  WCY22KB1S0 -> K2B1S0.
    """
    c = group_code
    if len(c) < 7:
        return c
    return c[5] + c[4] + c[6:]


def fetch_logged(session, base, sid, mid, iid, exv=None, timeout=30):
    """GET one logged_inc.php view (plan or chooser) and decode it."""
    params = {"sid": sid, "mid": mid, "iid": iid, "pos": 0, "rdo": 1}
    if exv:
        params["exv"] = exv
    r = session.get(f"{base}/logged_inc.php", params=params, timeout=timeout)
    r.raise_for_status()
    return _decode(r)


def login(userid, password, base=BASE, timeout=30, session=None):
    """Log in; return (session, sid). Raises LoginError on failure."""
    session = session or new_session()
    sid = _fresh_sid(session, base, timeout)
    form = {"formname": "login", "default_fun": "2", "userid": userid,
            "password": password, "view_width": "1280", "view_height": "800"}
    r = session.post(f"{base}/index.php?sid={sid}", data=form,
                     timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    if _LOGIN_FORM.search(_decode(r)):
        raise LoginError("login failed - wrong identifier/password, or the "
                         "account is locked for 30 min after 3 bad tries")
    return session, sid


def group_codes(chooser_html):
    """All study-group codes from the 'Plan zajęć grupy dziekańskiej' page."""
    return sorted(set(_SHOW_GROUP.findall(chooser_html)))
