"""WTC - Wydział Nowych Technologii i Chemii (Plansoft, Incapsula)."""
from watcalendars.core.models import FacultySpec
from watcalendars.faculties import plansoft
from watcalendars.parsers.schedule.wtc import parse_schedule

BASE = "https://wtc.wat.edu.pl/Plany"


def parse_groups(xml_text):
    """WTC's index.xml now advertises .pdf for every group, but the .htm
    twins are still served (verified: 22/22). Accept the PDF entries and
    let the schedule URL fetch the HTML, which the parser can read."""
    return plansoft.parse_groups(xml_text, accept=("htm", "html", "pdf"))

SPEC = FacultySpec(
    code="wtc",
    name="Wydział Nowych Technologii i Chemii",
    groups_url=f"{BASE}/index.xml",
    schedule_url=f"{BASE}/{{group}}.htm",
    parse_groups=parse_groups,
    parse_schedule=parse_schedule,
    seasonal=False,
    concurrency=10,
    fetch_strategy="browser",
    notes=(
        "BROKEN AT SOURCE: WTC now publishes PDFs only (22/22). The HTML parser cannot read them - needs a PDF parser."
    ),
)
