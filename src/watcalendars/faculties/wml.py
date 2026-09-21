"""WML - Wydział Mechatroniki, Uzbrojenia i Lotnictwa.

The group list lives on a WordPress page that links to a Plansoft
index.xml; the legacy parser already copes with both shapes, so it is
kept rather than assuming one.
"""
from watcalendars.core.models import FacultySpec
from watcalendars.parsers.groups.wml import parse_wml_groups
from watcalendars.parsers.schedule.wml import parse_schedule

SPEC = FacultySpec(
    code="wml",
    name="Wydział Mechatroniki, Uzbrojenia i Lotnictwa",
    groups_url="https://wml.wat.edu.pl/rozklady-zajec/",
    schedule_url=(
        "https://wml.wat.edu.pl/wp-content/uploads/rozklady_zajec/"
        "2025_sem_lato/{group}.htm"
    ),
    parse_groups=parse_wml_groups,
    parse_schedule=parse_schedule,
    seasonal=False,
    concurrency=6,
    fetch_strategy="browser_slow",
    notes=(
        "Source appears unpublished: the site only lists 2025/26 lato, and that page no longer links any plans. Schedule URL pins an old folder."
    ),
)
