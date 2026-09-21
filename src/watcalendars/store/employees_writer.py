"""
Employees Writer - Save employee data to JSON format
"""

import json
import os
import time
from datetime import datetime
from typing import List, Tuple
from watcalendars.utils.log import OK, ERROR, WARNING, INFO, SUCCESS
from watcalendars import DB_DIR


def save_employees_to_json(employees: List[Tuple[str, str]]) -> None:
    """
    Save employee data to JSON file.
    
    Args:
        employees: List of tuples containing (degree, full_name)
    """
    filename = os.path.join(DB_DIR, "employees.json")
    
    if not os.path.exists(filename):
        print(f"Created a new db file for WAT employees: '{os.path.abspath(filename)}'")
    else:
        print(f"{INFO} Using existing db file for WAT employees: '{os.path.abspath(filename)}'")

    def save_log():
        logs = []
        existing_employees = set()
        existing_data = {}

        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)

                if "employees" in existing_data:
                    for emp in existing_data["employees"]:
                        if isinstance(emp, dict) and "degree" in emp and "name" in emp:
                            name = emp["name"].replace(" [NEW]", "").strip()
                            existing_employees.add((emp["degree"], name))
                
                logs.append(f"Reading existing employees... Done."); print(f"Reading existing employees... Done.")
                logs.append(f"Existing employees loaded: {len(existing_employees)}"); print(f"Existing employees loaded: {len(existing_employees)}")
            except (json.JSONDecodeError, KeyError) as e:
                logs.append(f"{WARNING} Error reading existing data, starting fresh: {e}"); print(f"{WARNING} Error reading existing data, starting fresh: {e}")
                existing_data = {}
            except Exception as e:
                logs.append(f"{ERROR} Unexpected error reading file: {e}"); print(f"{ERROR} Unexpected error reading file: {e}")
                existing_data = {}

        normalized_employees = set()
        for degree, full_name in employees:
            normalized_degree = degree.strip()
            normalized_name = full_name.strip()
            if normalized_degree and normalized_name:
                normalized_employees.add((normalized_degree, normalized_name))
        
        logs.append(f"Normalizing employee data."); print(f"Normalizing employee data.")
        logs.append(f"Current employees to save: {len(normalized_employees)}"); print(f"Current employees to save: {len(normalized_employees)}")
        
        new_employees = normalized_employees - existing_employees
        all_employees = existing_employees | normalized_employees
        
        logs.append(f"New employees detected: {len(new_employees)}"); print(f"New employees detected: {len(new_employees)}")
        
        employee_list = []
        for degree, full_name in sorted(all_employees):
            is_new = (degree, full_name) in new_employees
            employee_entry = {
                "degree": degree,
                "name": full_name + (" [NEW]" if is_new else ""),
                "is_new": is_new
            }
            employee_list.append(employee_entry)
        
        metadata = {
            "last_updated": datetime.now().isoformat(),
            "last_updated_readable": time.strftime('%Y-%m-%d %H:%M:%S'),
            "total_employees": len(all_employees),
            "new_employees_count": len(new_employees),
            "scraper_version": "1.0"
        }
        
        json_data = {
            "metadata": metadata,
            "employees": employee_list
        }
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2, sort_keys=True)
            logs.append(f"Writing JSON data to '{os.path.abspath(filename)}'... Done."); print(f"Writing JSON data to '{os.path.abspath(filename)}'... Done.")
        
        return len(new_employees), len(all_employees)

    try:
        new_count, total_count = (print(f"Saving employees..."), save_log())[1]
        
        if new_count > 0:
            print(f"{SUCCESS} Summary: Saved {new_count} new employees (marked with [NEW]) in '{os.path.abspath(filename)}'.")
        else:
            print(f"{SUCCESS} Summary: No new employees found since last run.")
        
        print(f"{INFO} Total employees in '{os.path.abspath(filename)}' ({total_count})")
        
    except Exception as e:
        print(f"{ERROR} Error saving employees: {e}")
