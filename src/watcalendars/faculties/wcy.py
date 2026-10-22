"""WCY - Wydział Cybernetyki.

Runs its own Drupal application which renders the whole schedule server
side, so a plain GET is enough - no browser needed.
"""
from watcalendars.core.models import FacultySpec
from watcalendars.parsers.groups.wcy import parse_wcy_groups
from watcalendars.parsers.schedule.wcy import parse_schedule as _parse
from watcalendars.store.employees import load_employees

_employees = None


def parse_schedule(html):
    """WCY resolves lecturer names against the USOS employee list."""
    global _employees
    if _employees is None:
        _employees = load_employees()
    return _parse(html, _employees)


SPEC = FacultySpec(
    code="wcy",
    name="Wydział Cybernetyki",
    groups_url="https://planzajec.wcy.wat.edu.pl/rozklad",
    schedule_url="https://planzajec.wcy.wat.edu.pl/pl/rozklad?grupa_id={group}",
    parse_groups=parse_wcy_groups,
    parse_schedule=parse_schedule,
    seasonal=False,
    # One request every 4-6 s: concurrency=8 got the Pi's home IP banned.
    concurrency=1,
    delay=4,
    # Sequential, so 3 refusals in a row already mean the address is
    # banned - stop knocking instead of deepening the ban.
    waf_threshold=3,
    fetch_strategy="http",
    notes="Behind Incapsula since Oct 2026; scraped slowly from a residential IP (Raspberry Pi)",
)
