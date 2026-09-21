import re
import unicodedata
from datetime import datetime
from bs4 import BeautifulSoup
from watcalendars.utils.config import BLOCK_TIMES, ROMAN_MONTH, DATE_TOKEN_RE, TYPE_FULL_MAP, DAY_ALIASES, TYPE_SYMBOLS
from watcalendars.utils.log import OK, ERROR, WARNING, INFO, SUCCESS

def extract_legend(soup: BeautifulSoup, logs=None) -> list[tuple[str, str, list[str]]]:
    logs = logs if logs is not None else []
    entries: list[tuple[str, str, list[str]]] = []
    seen: set[tuple[str, str]] = set()

    def norm(s: str | None) -> str:
        return re.sub(r"\s+", " ", (s or "")).strip()

    def is_lect(t: str) -> bool:
        pattern = r"(?i)\b(prof|dr|hab|mgr|inz|pplk|plk|mjr|kpt|por|ppor|chor|sierz|kpr)\.?\b"
        s = ''.join(c for c in unicodedata.normalize('NFD', t or '') if unicodedata.category(c) != 'Mn')
        s = s.replace('ł', 'l').replace('Ł', 'L')
        return re.search(pattern, s or "") is not None

    def split_lect(t: str) -> list[str]:
        parts = re.split(r"(?i)\s*(?:;|/|,| i | oraz |•|\n|\r)\s*", t)
        return [re.sub(r"^[•\-–]\s*", "", norm(p)) for p in parts if norm(p)]

    table = soup.find('table') or (soup.find_all('table')[0] if soup.find_all('table') else None)
    if table:
        rows = table.find_all('tr')
        
        legend_started = False
        
        for i, tr in enumerate(rows):
            cells = tr.find_all('td')
            if len(cells) < 2:
                continue
                
            last_two = cells[-2:]
            if len(last_two) < 2:
                continue
                
            left_text = norm(last_two[0].get_text(strip=True))
            right_text = norm(last_two[1].get_text(strip=True))
            
            if left_text and right_text and len(left_text) <= 10 and len(right_text) > 10:
                is_lecturer = is_lect(right_text)
                lecturers = []
                if is_lecturer:
                    lecturers = [right_text]  
                    
                key = (left_text, right_text)
                if key not in seen:
                    entries.append((left_text, right_text, lecturers))
                    seen.add(key)
                    legend_started = True
                    
            elif legend_started and not left_text and not right_text:
                continue
                
    return entries

def parse_schedule(html: str, logs=None) -> list[dict]:
    logs = logs if logs is not None else []
    if not html:
        logs.append(f"{ERROR} No HTML for parsing."); print(f"{ERROR} No HTML for parsing.")
        return []

    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table') or (soup.find_all('table')[0] if soup.find_all('table') else None)
    if not table:
        logs.append(f"{ERROR} No table in HTML."); print(f"{ERROR} No table in HTML.")
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
    legend_entries = extract_legend(soup, logs)
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

    def undiac_local(s: str) -> str:
        return ''.join(c for c in unicodedata.normalize('NFD', s or '') if unicodedata.category(c) != 'Mn')

    def is_lect_text(t: str) -> bool:
        pattern = r"(?i)\b(prof|dr|hab|mgr|inz|pplk|plk|mjr|kpt|por|ppor|chor|sierz|kpr)\.?\b"
        s = undiac_local(t).replace('ł', 'l').replace('Ł', 'L')
        return re.search(pattern, s or "") is not None

    for node in soup.find_all(['p', 'td', 'font']):
        text = " ".join([t for t in node.stripped_strings])
        if not text:
            continue
        for piece in re.split(r"(?i)\s*(?:;|/|,| i | oraz |•|\n|\r)\s*", text):
            piece = piece.strip()
            if not piece:
                continue
            if is_lect_text(piece):
                name = re.sub(r"^[•\-–]\s*", "", piece)
                if name and name not in all_lecturers:
                    all_lecturers.append(name)

    def normalize_type(sym: str) -> str:
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
        names = subject_legend_lect.get(subj) or []
        subject_only = bool(names)
        if not names:
            names = all_lecturers
        if not code:
            return list(names)
        if not names:
            return []
        
        def clean_lecturer_code(raw_code: str) -> str:
            if not raw_code or not raw_code.strip():
                return ""
            
            original = raw_code.strip()
            cleaned = original
            
            if cleaned.startswith('(') and 'Ep)' in cleaned:
                cleaned = re.sub(r'\(\s*Ep\).*$', '', cleaned, flags=re.IGNORECASE).strip()
                if not cleaned:
                    return ""
            
            cleaned = re.sub(r'\s*-\s*Egz\.\s*poprawkowy.*$', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s*Rozkład\s+zajęć.*$', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s*tel\.\s*\d+[-\d\s]*.*$', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s*(marzec|kwiecień|maj|czerwiec|lipiec|sierpień|wrzesień|październik|listopad|grudzień).*$', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s*pon\.\s*\d+.*$', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s*\d+\s*(III|IV|V|VI|VII|VIII|IX|X|XI|XII).*$', '', cleaned, flags=re.IGNORECASE)
            
            if len(cleaned) > 50:
                match = re.match(r'^([A-Za-z]{2,8})\b', cleaned)
                if match:
                    cleaned = match.group(1)
                else:
                    return ""
            
            return cleaned.strip()
        
        def undiac(s: str) -> str:
            return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        
        code = clean_lecturer_code(code)
        if not code:
            return []
            
        codes = [c for c in re.split(r"[\s/,;]+", code.strip()) if c]
        result: list[str] = []
        seen: set[str] = set()
        norm_names = [(full, re.sub(r'[^a-z]', '', undiac(full).lower())) for full in names]
        norm_all = [(full, re.sub(r'[^a-z]', '', undiac(full).lower())) for full in all_lecturers]
        for code_token in codes:
            k = re.sub(r'[^a-z]', '', undiac(code_token).lower())
            if not k:
                continue
            matched = False
            for full, hay in norm_names:
                if full in seen:
                    continue
                if all(ch in hay for ch in set(k)):
                    result.append(full)
                    seen.add(full)
                    matched = True
                    break
            if subject_only and not matched:
                for full, hay in norm_all:
                    if full in seen:
                        continue
                    if all(ch in hay for ch in set(k)):
                        result.append(full)
                        seen.add(full)
                        matched = True
                        break
            if not matched:
                if code_token not in seen and len(code_token) <= 20:
                    result.append(code_token)
                    seen.add(code_token)
        return result

    lessons: list[dict] = []
    current_day = None
    current_dates: list[datetime | None] = []
    for tr in table.find_all('tr'):
        cells = tr.find_all(['td', 'th'])
        if not cells:
            continue
        first = (cells[0].get_text(strip=True) or '').lower()
        if first in DAY_ALIASES and len(cells) > 2 and not cells[1].get_text(strip=True):
            current_day = first
            current_dates = []
            for c in cells[2:]:
                token = (c.get_text(strip=True) or '').replace('\xa0', ' ').strip()
                if not token:
                    current_dates.append(None)
                    continue
                m = DATE_TOKEN_RE.match(token)
                if m:
                    d = int(m.group(1)); roman = m.group(2)
                    month = ROMAN_MONTH.get(roman)
                    if month:
                        try:
                            current_dates.append(datetime(year, month, d))
                        except ValueError:
                            current_dates.append(None)
                        continue
                current_dates.append(None)
            continue
        if first in DAY_ALIASES and len(cells) > 2 and current_day:
            block_label = cells[1].get_text(strip=True)
            if block_label not in BLOCK_TIMES:
                continue
            start_time, end_time = BLOCK_TIMES[block_label]
            for i, c in enumerate(cells[2:]):
                if i >= len(current_dates):
                    break
                dt = current_dates[i]
                if not dt:
                    continue
                raw_lines = [t.strip() for t in c.stripped_strings if t.strip() and t.strip() != '-']
                if not raw_lines:
                    continue
                subject_abbr = raw_lines[0]
                if subject_abbr.strip().upper() == 'SK':
                    continue
                subj_norm = subject_abbr.strip().upper()
                if subj_norm.startswith('WF'):
                    type_token = raw_lines[1] if len(raw_lines) > 1 else ''
                    lect_code = raw_lines[2] if len(raw_lines) > 2 else ''
                    room = ''
                else:
                    type_token = raw_lines[1] if len(raw_lines) > 1 else ''
                    room = raw_lines[2] if len(raw_lines) > 2 else ''
                    lect_code = raw_lines[3] if len(raw_lines) > 3 else ''
                
                lesson_type = normalize_type(type_token)
                type_full = TYPE_FULL_MAP.get(lesson_type, lesson_type or '-')
                lecturers = pick_lecturers_for_code(subject_abbr, lect_code)
                full_subject_name = subject_legend_full.get(subject_abbr, subject_abbr)
                try:
                    start_dt = datetime.strptime(start_time, '%H:%M').replace(year=dt.year, month=dt.month, day=dt.day)
                    end_dt = datetime.strptime(end_time, '%H:%M').replace(year=dt.year, month=dt.month, day=dt.day)
                except Exception:
                    continue
                lessons.append({
                    'date': dt.strftime('%Y_%m_%d'),
                    'start': start_dt,
                    'end': end_dt,
                    'subject': subject_abbr,
                    'type': lesson_type,
                    'type_full': type_full,
                    'room': room,
                    'lesson_number': '',
                    'full_subject_name': full_subject_name,
                    'lecturers': lecturers,
                })
    totals: dict[tuple[str, str], int] = {}
    for les in lessons:
        key = (les['subject'], les['type'])
        totals[key] = totals.get(key, 0) + 1
    counters: dict[tuple[str, str], int] = {}
    for les in lessons:
        key = (les['subject'], les['type'])
        counters[key] = counters.get(key, 0) + 1
        les['lesson_number'] = f"{counters[key]}/{totals.get(key, 0)}"
    return lessons

def parse_schedules(html_map: dict) -> dict:
    logs = []
    total = len(html_map)
    done = [0]
    def progress():
        return f"({done[0]}/{total})"
    def parse_all():
        schedules = {}
        for group_id, html in html_map.items():
            lessons = parse_schedule(html, logs)
            schedules[group_id] = lessons
            print(f"{OK} Parsing {group_id} completed. (items: {len(lessons)})")
            done[0] += 1
        return schedules
    schedules = (print(f"{INFO} Parsing schedules..."), parse_all())[1]
    parsed_total = sum(len(lessons or []) for lessons in schedules.values())
    if parsed_total > 0:
        print(f"{SUCCESS} Summary: Parsed events: {parsed_total} across {len(schedules)} groups")
    else:
        print(f"{ERROR} No events parsed.")
    return schedules