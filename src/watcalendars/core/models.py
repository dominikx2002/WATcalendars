"""Data contracts shared by every faculty.

`Lesson` is the only thing a schedule parser must produce, and the only
thing the ICS writer consumes. `FacultySpec` is the only thing that
differs between faculties.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional, Sequence, Union


@dataclass
class Lesson:
    """A single calendar event. Times are naive Europe/Warsaw local time."""

    start: datetime
    end: datetime
    subject: str
    type: str = ""
    type_full: str = ""
    room: str = ""
    lesson_number: str = ""
    full_subject: str = ""
    lecturers: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Lesson":
        """Build a Lesson from the loose dicts the legacy parsers return.

        Accepts the historical key aliases (room/location,
        lecturer/lecturers, full_subject/full_subject_name) so that
        parsers can be migrated one at a time.
        """
        lecturers = data.get("lecturers") or []
        if not lecturers and data.get("lecturer"):
            lecturers = [data["lecturer"]]

        return cls(
            start=data.get("start"),
            end=data.get("end"),
            subject=data.get("subject", ""),
            type=data.get("type", ""),
            type_full=data.get("type_full") or data.get("type", ""),
            room=data.get("room") or data.get("location", ""),
            lesson_number=str(data.get("lesson_number", "")),
            full_subject=(
                data.get("full_subject")
                or data.get("full_subject_name")
                or data.get("subject", "")
            ),
            lecturers=list(lecturers),
        )

    @property
    def is_valid(self) -> bool:
        return isinstance(self.start, datetime) and isinstance(self.end, datetime)


# A fetcher takes (identifier, url) pairs and returns {identifier: html}.
Fetcher = Callable[[Sequence[tuple], int, str], Dict[str, Optional[str]]]


@dataclass(frozen=True)
class FacultySpec:
    """Everything that makes one faculty different from another.

    Adding a faculty means adding one of these plus a parser - no new
    pipeline, no new writer, no new entry point.
    """

    code: str
    name: str
    groups_url: Union[str, Dict[str, str]]
    schedule_url: Union[str, Dict[str, str]]
    parse_groups: Optional[Callable]
    parse_schedule: Callable
    seasonal: bool = False
    concurrency: int = 10
    fetch_strategy: str = "browser"
    groups_fetch_strategy: Optional[str] = None
    custom_groups_job: Optional[Callable] = None
    notes: str = ""

    def url_for(self, which: str, semester: Optional[str]) -> str:
        """Resolve groups_url/schedule_url.

        Handles per-semester mappings and the {year} placeholder, which
        expands to the starting year of the current academic year.
        """
        from watcalendars.core.semester import academic_year

        source = self.groups_url if which == "groups" else self.schedule_url
        if isinstance(source, str):
            return source.replace("{year}", str(academic_year()))
        if semester is None:
            raise ValueError(f"{self.code}: {which} URL is per-semester but no semester given")
        try:
            return source[semester].replace("{year}", str(academic_year()))
        except KeyError:
            raise ValueError(
                f"{self.code}: no {which} URL for semester '{semester}' "
                f"(have: {', '.join(sorted(source))})"
            )

    @property
    def groups_fetcher(self) -> str:
        return self.groups_fetch_strategy or self.fetch_strategy
