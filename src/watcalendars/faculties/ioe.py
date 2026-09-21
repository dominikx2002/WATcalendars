"""IOE - Instytut Optoelektroniki (Plansoft, behind Incapsula)."""
from watcalendars.core.models import FacultySpec
from watcalendars.faculties.plansoft import parse_groups
from watcalendars.parsers.schedule.ioe import parse_schedule

BASE = "https://ioe.wat.edu.pl/plany"

SPEC = FacultySpec(
    code="ioe",
    name="Instytut Optoelektroniki",
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
    notes=(
        "Publishes only one semester at a time; the 'lato' folder currently holds the WINTER plan (period says IOE-Zima2026). 4 of 22 entries are PDFs."
    ),
)
