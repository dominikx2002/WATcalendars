"""
Employee Parser - Parsing employees from WAT USOS HTML pages
"""
import time
from datetime import datetime
import re
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from watcalendars.utils.log import OK, ERROR, WARNING, INFO, SUCCESS



def scrape_employees_html(url: str, timeout: int = 30000) -> str:
    """
    Scrape employee HTML with proper waiting for dynamic content.
    
    Args:
        url: URL to scrape
        timeout: Timeout in milliseconds
        
    Returns:
        str: HTML content or empty string if failed
    """
    logs = []
    html = ""
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            t0 = time.monotonic()
            resp = page.goto(url, timeout=timeout)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            status = resp.status if resp else None
            ok = getattr(resp, "ok", None) if resp else None
            logs.append(f"Navigation done: status={status}, ok={ok}, elapsed_ms={elapsed_ms}"); print(f"Navigation done: status={status}, ok={ok}, elapsed_ms={elapsed_ms}")

            try:
                page.wait_for_selector("td.uwb-staffuser-panel", timeout=10000)
            except PlaywrightTimeoutError:
                logs.append(f"{WARNING} Employee panels not found within timeout"); print(f"{WARNING} Employee panels not found within timeout")
                page.wait_for_load_state("networkidle", timeout=5000)
            html = page.content()
            
        except Exception as e:
            logs.append(f"{ERROR} Failed to scrape page: {e}"); print(f"{ERROR} Failed to scrape page: {e}")
        finally:
            browser.close()
    
    return html


def detect_total_pages(url: str) -> int:
    """
    Detect the total number of pages by parsing the pagination element.
    
    Args:
        url: Base URL to check for pagination
        
    Returns:
        int: Total number of pages, or 1 if detection fails
    """
    logs = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            logs.append("Browser launched (chromium, headless=True)"); print("Browser launched (chromium, headless=True)")
            page = browser.new_page(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            logs.append(f"Navigating to URL: {url}"); print(f"Navigating to URL: {url}")
            t0 = time.monotonic()
            resp = page.goto(url, timeout=30000)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            status = resp.status if resp else None
            ok = getattr(resp, "ok", None) if resp else None
            logs.append(f"Navigation done: status={status}, ok={ok}, elapsed_ms={elapsed_ms}"); print(f"Navigation done: status={status}, ok={ok}, elapsed_ms={elapsed_ms}")

            try:
                page.wait_for_selector("div.uwb-page-switcher-panel", timeout=5000)
                page.wait_for_load_state("networkidle")
            except Exception:
                logs.append(f"{WARNING} Pagination element not found within timeout"); print(f"{WARNING} Pagination element not found within timeout")
            
            html = page.content()
            logs.append(f"Getting page content."); print(f"Getting page content.")
            
            soup = BeautifulSoup(html, 'html.parser')
            logs.append(f"Parsing HTML content."); print(f"Parsing HTML content.")
            
            pagination = soup.find("div", class_="uwb-page-switcher-panel")
            
            if pagination:
                td = pagination.find("td")
                if td:
                    text = td.get_text(strip=True)
                    logs.append(f"Pagination text found: \"{text}\"."); print(f"Pagination text found: \"{text}\".")
                    match = re.search(r'/\s*(\d+)', text)
                    if match:
                        total_pages = int(match.group(1))
                        now = datetime.now().strftime('%Y-%m-%d %H:%M')
                        logs.append(f"[{now}] {SUCCESS} Total pages detected: {total_pages}"); print(f"[{now}] {SUCCESS} Total pages detected: {total_pages}")
                        return total_pages
                    else:
                        logs.append(f"[{now}] {ERROR} No page number found in pagination text."); print(f"[{now}] {ERROR} No page number found in pagination text.")
                        return 1
                else:
                    logs.append(f"[{now}] {ERROR} No td element found in pagination."); print(f"[{now}] {ERROR} No td element found in pagination.")
                    return 1
            else:
                logs.append(f"[{now}] {ERROR} No pagination nav found. Assuming only 1 page."); print(f"[{now}] {ERROR} No pagination nav found. Assuming only 1 page.")
                return 1
                
        except Exception as e:
            logs.append(f"[{now}] {ERROR} Failed to load page or find pagination element: {e}"); print(f"[{now}] {ERROR} Failed to load page or find pagination element: {e}")
            return 1
        finally:
            browser.close()
            logs.append(f"Closing browser."); print(f"Closing browser.")


def parse_employees_page(html: str, page_num: int, total_pages: int) -> list[tuple[str, str]]:
    """
    Parse employee information from a single HTML page.
    
    Args:
        html: HTML content of the page
        page_num: Current page number (for logging)
        total_pages: Total number of pages (for logging)
        
    Returns:
        list: List of tuples containing (degree, full_name)
    """
    employees = []
    
    if not html:
        print(f"\n{ERROR} Empty HTML for page {page_num}")
        return employees
    
    if "pracownicyJednostki" not in html:
        print(f"\n{WARNING} Page {page_num} may not have loaded correctly. Content check failed")
        return employees
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        panels = soup.find_all("td", class_="uwb-staffuser-panel")
        
        for panel in panels:
            name_tag = panel.find("b")
            degree_link = panel.find("a", class_="no-badge uwb-photo-panel-title")
            
            if name_tag and degree_link:
                full_name = name_tag.text.strip()
                degree_text = degree_link.text.replace(full_name, "").strip()
                degree_text = ' '.join(degree_text.split())
                
                if full_name and degree_text:
                    employees.append((degree_text, full_name))
                    
        [].append(f"{SUCCESS} Found {len(employees)} employees"); print(f"{SUCCESS} Found {len(employees)} employees")
        
    except Exception as e:
        print(f"\n{ERROR} Error parsing page {page_num}: {e}")
    
    return employees
