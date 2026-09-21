import json
import os
from watcalendars.utils.log import OK, ERROR, WARNING, INFO, SUCCESS


def load_json_config(filename: str):
    """Load JSON config from a file."""
    try:
        with open(filename, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"{ERROR} Config file not found: {filename}")
        return {}
    except Exception as ex:
        print(f"{ERROR} Error loading {filename}: {ex}")
        return {}

def _pick_url(url_data, requested):
    if requested in url_data and url_data.get(requested):
        return url_data.get(requested)
    return None

def load_url_from_config(config_file: str, key: str, url_type: str = None):
    """
    Load URL from a given JSON config file ("url_for_employees.json", "url_for_groups.json", "url_for_schedules.json")
    :param config_file: Path to JSON file
    :param key: Section key (e.g. 'wcy_schedule')
    :param url_type: Subkey (e.g. 'url_lato')
    :return: (url, description) or (None, None)
    """
    try:
        config = load_json_config(config_file)
        if not url_type:
            print(f"{ERROR} url_type must be specified explicitly.")
            return None, None

        if isinstance(config, dict):
            if key not in config:
                available_keys = [k for k in config.keys()]
                print(f"{ERROR} Unknown key '{key}'. Available: {', '.join(sorted(available_keys))}")
                return None, None

            url_list = config[key]
            if not url_list:
                print(f"{ERROR} No entries for key '{key}'")
                return None, None

            url_data = url_list[0]
            picked = _pick_url(url_data, url_type)
            if not picked:
                print(f"{ERROR} No URL found (requested '{url_type}') for key '{key}'. Keys present: {', '.join(url_data.keys())}")
                return None, None
            return picked, url_data.get('description')

        print(f"{ERROR} Unsupported config structure")
        return None, None

    except Exception as e:
        print(f"{ERROR} {e}")
        return None, None
