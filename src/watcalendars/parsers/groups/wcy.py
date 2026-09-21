import re

from bs4 import BeautifulSoup

from watcalendars.utils.log import OK

def parse_wcy_groups(html, logs=None):
    """
    Parse WCY group names from HTML content (option elements).
    Returns sorted list of group tokens.
    """

    def parse_wcy_groups_log():
        logs = []
        if not html:
            logs.append(f"[ERROR] No HTML retrieved."); print(f"[ERROR] No HTML retrieved.")
            return []

        soup = BeautifulSoup(html, "html.parser")
        options = soup.find_all("option")
        logs.append(f"{OK} Found pagination element: {len(options)} options."); print(f"{OK} Found pagination element: {len(options)} options.")
        groups = []
        for option in options:
            group = option.text.strip()
            if group and "Wybierz" not in group:
                group = group.rstrip(".")
                groups.append(group)
        logs.append(f"Founding groups..."); print(f"Founding groups...")
        return sorted(groups)

    groups = (print("Parsing HTML content for WCY groups..."), parse_wcy_groups_log())[1]
    return sorted(groups)