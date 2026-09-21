"""WTC - Wydział Nowych Technologii i Chemii (Plansoft, Incapsula)."""
from watcalendars.core.models import FacultySpec
from watcalendars.faculties.plansoft import parse_groups
from watcalendars.parsers.schedule.wtc import parse_schedule

BASE = "https://wtc.wat.edu.pl/Plany"

SPEC = FacultySpec(
    code="wtc",
    name="Wydział Nowych Technologii i Chemii",
    groups_url=f"{BASE}/index.xml",
    schedule_url=f"{BASE}/{{group}}.pdf",
    parse_groups=parse_groups,
    parse_schedule=parse_schedule,
    seasonal=False,
    concurrency=10,
    fetch_strategy="browser",
    notes=(
        "BROKEN AT SOURCE: WTC now publishes PDFs only (22/22). The HTML parser cannot read them - needs a PDF parser."
    ),
)
