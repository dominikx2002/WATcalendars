"""
WCY schedule parser - specialized for WCY department HTML format
"""
import re
from collections import defaultdict
from datetime import datetime
from bs4 import BeautifulSoup

from watcalendars.utils.employees_loader import load_employees
from watcalendars.utils.config import BLOCK_TIMES, TYPE_FULL_MAP
from watcalendars.utils.log import OK, ERROR, INFO, SUCCESS, WARNING, CHANGED, UNCHANGED, ADDED


def parse_schedule(html, employees):
    """Parse single WCY schedule HTML into lesson events"""
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    lessons = []
    lesson_counters = defaultdict(int)
    max_lessons_count = defaultdict(int)

    for lesson in soup.find_all("div", class_="lesson"):
        try:
            subject_element = lesson.find("span", class_="name")
            
            if not subject_element:
                continue
            
            subject_lines = [line.strip() for line in subject_element.stripped_strings]
            
            if len(subject_lines) < 4:
                continue
            
            subject_short = subject_lines[0]
            lesson_type = subject_lines[1]
            lesson_number_match = re.search(r"\[(\d+)\]", subject_lines[3])
            lesson_number = int(lesson_number_match.group(1)) if lesson_number_match else 0
            lesson_key = (subject_short, lesson_type)
            
            if lesson_number:
                max_lessons_count[lesson_key] = max(max_lessons_count[lesson_key], lesson_number)
        
        except:
            continue

    for lesson in soup.find_all("div", class_="lesson"):
        try:
            date_str_el = lesson.find("span", class_="date")
            block_id_el = lesson.find("span", class_="block_id")

            if not date_str_el or not block_id_el:
                continue

            date_str = date_str_el.text.strip()
            block_id = block_id_el.text.strip()

            subject_element = lesson.find("span", class_="name")
            
            if not subject_element:
                continue
            
            subject_lines = [line.strip() for line in subject_element.stripped_strings]
            
            if len(subject_lines) < 4:
                continue
            
            subject_short = subject_lines[0]
            lesson_type = subject_lines[1]
            room = subject_lines[2].replace(",", "").strip()
            
            lesson_number_match = re.search(r"\[(\d+)\]", subject_lines[3])
            lesson_number = int(lesson_number_match.group(1)) if lesson_number_match else 0
            lesson_key = (subject_short, lesson_type)
            max_lessons = max_lessons_count.get(lesson_key) or lesson_number or 0
            
            info_element = lesson.find("span", class_="info")
            full_subject_info = info_element.text.strip() if info_element else " - "
            full_subject_cleaned = re.sub(r" - \(.+\) - .*", "", full_subject_info).strip()
            
            lecturer_with_title = "-"
            lecturer_match = re.search(
                r"- \(.+\) - ((?:dr |prof\. |inż\. )?[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+) ([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)",
                full_subject_info,
            )

            if lecturer_match:
                first_name = lecturer_match.group(2)
                last_name = lecturer_match.group(1)
                key = f"{first_name} {last_name}"
                lecturer_with_title = employees.get(key, key)
            else:
                name_match = re.search(
                    r"- \(.+\) - ([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+ [A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)",
                    full_subject_info,
                )
                if name_match:
                    key = name_match.group(1)
                    lecturer_with_title = employees.get(key, key)

            lesson_type_full = TYPE_FULL_MAP.get(lesson_type, lesson_type)

            try:
                date_obj = datetime.strptime(date_str, "%Y_%m_%d")
            except Exception:
                continue

            start_time, end_time = BLOCK_TIMES.get(block_id, ("00:00", "00:00"))
            start_datetime = datetime.strptime(start_time, "%H:%M").replace(
                year=date_obj.year, month=date_obj.month, day=date_obj.day
            )
            end_datetime = datetime.strptime(end_time, "%H:%M").replace(
                year=date_obj.year, month=date_obj.month, day=date_obj.day
            )

            # Deduplication: Check if an event already exists for this block
            unique_key = (date_str, block_id, subject_short, lesson_type)
            existing_lesson = next((l for l in lessons if l.get("_unique_key") == unique_key), None)
            
            if existing_lesson:
                if lecturer_with_title != "-" and lecturer_with_title not in existing_lesson["lecturer"]:
                    if existing_lesson["lecturer"] == "-":
                        existing_lesson["lecturer"] = lecturer_with_title
                    else:
                        existing_lesson["lecturer"] += ", " + lecturer_with_title
                continue

            lesson_counters[lesson_key] += 1
            lesson_number_formatted = f"{lesson_counters[lesson_key]}/{max_lessons or '?'}"

            lessons.append({
                "_unique_key": unique_key,
                "date": date_str,
                "start": start_datetime,
                "end": end_datetime,
                "subject": subject_short,
                "type": lesson_type,
                "type_full": lesson_type_full,
                "room": room,
                "lesson_number": lesson_number_formatted,
                "full_subject": full_subject_cleaned,
                "lecturer": lecturer_with_title,
            })

        except Exception as e:
            print(f"{ERROR} Error parsing lesson: {e}")
    
    return lessons


def parse_schedules(html_map):
    """Parse multiple WCY schedule HTMLs"""
    employees = load_employees()
    schedules = {}
    total_groups = len(html_map)
    groups_done = 0
    events_done = 0

    def progress():
        return f"({groups_done}/{total_groups})"

    def log_parse_schedule():
        nonlocal groups_done, events_done
        for group_id, html in html_map.items():
            lessons = parse_schedule(html, employees)
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