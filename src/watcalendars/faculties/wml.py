"""WML - Wydział Mechatroniki, Uzbrojenia i Lotnictwa.

Publishes Plansoft exports under a dated folder rather than a fixed
path: <year>_sem_<semester>, where <year> is the starting year of the
academic year. The old spec pinned "2025_sem_lato" and therefore went
stale; {year} is expanded at run time instead.
"""
from watcalendars.core.models import FacultySpec
from watcalendars.faculties.plansoft import parse_groups
from watcalendars.parsers.schedule.wml import parse_schedule

BASE = "https://wml.wat.edu.pl/wp-content/uploads/rozklady_zajec"

SPEC = FacultySpec(
    code="wml",
    name="Wydział Mechatroniki, Uzbrojenia i Lotnictwa",
    groups_url={
        "zima": f"{BASE}/{{year}}_sem_zima/index.xml",
        "lato": f"{BASE}/{{year}}_sem_lato/index.xml",
    },
    schedule_url={
        "zima": f"{BASE}/{{year}}_sem_zima/{{group}}.htm",
        "lato": f"{BASE}/{{year}}_sem_lato/{{group}}.htm",
    },
    parse_groups=parse_groups,
    parse_schedule=parse_schedule,
    seasonal=True,
    concurrency=6,
    fetch_strategy="browser",
    notes="Plansoft under a dated folder; {year} = start of academic year.",
)
