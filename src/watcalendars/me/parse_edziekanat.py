"""Parse the WCY e-Dziekanat "Rozkład zajęć" page into Lessons.

The page is one big HTML table per weekday. Columns are the concrete
dates of that weekday across the whole semester (e.g. CZWARTEK -> 01X,
08X, 15X ... as 1 Oct, 8 Oct ...), rows are the lesson blocks (1..7),
and a filled cell carries the class in its `title` attribute:
"<subject> - <teacher(s)> (<type>)". A class that lasts two blocks or
two weeks is one cell with rowspan/colspan, so the table is expanded
into a matrix (rowspan/colspan honoured) before anything is read off it.

Every filled cell holds a nested 3-4 row <table> whose <td>s repeat the
lesson title. Those inner <tr>s must not count as schedule rows: they
shifted the grid (the weekday label's rowspan=8 no longer covered the
day) and lessons landed on the wrong block, e.g. a duplicated lecture.

Encoding: the server sends iso-8859-2; decode the raw bytes with that,
not utf-8, or every Polish diacritic turns to mojibake.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from watcalendars.core.models import Lesson

_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
          "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12}

# First semester runs Sep-Feb: Sep-Dec are year Y, Jan-Feb are Y+1. The
# summer semester (Feb-Sep) is all one calendar year. academic_start_year
# is the year the autumn term began.
_WEEKDAYS = [("PONIEDZIA", 0), ("WTOREK", 1), ("RODA", 2), ("CZWARTEK", 3),
             ("PITEK", 4), ("SOBOTA", 5), ("NIEDZIELA", 6)]

_TIME = re.compile(r"([01]?\d|2[0-3])[:.](\d{2})\D+([01]?\d|2[0-3])[:.](\d{2})")
_DATECOL = re.compile(r"(\d{1,2})([IVX]+)$")


def _norm(cell) -> str:
    """Uppercase, ASCII-only key: strips whitespace AND diacritics (Ś, Ą,
    Ł...) and any mojibake, so weekday names like 'ŚRODA'/'PIĄTEK' match on
    their ASCII skeleton ('RODA'/'PITEK'). Without this, Wed and Fri were
    missed and their classes piled onto Tue/Thu."""
    return re.sub(r"[^A-Z0-9]", "", cell.get_text("", strip=True).upper())


def _text(cell) -> str:
    return re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()


def _col_date(token: str, start_year: int) -> Optional[date]:
    m = _DATECOL.fullmatch(token)
    if not m:
        return None
    month = _ROMAN.get(m.group(2))
    if not month:
        return None
    year = start_year if month >= 9 else start_year + 1
    try:
        return date(year, month, int(m.group(1)))
    except ValueError:
        return None


def _weekday_of(tr) -> Optional[int]:
    cells = tr.find_all(["td", "th"], recursive=False)
    if not cells:
        return None
    first = _norm(cells[0])
    for key, wd in _WEEKDAYS:
        if first.startswith(key):
            dates = sum(1 for c in cells if _DATECOL.fullmatch(_norm(c)))
            if dates >= 5:
                return wd
    return None


def _expand(rows) -> List[list]:
    """Render <tr> rows into a matrix of tags, honouring row/colspan."""
    grid: List[Dict[int, object]] = []
    for r, tr in enumerate(rows):
        while len(grid) <= r:
            grid.append({})
        col = 0
        for cell in tr.find_all(["td", "th"], recursive=False):
            while grid[r].get(col) is not None:
                col += 1
            colspan = int(cell.get("colspan", 1) or 1)
            rowspan = int(cell.get("rowspan", 1) or 1)
            for dr in range(rowspan):
                while len(grid) <= r + dr:
                    grid.append({})
                for dc in range(colspan):
                    grid[r + dr][col + dc] = cell
            col += colspan
    width = max((max(d) + 1 if d else 0) for d in grid) if grid else 0
    return [[row.get(c) for c in range(width)] for row in grid]


def _split_title(title: str):
    """'Subject - Teacher; Teacher (Type)' -> (subject, [teachers], type)."""
    t = title.strip()
    m = re.search(r"\(([^()]*)\)\s*$", t)
    type_ = m.group(1).strip() if m else ""
    head = t[: m.start()].strip() if m else t
    head = re.sub(r"\s+-$", "", head)  # "Subject -  (Type)": no teacher
    if " - " in head:
        subject, teachers = head.split(" - ", 1)
    else:
        subject, teachers = head, ""
    people = [p.strip() for p in re.split(r";|/", teachers) if p.strip()]
    return subject.strip(), people, type_


def _short_code(cell) -> str:
    """Abbreviation shown in the cell, e.g. 'BsIP' from 'BsIP (w) 307 S'."""
    m = re.match(r"^(\S+)\s*\(", _text(cell))
    return m.group(1).strip() if m else ""


_TYPE_ABBR = [("wyklad", "w"), ("cwicz", "ć"), ("laborat", "L"),
              ("projekt", "P"), ("seminar", "S"), ("lektorat", "Lk"),
              ("egzamin poprawkowy", "Ep"), ("egzamin", "E"),
              ("zal popr", "Zp"), ("zaliczenie", "Zal")]
_FOLD = str.maketrans("łśżźąęóćń", "lszzaeocn")


def _type_abbr(full_type: str) -> str:
    folded = re.sub(r"[^a-z ]", "", full_type.lower().translate(_FOLD))
    for needle, abbr in _TYPE_ABBR:
        if needle in folded:
            return abbr
    return full_type[:1].lower() if full_type else ""


def _inside_lesson_cell(tr) -> bool:
    """True for the little <tr>s nested inside a filled lesson cell."""
    return any(td.get("title") for td in tr.find_parents("td"))


def _room_from_cell(cell, type_: str) -> str:
    """Room and building, e.g. "307 S", "203 65", "AW 7", "ST.nr 1(PWC3)".

    In the full view a filled cell holds a nested table whose first
    inner cell reads "<code><br>(<type>)<br><room building>"; the room
    is whatever follows the type. "-" means no room. Without the nested
    table (the "Miniatura" view packs room, building and a teacher
    abbreviation together) only a clear "<number>[ <LETTER>]" is taken,
    because a wrong LOCATION is worse than none.
    """
    inner = cell.find("td")
    if inner is not None:
        m = re.match(r"^\S+\s*\(\s*[^()]*?\s*\)\s*(.*)$", _text(inner))
        room = m.group(1).strip() if m else ""
        return "" if room in ("", "-") else room
    txt = _text(cell)
    m = re.search(r"\([^()]*\)\s*(.+)$", txt)
    tail = m.group(1).strip() if m else ""
    mroom = re.search(r"(\d{1,3}(?:\s?[A-Z])?)", tail)
    return mroom.group(1).strip() if mroom else ""


def parse(html: str, academic_start_year: int = 2026,
          with_rooms: bool = True) -> List[Lesson]:
    soup = BeautifulSoup(html, "html.parser")
    rows = [tr for tr in soup.find_all("tr")
            if not _inside_lesson_cell(tr)]
    sections = [(i, _weekday_of(tr)) for i, tr in enumerate(rows)]
    sections = [(i, wd) for i, wd in sections if wd is not None]

    raw: List[dict] = []
    for idx, (start, wd) in enumerate(sections):
        end = sections[idx + 1][0] if idx + 1 < len(sections) else len(rows)
        grid = _expand(rows[start:end])
        if not grid:
            continue

        col_date: Dict[int, date] = {}
        for c, cell in enumerate(grid[0]):
            if cell is None:
                continue
            dt = _col_date(_norm(cell), academic_start_year)
            if dt:
                col_date[c] = dt
        if not col_date:
            continue
        date_cols = sorted(col_date)

        # row -> (block_number, start_time, end_time), read from the
        # columns to the left of the first date column.
        row_block: Dict[int, Optional[tuple]] = {}
        current = None
        for r in range(1, len(grid)):
            block = None
            times = None
            for c in range(0, date_cols[0]):
                cell = grid[r][c]
                if cell is None:
                    continue
                txt = _text(cell)
                mt = _TIME.search(txt)
                if mt:
                    times = (time(int(mt.group(1)), int(mt.group(2))),
                             time(int(mt.group(3)), int(mt.group(4))))
                mb = re.fullmatch(r"(\d)", txt)
                if mb:
                    block = int(mb.group(1))
            if times:
                current = (block, times[0], times[1])
            row_block[r] = current

        # title cells -> raw lessons; remember first/last matrix row per cell
        span: Dict[tuple, list] = {}
        for r in range(1, len(grid)):
            for c in date_cols:
                cell = grid[r][c] if c < len(grid[r]) else None
                if cell is None:
                    continue
                title = cell.get("title")
                if not title or "(" not in title:
                    continue
                subject, _people, _type = _split_title(title)
                if not subject or subject == "-":
                    continue  # military-study placeholder cells
                key = (id(cell), c)
                if key not in span:
                    span[key] = [r, r]
                else:
                    span[key][1] = r

        for (_cid, c), (r0, r1) in span.items():
            cell = grid[r0][c]
            subject, people, type_ = _split_title(cell.get("title"))
            b0 = row_block.get(r0)
            b1 = row_block.get(r1) or b0
            if not b0:
                continue
            day = col_date[c]
            raw.append(dict(
                date=day, weekday=wd, block=b0[0],
                start=datetime.combine(day, b0[1]),
                end=datetime.combine(day, (b1 or b0)[2]),
                subject=subject, lecturers=people, type=type_,
                short=_short_code(cell),
                room=_room_from_cell(cell, type_) if with_rooms else "",
            ))

    return _to_lessons(_merge(raw))


def _merge(raw: List[dict]) -> List[dict]:
    """Fold consecutive same-class blocks on one day into one event."""
    raw.sort(key=lambda x: (x["date"], x["subject"], x["type"],
                            tuple(x["lecturers"]), x["start"]))
    out: List[dict] = []
    for item in raw:
        if out:
            prev = out[-1]
            same = (prev["date"] == item["date"]
                    and prev["subject"] == item["subject"]
                    and prev["type"] == item["type"]
                    and prev["lecturers"] == item["lecturers"]
                    and (item["start"] - prev["end"]).total_seconds() <= 20 * 60)
            if same:
                if item["end"] > prev["end"]:
                    prev["end"] = item["end"]
                continue
        out.append(dict(item))
    out.sort(key=lambda x: x["start"])
    return out


def _to_lessons(raw: List[dict]) -> List[Lesson]:
    lessons = []
    for x in raw:
        lessons.append(Lesson.from_dict(dict(
            start=x["start"], end=x["end"],
            subject=x.get("short") or x["subject"],
            type=f"({_type_abbr(x['type'])})" if x["type"] else "",
            type_full=x["type"], room=x["room"],
            lesson_number=str(x["block"] or ""), full_subject=x["subject"],
            lecturers=x["lecturers"],
        )))
    return lessons
