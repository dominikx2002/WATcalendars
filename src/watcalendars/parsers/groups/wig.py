from bs4 import BeautifulSoup
from watcalendars.utils.log import OK, ERROR, WARNING, INFO, SUCCESS

def parse_wig_groups_from_subcategory(html, logs=None):
    """
    Parse WIG group schedule links from a subcategory page.
    Looks for <div class="pd-float"> containing <a> links to Word documents.
    Returns dict of {group_name: download_url}.
    """

    def parse_wig_groups_log():
        logs = []
        if not html:
            logs.append(f"{ERROR} No HTML retrieved."); print(f"{ERROR} No HTML retrieved.")
            return {}

        soup = BeautifulSoup(html, "html.parser")
        
        float_divs = soup.find_all("div", class_="pd-float")
        logs.append(f"{OK} Found {len(float_divs)} pd-float divs."); print(f"{OK} Found {len(float_divs)} pd-float divs.")
        
        groups = {}
        for div in float_divs:
            link = div.find("a")
            if link and link.get("href"):
                href = link.get("href")
                group_name = link.text.strip()
                group_name = group_name.encode('windows-1250', 'replace').decode('utf-8', 'replace')

                if href.startswith("/"):
                    base_url = "https://www.wig.wat.edu.pl"
                    full_url = base_url + href
                elif not href.startswith("http"):
                    base_url = "https://www.wig.wat.edu.pl/cpp/index.php"
                    full_url = f"{base_url}/{href}"
                else:
                    full_url = href
                
                if group_name:
                    groups[group_name] = full_url
        
        logs.append(f"{OK} Parsed {len(groups)} groups."); print(f"{OK} Parsed {len(groups)} groups.")
        return groups

    groups = (print(f"{INFO} Parsing HTML content for WIG groups..."), parse_wig_groups_log())[1]
    return groups