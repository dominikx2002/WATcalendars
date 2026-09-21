"""The one and only ICS writer.

Every faculty produces the same calendar format, so this is shared. What
differs per faculty (target directory, semester) comes from FacultySpec
and is passed in - it is data, not code.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Sequence

from watcalendars.core.logging import (
    ADDED,
    CHANGED,
    ERROR,
    INFO,
    OK,
    SUCCESS,
    UNCHANGED,
    WARNING,
    get_logger,
)
from watcalendars.core.models import Lesson
from watcalendars.core.paths import calendars_dir, ensure_dir

log = get_logger()

_ILLEGAL_FILENAME = re.compile(r'[<>:"\\|?*]')

try:  # Python 3.9+ with tzdata available
    from zoneinfo import ZoneInfo

    _WARSAW = ZoneInfo("Europe/Warsaw")
except Exception:  # pragma: no cover - fallback below handles it
    _WARSAW = None


def sanitize_filename(name: str) -> str:
    return _ILLEGAL_FILENAME.sub("_", name)


def _last_sunday(year: int, month: int) -> int:
    first_next = (
        datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    )
    last = first_next - timedelta(days=1)
    return last.day - ((last.weekday() + 1) % 7)


def _manual_warsaw_offset(naive: datetime) -> timedelta:
    """EU DST rules, used only when the tz database is unavailable."""
    year = naive.year
    dst_start = datetime(year, 3, _last_sunday(year, 3), 2, 0, 0)
    dst_end = datetime(year, 10, _last_sunday(year, 10), 3, 0, 0)
    return timedelta(hours=2) if dst_start <= naive < dst_end else timedelta(hours=1)


def to_utc_string(value: datetime) -> str:
    """Format a datetime as an ICS UTC stamp; naive means Europe/Warsaw."""
    if value is None:
        return ""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if _WARSAW is not None:
        return value.replace(tzinfo=_WARSAW).astimezone(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        )
    return (value - _manual_warsaw_offset(value)).strftime("%Y%m%dT%H%M%SZ")


def build_calendar(group_id: str, lessons: Iterable[Lesson]) -> str:
    """Render one group's lessons as an iCalendar document."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//WATcalendars//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{group_id}",
    ]

    for lesson in lessons:
        if not lesson.is_valid:
            continue

        description = []
        if lesson.full_subject:
            description.append(lesson.full_subject)
        if lesson.type_full:
            description.append(f"Rodzaj zajęć: {lesson.type_full}")
        if lesson.lesson_number:
            description.append(f"Numer zajęć: {lesson.lesson_number}")
        if lesson.lecturers:
            description.append("Prowadzący: " + "; ".join(lesson.lecturers))

        lines += [
            "BEGIN:VEVENT",
            f"DTSTART:{to_utc_string(lesson.start)}",
            f"DTEND:{to_utc_string(lesson.end)}",
            f"SUMMARY:{lesson.subject} {lesson.type}",
            f"LOCATION:{lesson.room}",
            "DESCRIPTION:" + "\\n".join(description),
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\n".join(lines)


def write_calendar(group_id: str, lessons: Sequence[Lesson], target_dir: str) -> str:
    """Write one .ics file; returns 'added', 'changed' or 'unchanged'."""
    ensure_dir(target_dir)
    path = os.path.join(target_dir, f"{sanitize_filename(group_id)}.ics")
    content = build_calendar(group_id, lessons)

    status = "added"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            status = "unchanged" if handle.read() == content else "changed"

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return status


def write_all(
    schedules: Dict[str, List[Lesson]], code: str, semester: str
) -> Dict[str, List[str]]:
    """Write every group's calendar and report what changed."""
    target_dir = calendars_dir(code, semester)
    existed = os.path.isdir(target_dir)
    ensure_dir(target_dir)

    log.info(f"{INFO} Saving ICS calendars into '{target_dir}'")
    log.debug(f"{INFO} Directory {'already existed' if existed else 'was created'}")

    summary = {"added": [], "changed": [], "unchanged": [], "skipped": []}

    for group_id in sorted(schedules):
        lessons = schedules.get(group_id) or []
        if not lessons:
            log.warning(f"{WARNING} No lessons for {group_id} - skipping")
            summary["skipped"].append(group_id)
            continue

        status = write_calendar(group_id, lessons, target_dir)
        summary[status].append(group_id)
        marker = {"added": ADDED, "changed": CHANGED, "unchanged": UNCHANGED}[status]
        log.debug(f"{OK} {group_id}: {marker} ({len(lessons)} events)")

    written = len(summary["added"]) + len(summary["changed"]) + len(summary["unchanged"])
    if written:
        log.info(
            f"{SUCCESS} Wrote {written} ICS files | "
            f"added: {len(summary['added'])} "
            f"changed: {len(summary['changed'])} "
            f"unchanged: {len(summary['unchanged'])} "
            f"skipped: {len(summary['skipped'])}"
        )
    else:
        log.error(f"{ERROR} No ICS files written.")

    return summary
