"""WIM - Wydział Inżynierii Mechanicznej (Plansoft, plain HTTP)."""
from watcalendars.core.models import FacultySpec
from watcalendars.faculties.plansoft import parse_groups
from watcalendars.parsers.schedule.wim import parse_schedule

BASE = "https://www.wim.wat.edu.pl/wp-content/uploads/rozklady"

SPEC = FacultySpec(
    code="wim",
    name="Wydział Inżynierii Mechanicznej",
    groups_url={"lato": f"{BASE}/lato/index.xml", "zima": f"{BASE}/zima/index.xml"},
    schedule_url={
        "lato": f"{BASE}/lato/{{group}}.htm",
        "zima": f"{BASE}/zima/{{group}}.htm",
    },
    parse_groups=parse_groups,
    parse_schedule=parse_schedule,
    seasonal=True,
    concurrency=8,
    fetch_strategy="http",
    notes="Static Plansoft files, no WAF; plain HTTP verified working.",
)
