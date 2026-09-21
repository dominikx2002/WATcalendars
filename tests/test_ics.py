"""The ICS writer - output format is a contract with users' phones."""
from datetime import datetime

from watcalendars.core.models import Lesson
from watcalendars.store.ics import build_calendar, sanitize_filename, to_utc_string


def lesson(**kw):
    base = dict(
        start=datetime(2026, 1, 15, 8, 0),
        end=datetime(2026, 1, 15, 9, 35),
        subject="AiSD",
        type="(w)",
    )
    base.update(kw)
    return Lesson.from_dict(base)


def test_winter_time_is_utc_plus_one():
    assert to_utc_string(datetime(2026, 1, 15, 8, 0)) == "20260115T070000Z"


def test_summer_time_is_utc_plus_two():
    assert to_utc_string(datetime(2026, 7, 3, 13, 30)) == "20260703T113000Z"


def test_dst_boundaries():
    # last Sunday of March / October, just outside the transition
    assert to_utc_string(datetime(2026, 3, 29, 1, 0)) == "20260329T000000Z"
    assert to_utc_string(datetime(2026, 10, 25, 4, 0)) == "20261025T030000Z"


def test_calendar_envelope():
    text = build_calendar("WCY25XX1S0", [lesson()])
    assert text.startswith("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//WATcalendars//EN")
    assert "X-WR-CALNAME:WCY25XX1S0" in text
    assert text.endswith("END:VCALENDAR")
    assert text.count("BEGIN:VEVENT") == 1


def test_description_uses_escaped_newlines():
    text = build_calendar(
        "G",
        [
            lesson(
                full_subject="Algorytmy i struktury danych",
                type_full="Wykład",
                lesson_number="1/30",
                lecturers=["dr Jan Kowalski", "prof. Anna Nowak"],
            )
        ],
    )
    line = [l for l in text.split("\n") if l.startswith("DESCRIPTION:")][0]
    assert line == (
        "DESCRIPTION:Algorytmy i struktury danych\\nRodzaj zajęć: Wykład"
        "\\nNumer zajęć: 1/30\\nProwadzący: dr Jan Kowalski; prof. Anna Nowak"
    )


def test_lessons_without_times_are_dropped():
    text = build_calendar("G", [lesson(), Lesson.from_dict({"subject": "brak dat"})])
    assert text.count("BEGIN:VEVENT") == 1


def test_sanitize_filename_strips_illegal_characters():
    assert sanitize_filename('WCY<>:"|?*X') == "WCY_______X"
    assert sanitize_filename("SDRMXCSS24Z_-_Ceg") == "SDRMXCSS24Z_-_Ceg"
