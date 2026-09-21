"""IOE - Instytut Optoelektroniki (Plansoft, behind Incapsula).

IOE keeps a single folder regardless of semester: plany/zima/ is a 404
and plany/lato/ currently holds the WINTER plan (its period field reads
"IOE-Zima2026"). Treating it as non-seasonal is what actually works;
revisit if the faculty ever starts publishing both.

The index also lists four PDFs that are not group schedules at all
(Siatka Godzin Dydaktycznych, Harmonogram RA, PLAN_WAT) - the default
HTML-only filter drops them, which is correct here.
"""
from watcalendars.core.models import FacultySpec
from watcalendars.faculties.plansoft import parse_groups
from watcalendars.parsers.schedule.ioe import parse_schedule

BASE = "https://ioe.wat.edu.pl/plany/lato"

SPEC = FacultySpec(
    code="ioe",
    name="Instytut Optoelektroniki",
    groups_url=f"{BASE}/index.xml",
    schedule_url=f"{BASE}/{{group}}.htm",
    parse_groups=parse_groups,
    parse_schedule=parse_schedule,
    seasonal=False,
    concurrency=8,
    fetch_strategy="browser",
    notes="Single folder for both semesters (plany/lato holds the winter plan).",
)
