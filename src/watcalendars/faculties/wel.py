"""WEL - Wydział Elektroniki (Plansoft, behind Incapsula)."""
from watcalendars.core.models import FacultySpec
from watcalendars.faculties.plansoft import parse_groups
from watcalendars.parsers.schedule.wel import parse_schedule

BASE = "https://wel.wat.edu.pl/planyzajec"

SPEC = FacultySpec(
    code="wel",
    name="Wydział Elektroniki",
    groups_url={"lato": f"{BASE}/lato/index.xml", "zima": f"{BASE}/zima/index.xml"},
    schedule_url={
        "lato": f"{BASE}/lato/{{group}}.htm",
        "zima": f"{BASE}/zima/{{group}}.htm",
    },
    parse_groups=parse_groups,
    parse_schedule=parse_schedule,
    seasonal=True,
    concurrency=10,
    fetch_strategy="browser",
    notes="Moved from plany.wel.wat.edu.pl (now NXDOMAIN); Incapsula.",
)
