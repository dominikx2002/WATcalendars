import re

from bs4 import BeautifulSoup
from watcalendars.utils.log import OK, ERROR, WARNING, INFO, SUCCESS


def parse_wml_groups(html, logs=None):

    def parse_wml_groups_log():
        local_logs = []
        if not html:
            msg = f"{ERROR} No HTML retrieved."
            local_logs.append(msg)
            print(msg)
            return []

        soup = BeautifulSoup(html, "html.parser")

        gro_tags = soup.find_all(['gro', 'pod', 'a'])
        if gro_tags:
            msg = f"{OK} Found {len(gro_tags)} <gro>/<pod>/<a> elements (WLO-like fallback)."
            local_logs.append(msg)
            print(msg)
            anchor_parent = gro_tags

        container = soup.find("div", id="container")
        if container:
            ul = container.find("ul", class_="menu")
            if ul:
                anchor_parent = ul
                msg = f"{OK} Found div#container > ul.menu (preferred)."
                local_logs.append(msg)
                print(msg)

        if not anchor_parent:
            for table in soup.find_all("table"):
                text = table.get_text(strip=True)
                if "Grupa/Group no." in text:
                    rows = table.find_all("tr")
                    if len(rows) >= 2:
                        data_row = rows[1]
                        tds = data_row.find_all("td")
                        if tds:
                            anchor_parent = tds[0]
                            msg = f"{OK} Found first data <td> in table with 'Grupa/Group no.' header."
                            local_logs.append(msg)
                            print(msg)
                    break

        if not anchor_parent:
            for td in soup.find_all("td"):
                if td.get("valign", "").upper() == "TOP":
                    anchor_parent = td
                    msg = f"{OK} Found <td valign=TOP> element (fallback)."
                    local_logs.append(msg)
                    print(msg)
                    break

        if not anchor_parent:
            msg = f"{ERROR} No suitable anchor parent found for WML groups."
            local_logs.append(msg)
            print(msg)
            msg = f"{WARNING} Falling back to scanning all <a> elements in the document."
            local_logs.append(msg)
            print(msg)
            anchor_parent = soup  

        groups = set()
        anchors = []
        if isinstance(anchor_parent, list):
            for el in anchor_parent:
                if el.name == 'a' and el.get('href'):
                    anchors.append(el)
                else:
                    anchors.extend(el.find_all('a', href=True))
        else:
            anchors = anchor_parent.find_all('a', href=True)

        for a in anchors:
            href = a["href"]
            if not href.lower().endswith((".htm", ".html")):
                continue

            base = href.rsplit("/", 1)[-1].split("?")[0].split("#")[0]
            base_no_ext = re.sub(r"\.(?:htm|html)$", "", base, flags=re.IGNORECASE).strip()
            if not base_no_ext:
                continue

            teacher_pattern = r'^_?(mgr|dr|prof|plk|pplk|mjr|kpt|por|inz|chor|ml\._chor)\b'
            room_pattern = r'^(s\d+|n\d+|aula|bibl|hala|sala|\d{1,3}(?:\.\d+)*_[0-9A-Za-z]+)$'

            if not re.match(r'^WML', base_no_ext, re.IGNORECASE):
                if re.match(teacher_pattern, base_no_ext, re.IGNORECASE):
                    continue
                if re.match(room_pattern, base_no_ext, re.IGNORECASE):
                    continue
            token = re.sub(r"[^A-Za-z0-9]+", "", base_no_ext)
            if not token:
                continue
            groups.add(token)

        if groups:
            msg = f"{OK} Extracted {len(groups)} WML group links."
            local_logs.append(msg)
            print(msg)
        else:
            msg = f"{WARNING} No WML group links found in selected <td>."
            local_logs.append(msg)
            print(msg)

        if logs is not None:
            logs.extend(local_logs)
        return sorted(groups)

    print("Parsing HTML content for WML groups...")
    groups = parse_wml_groups_log()
    return groups