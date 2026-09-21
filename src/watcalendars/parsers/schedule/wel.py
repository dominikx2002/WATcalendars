"""
WEL schedule parser - specialized for WEL department HTML format with complex table parsing
"""
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from bs4 import BeautifulSoup

from watcalendars.utils.config import BLOCK_TIMES, ROMAN_MONTH, DATE_TOKEN_RE, TYPE_FULL_MAP, DAY_ALIASES, TYPE_SYMBOLS
from watcalendars.utils.log import OK, ERROR, INFO, SUCCESS, WARNING, CHANGED, UNCHANGED, ADDED

def extract_legend(soup: BeautifulSoup) -> list[tuple[str, str, list[str]]]:
    """Extract subject legend and lecturers from WEL HTML"""
    entries: list[tuple[str, str, list[str]]] = []
    seen: set[tuple[str, str]] = set()
    norm = lambda s: re.sub(r"\s+", " ", (s or "")).strip()
    is_lect = lambda t: re.search(r"(?i)\b(prof\.|dr|hab\.|mgr|inż\.|inz\.|ppłk|płk|mjr|kpt\.|por\.|ppor\.|chor\.|sierż\.|kpr\.)\b", t or "") is not None
    
    def split_lect(t: str) -> list[str]:
        parts = re.split(r"(?i)\s*(?:;|/|,| i | oraz )\s*", t)
        return [re.sub(r"^[•\-–]\s*", "", norm(p)) for p in parts if norm(p)]

    last_idx: int | None = None
    for td in soup.find_all("td"):
        full = None
        if td.has_attr("mergewith"):
            try:
                full = BeautifulSoup(td["mergewith"], "html.parser").get_text(" ", strip=True)
            except Exception:
                full = norm(re.sub(r"<[^>]+>", " ", td["mergewith"]))
        abbr = td.get_text(strip=True)
        lect_text = norm(full if full else " ".join(td.stripped_strings))
        if lect_text and is_lect(lect_text) and last_idx is not None:
            lects = entries[last_idx][2]
            for n in split_lect(lect_text):
                if n not in lects:
                    lects.append(n)
            if not (abbr and full):
                continue
        if full and abbr:
            key = (abbr, full)
            if key in seen:
                for idx in range(len(entries) - 1, -1, -1):
                    a, f, _ = entries[idx]
                    if a == abbr and f == full:
                        last_idx = idx
                        break
                continue
            seen.add(key)
            lects: list[str] = []
            entries.append((abbr, full, lects))
            last_idx = len(entries) - 1
    return entries


def parse_schedule(html: str) -> list[dict]:
    """Parse single WEL schedule HTML into lesson events"""
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')
    table = None
    if tables:
        for t in tables:
            for tr in t.find_all('tr'):
                tds = tr.find_all(['td', 'th'])
                if not tds:
                    continue
                first_cell = (tds[0].get_text(strip=True) or '').lower()
                if first_cell in DAY_ALIASES:
                    table = t
                    break
            if table:
                break
        if not table:
            table = tables[0]
    if not table:
        return []

    txt = re.sub(r"\s+", " ", soup.get_text(" ").strip())
    now = datetime.now()
    year = now.year
    m_year = re.search(r"(20\d{2})\s*/\s*(20\d{2})", txt)
    if m_year:
        y1, y2 = int(m_year.group(1)), int(m_year.group(2))
        year = y1 if now.month >= 9 else y2
    else:
        m_any = re.search(r"(20\d{2})", txt)
        if m_any:
            year = int(m_any.group(1))

    legend_entries = extract_legend(soup)
    subject_legend_full: dict[str, str] = {}
    subject_legend_lect: dict[str, list[str]] = {}
    all_lecturers: list[str] = []
    
    for abbr, full, lecturers in legend_entries:
        if abbr and full:
            subject_legend_full.setdefault(abbr, full)
            if lecturers:
                lst = subject_legend_lect.setdefault(abbr, [])
                for l in lecturers:
                    if l not in lst:
                        lst.append(l)
                        if l not in all_lecturers:
                            all_lecturers.append(l)

    def normalize_type(sym: str) -> str:
        """Normalize lesson type symbol"""
        s = (sym or '').strip()
        if not s:
            return s
        if s in TYPE_SYMBOLS:
            return s
        core = s.strip('()')
        for cand in (f'({core})', f'({core.lower()})', f'({core.upper()})'):
            if cand in TYPE_SYMBOLS:
                return cand
        return s

    def pick_lecturers_for_code(subj: str, code: str) -> list[str]:
        """Pick lecturers based on subject and lecturer codes"""
        names = subject_legend_lect.get(subj) or []
        if not names:
            names = all_lecturers
        if not code:
            return names[:1] if len(names) == 1 else []

        if not names:
            return []

        def undiac(s: str) -> str:
            return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

        codes = [c for c in re.split(r"[\s/,;]+", code.strip()) if c]
        result: list[str] = []
        seen: set[str] = set()
        norm_names = [(full, re.sub(r'[^a-z]', '', undiac(full).lower())) for full in names]
        for code_token in codes:
            k = re.sub(r'[^a-z]', '', undiac(code_token).lower())
            if not k:
                continue
            for full, hay in norm_names:
                if full in seen:
                    continue
                if all(ch in hay for ch in set(k)):
                    result.append(full)
                    seen.add(full)
                    break
        return result

    lessons: list[dict] = []
    current_day = None
    current_dates: list[datetime | None] = []
    active_cells: list[tuple[list[str], int] | None] = []

    for tr in table.find_all('tr'):
        cells = tr.find_all(['td', 'th'])
        if not cells:
            continue
        first = (cells[0].get_text(strip=True) or '').lower()
        
        if first in DAY_ALIASES and len(cells) > 2:
            tentative_dates: list[datetime | None] = []
            matched_any_date = False
            last_date_idx = -1
            
            for idx, c in enumerate(cells[2:]):
                token = (c.get_text(strip=True) or '').replace('\xa0', ' ').strip()
                if not token:
                    tentative_dates.append(None)
                    continue
                    
                m = DATE_TOKEN_RE.match(token)
                if m:
                    d = int(m.group(1))
                    roman = m.group(2)
                    month = ROMAN_MONTH.get(roman)
                    if month:
                        try:
                            tentative_dates.append(datetime(year, month, d))
                        except ValueError:
                            tentative_dates.append(None)
                        matched_any_date = True
                        last_date_idx = idx
                        continue
                tentative_dates.append(None)
                
            if matched_any_date:
                current_day = first
                if last_date_idx >= 0:
                    current_dates = tentative_dates[: last_date_idx + 1]
                else:
                    current_dates = tentative_dates
                active_cells = [None] * len(current_dates)
                continue

        if current_day and len(cells) > 2:
            block_label = None
            block_idx = None
            if first in BLOCK_TIMES:
                block_label = first
                block_idx = 0
            elif cells[1].get_text(strip=True) in BLOCK_TIMES:
                block_label = cells[1].get_text(strip=True)
                block_idx = 1
            if not block_label:
                continue
                
            start_time, end_time = BLOCK_TIMES[block_label]

            def append_lesson_if_valid(dt: datetime | None, raw_lines: list[str]):
                """Create lesson from parsed data"""
                if not (dt and raw_lines):
                    return
                    
                lines = [t for t in raw_lines if t]
                percent_token = None
                if lines and '%' in lines[0]:
                    percent_token = lines[0]
                    lines = lines[1:]
                    
                subject_abbr = None
                subject_idx = None
                for i, tok in enumerate(lines):
                    tt = tok.strip()
                    if re.fullmatch(r"[A-ZĄĆĘŁŃÓŚŹŻ]{2,6}", tt):
                        subject_abbr = tt
                        subject_idx = i
                        break
                        
                if not subject_abbr or subject_abbr.upper() == 'SK':
                    return
                    
                subject_display = f"{percent_token} {subject_abbr}".strip() if percent_token else subject_abbr
                
                symbol = ''
                room = ''
                lecturer_codes: list[str] = []
                rest = lines[subject_idx + 1:] if subject_idx is not None else []
                
                for line in rest:
                    if not symbol and line in TYPE_SYMBOLS:
                        symbol = line
                        continue
                    m_room = re.match(r'^(\d{2,3}(?:\s*\d{2})?[A-Z]?)$', line)
                    if not room and m_room:
                        room = m_room.group(1).replace(' ', '')
                        continue
                    if re.match(r'^[A-ZŻŹĆŁŚÓ]{2,}$', line) or re.match(r'^[A-ZŻŹĆŁŚÓ][a-ząćęłńóśźż]{2,}$', line):
                        lecturer_codes.append(line)
                        continue

                lesson_type = normalize_type(symbol)
                type_full = TYPE_FULL_MAP.get(lesson_type, lesson_type or '-')
                lect_code = ' '.join(lecturer_codes)
                lecturers = pick_lecturers_for_code(subject_abbr, lect_code)
                full_subject_name = subject_legend_full.get(subject_abbr, subject_abbr)
                
                try:
                    start_dt = datetime.strptime(start_time, '%H:%M').replace(year=dt.year, month=dt.month, day=dt.day)
                    end_dt = datetime.strptime(end_time, '%H:%M').replace(year=dt.year, month=dt.month, day=dt.day)
                except Exception:
                    return
                    
                lessons.append({
                    'date': dt.strftime('%Y_%m_%d'),
                    'start': start_dt,
                    'end': end_dt,
                    'subject': subject_abbr,
                    'subject_display': subject_display,
                    'type': lesson_type,
                    'type_full': type_full,
                    'room': room,
                    'lesson_number': '',
                    'full_subject_name': full_subject_name,
                    'lecturers': lecturers,
                    'full_subject': full_subject_name,
                    'lecturer': '; '.join(lecturers) if lecturers else '',
                })

            col_idx = 0
            ci = block_idx + 1
            while col_idx < len(current_dates):
                if active_cells and col_idx < len(active_cells) and active_cells[col_idx]:
                    raw_lines, remaining = active_cells[col_idx]
                    remaining -= 1
                    active_cells[col_idx] = (raw_lines, remaining) if remaining > 0 else None
                    dt = current_dates[col_idx]
                    append_lesson_if_valid(dt, raw_lines)
                    col_idx += 1
                    continue
                    
                if ci >= len(cells):
                    col_idx += 1
                    continue
                    
                c = cells[ci]
                ci += 1
                
                try:
                    colspan = int(c.get('colspan') or 1)
                except Exception:
                    colspan = 1
                try:
                    rowspan = int(c.get('rowspan') or 1)
                except Exception:
                    rowspan = 1
                    
                raw_lines = [t.strip() for t in c.stripped_strings if t.strip() and t.strip() != '-']
                
                for k in range(colspan):
                    if col_idx >= len(current_dates):
                        break
                    dt = current_dates[col_idx]
                    if rowspan > 1 and raw_lines and active_cells and col_idx < len(active_cells):
                        active_cells[col_idx] = (raw_lines, rowspan - 1)
                    append_lesson_if_valid(dt, raw_lines)
                    col_idx += 1

    return lessons


def parse_schedules(html_map):
    """Parse multiple WEL schedule HTMLs"""
    schedules = {}
    total_groups = len(html_map)
    groups_done = 0
    events_done = 0

    def progress():
        return f"({groups_done}/{total_groups})"

    def log_parse_schedule():
        nonlocal groups_done, events_done
        for group_id, html in html_map.items():
            lessons = parse_schedule(html)
            schedules[group_id] = lessons
            print(f"{OK} Parsing {group_id} completed. (items: {len(lessons)})")
            events_done += len(lessons)
            groups_done += 1
        return schedules

    schedules = (print(f"{INFO} Parsing schedules"), log_parse_schedule())[1]
    parsed_total = sum(len(lessons or []) for lessons in schedules.values())
    if parsed_total > 0:
        print(f"{SUCCESS} Summary: Parsed events: {parsed_total} across {len(schedules)} groups")
    else:
        print(f"{ERROR} No events parsed.")
    return schedules
