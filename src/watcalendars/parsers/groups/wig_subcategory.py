from bs4 import BeautifulSoup
from watcalendars.utils.log import OK, ERROR, WARNING, INFO, SUCCESS

def parse_wig_subcategories(html, logs=None):
    """
    Parse WIG subcategory URLs from HTML content.
    Looks for span elements with class 'pd-subcategory' and finds sibling <a> links.
    Returns dict of {subcategory_name: url}.
    """

    def parse_wig_subcategories_log():
        logs = []
        if not html:
            logs.append(f"{ERROR} No HTML retrieved."); print(f"{ERROR} No HTML retrieved.")
            return {}

        soup = BeautifulSoup(html, "html.parser")
        
        subcategory_spans = soup.find_all("span", class_="pd-subcategory")
        logs.append(f"{OK} Found {len(subcategory_spans)} subcategory elements."); print(f"{OK} Found {len(subcategory_spans)} subcategory elements.")
        
        subcategories = {}
        for span in subcategory_spans:
            parent = span.parent
            if parent:
                link = parent.find("a")
                if link and link.get("href"):
                    href = link.get("href")
                    name = link.text.strip()
                    name = name.encode('windows-1250', 'replace').decode('utf-8', 'replace')

                    if href.startswith("/"):
                        base_url = "https://www.wig.wat.edu.pl"
                        full_url = base_url + href
                    elif not href.startswith("http"):
                        base_url = "https://www.wig.wat.edu.pl/cpp/index.php/studenci/plany-rozklady-terminy/rozklady-zajec"
                        full_url = f"{base_url}/{href}"
                    else:
                        full_url = href
                    
                    if name:
                        subcategories[name] = full_url
        
        logs.append(f"{SUCCESS} Parsed {len(subcategories)} subcategories."); print(f"{SUCCESS} Parsed {len(subcategories)} subcategories.")
        return subcategories

    subcategories = (print(f"{INFO} Parsing HTML content for WIG subcategories..."), parse_wig_subcategories_log())[1]
    return subcategories
