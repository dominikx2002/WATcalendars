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
    concurrency=8,
    fetch_strategy="http",
    notes="Drupal, server-side rendered; plain HTTP verified working.",
)
