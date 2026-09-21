"""Semester detection and the lesson data contract."""
from datetime import datetime

import pytest

from watcalendars.core.models import Lesson
from watcalendars.core.paths import calendars_dir, groups_file
from watcalendars.core.semester import current_semester


@pytest.mark.parametrize(
    "month,expected",
    [(1, "zima"), (2, "zima"), (3, "lato"), (8, "lato"), (9, "zima"), (12, "zima")],
)
def test_semester_by_month(month, expected, monkeypatch):
    monkeypatch.delenv("WATCALENDARS_SEMESTER", raising=False)
    assert current_semester(datetime(2026, month, 15)) == expected


def test_semester_env_override(monkeypatch):
    monkeypatch.setenv("WATCALENDARS_SEMESTER", "lato")
    assert current_semester(datetime(2026, 1, 1)) == "lato"


def test_semester_env_rejects_garbage(monkeypatch):
    monkeypatch.setenv("WATCALENDARS_SEMESTER", "wiosna")
    with pytest.raises(ValueError):
        current_semester()


def test_lesson_accepts_legacy_key_aliases():
    l = Lesson.from_dict(
        {
            "start": datetime(2026, 1, 1, 8),
            "end": datetime(2026, 1, 1, 9),
            "subject": "X",
            "location": "sala 5",
            "lecturer": "dr Y",
            "full_subject_name": "Przedmiot X",
        }
    )
    assert l.room == "sala 5"
    assert l.lecturers == ["dr Y"]
    assert l.full_subject == "Przedmiot X"
    assert l.is_valid


def test_lesson_without_times_is_invalid():
    assert not Lesson.from_dict({"subject": "X"}).is_valid


def test_paths_include_semester():
    assert groups_file("wel", "zima").endswith("wel_groups_zima_url.json")
    assert groups_file("wcy", None).endswith("wcy_groups_url.json")
    assert calendars_dir("wcy", "lato").endswith("wcy_calendars/wcy_calendars_lato")


@pytest.mark.parametrize(
    "date,expected",
    [
        (datetime(2026, 9, 1), 2026),   # new academic year starts in September
        (datetime(2026, 12, 31), 2026),
        (datetime(2027, 1, 15), 2026),  # still the 2026/27 year
        (datetime(2027, 8, 31), 2026),
        (datetime(2027, 9, 1), 2027),
    ],
)
def test_academic_year(date, expected):
    from watcalendars.core.semester import academic_year

    assert academic_year(date) == expected


def test_year_placeholder_is_expanded(monkeypatch):
    """WML's URLs carry {year}; a literal placeholder would 404."""
    from watcalendars.core.registry import get

    url = get("wml").url_for("groups", "zima")
    assert "{year}" not in url
    assert "_sem_zima/index.xml" in url
