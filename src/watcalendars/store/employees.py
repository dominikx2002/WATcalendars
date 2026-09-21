"""
Employees Loader - Load employee data from JSON file
"""

import json
import os
from typing import Dict

from watcalendars import DB_DIR


def load_employees() -> Dict[str, str]:
    """
    Load employee data from employees.json file.
    
    Returns:
        Dict[str, str]: Dictionary mapping employee names to their full titles
                       (e.g., "Jan Kowalski" -> "dr Jan Kowalski")
    """
    filename = os.path.join(DB_DIR, "employees.json")
    
    if not os.path.exists(filename):
        print(f"[WARNING] Employees file not found: {filename}")
        return {}
    
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        employees_dict = {}
        
        if "employees" in data and isinstance(data["employees"], list):
            for employee in data["employees"]:
                if isinstance(employee, dict) and "degree" in employee and "name" in employee:
                    clean_name = employee["name"].replace(" [NEW]", "").strip()
                    degree = employee["degree"].strip()
                    
                    if clean_name and degree:
                        full_title = f"{degree} {clean_name}"
                        employees_dict[clean_name] = full_title
        
        return employees_dict
        
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in employees file: {e}")
        return {}
    except Exception as e:
        print(f"[ERROR] Error loading employees: {e}")
        return {}


def get_employee_title(name: str, employees_dict: Dict[str, str] = None) -> str:
    """
    Get employee title by name.
    
    Args:
        name: Employee name to look up
        employees_dict: Optional pre-loaded employees dictionary
        
    Returns:
        str: Full employee title or original name if not found
    """
    if employees_dict is None:
        employees_dict = load_employees()
    
    return employees_dict.get(name, name)
