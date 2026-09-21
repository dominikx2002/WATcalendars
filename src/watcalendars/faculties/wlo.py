"""WLO - Wydział Logistyki (Plansoft, aggressive Incapsula)."""
from watcalendars.core.models import FacultySpec
from watcalendars.faculties.plansoft import parse_groups
from watcalendars.parsers.schedule.wlo import parse_schedule

BASE = "https://wlo.wat.edu.pl/planzajec"

SPEC = FacultySpec(
    code="wlo",
    name="Wydział Logistyki",
    groups_url={"lato": f"{BASE}/letni/index.xml", "zima": f"{BASE}/zima/index.xml"},
    schedule_url={
        "lato": f"{BASE}/letni/{{group}}.htm",
        "zima": f"{BASE}/zima/{{group}}.htm",
    },
    parse_groups=parse_groups,
    parse_schedule=parse_schedule,
    seasonal=True,
    concurrency=1,
    fetch_strategy="browser_slow",
    notes="Incapsula; raw requests through the browser work, no rendering needed.",
)
