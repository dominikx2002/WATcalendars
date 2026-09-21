# calendar parser definitions
import re

BLOCK_TIMES = {
    "block1": ("08:00", "09:35"),
    "block2": ("09:50", "11:25"),
    "block3": ("11:40", "13:15"),
    "block4": ("13:30", "15:05"),
    "block5": ("16:00", "17:35"),
    "block6": ("17:50", "19:25"),
    "block7": ("19:40", "21:15"),
    '1-2': ("08:00", "09:35"),
    '3-4': ("09:50", "11:25"),
    '5-6': ("11:40", "13:15"),
    '7-8': ("13:30", "15:05"),
    '9-10': ("16:00", "17:35"),
    '11-12': ("17:50", "19:25"),
    '13-14': ("19:40", "21:15")
}

ROMAN_MONTH = {
    'I': 1,
    'II': 2,
    'III': 3,
    'IV': 4,
    'V': 5,
    'VI': 6,
    'VII': 7,
    'VIII': 8,
    'IX': 9,
    'X': 10,
    'XI': 11,
    'XII': 12
}

DATE_TOKEN_RE = re.compile(r'^(\d{2})\s+([IVX]{1,4})$')

TYPE_FULL_MAP = {
    "(w)": "Wykład",
    "(L)": "Laboratorium",
    "(ć)": "Ćwiczenia",
    "(P)": "Projekt",
    "(S)": "Seminarium",
    "(E)": "Egzamin",
    "(Ep)": "Egzamin poprawkowy",
    "(inne)": "inne",
}

DAY_ALIASES = {
    'pon.': 'MON', 'wt.': 'TUE', 'śr.': 'WED', 'sr.': 'WED', 'czw.': 'THU', 'pt.': 'FRI', 'sob.': 'SAT', 'niedz.': 'SUN'
}

TYPE_SYMBOLS = set(TYPE_FULL_MAP.keys())

def sanitize_filename(filename):
    return re.sub(r'[<>:"\\|?*]', "_", filename)
from datetime import datetime

def get_current_semester() -> str:
    current_month = datetime.now().month
    if current_month >= 9 or current_month <= 2:
        return "zima"
    return "lato"
