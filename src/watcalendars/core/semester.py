"""Which semester are we in - decided in one place, overridable."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

WINTER = "zima"
SUMMER = "lato"


def current_semester(now: Optional[datetime] = None) -> str:
    """Return 'zima' or 'lato'.

    WATCALENDARS_SEMESTER overrides the calendar, which makes the whole
    pipeline reproducible when re-running an old scrape or testing.
    """
    override = os.environ.get("WATCALENDARS_SEMESTER")
    if override:
        value = override.strip().lower()
        if value not in (WINTER, SUMMER):
            raise ValueError(
                f"WATCALENDARS_SEMESTER must be '{WINTER}' or '{SUMMER}', got '{override}'"
            )
        return value

    month = (now or datetime.now()).month
    return WINTER if month >= 9 or month <= 2 else SUMMER
