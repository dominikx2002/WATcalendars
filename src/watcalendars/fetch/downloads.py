import os
import time
import re
import requests
from playwright.sync_api import sync_playwright
from watcalendars.utils.log import OK, ERROR, WARNING, INFO, SUCCESS

def download_schedule_file(url, output_dir, filename, logs=None):
    """
    Download a schedule file (Word document) from URL using Playwright.
    
    Args:
        url: URL to download from
        output_dir: Directory to save the file
        filename: Name for the saved file
        logs: Optional logs list
    
    Returns:
        Path to saved file or None if failed
    """
    logs = logs if logs is not None else []
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        if not filename.endswith(('.doc', '.docx')):
            filename = f"{filename}.docx"
        
        filepath = os.path.join(output_dir, filename)

        try:
            r = requests.get(url, timeout=30, allow_redirects=True)
            r.raise_for_status()
            cd = r.headers.get('content-disposition', '')
            m = re.search(r'filename\*=UTF-8\'\'([^;]+)', cd) or re.search(r'filename="?([^";]+)"?', cd)
            if m:
                suggested = m.group(1)
                if suggested.lower().endswith(('.doc', '.docx')):
                    _, ext = os.path.splitext(suggested)
                    if not filename.lower().endswith(ext.lower()):
                        filename = filename + ext
                    filepath = os.path.join(output_dir, filename)
            if not filename.endswith(('.doc', '.docx')):
                filename = f"{filename}.docx"
                filepath = os.path.join(output_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(r.content)
            size_kb = len(r.content) / 1024
            logs.append(f"{SUCCESS} Downloaded {filename} via HTTP ({size_kb:.1f} KB)"); print(f"{SUCCESS} Downloaded {filename} via HTTP ({size_kb:.1f} KB)")
            return filepath
        except Exception:
            pass

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            
            download_obj = {'download': None}
            
            def handle_download(download):
                download_obj['download'] = download
            
            page.on('download', handle_download)
            
            try:
                try:
                    page.goto(url, timeout=30000, wait_until="commit")
                except Exception:
                    pass
                
                timeout = 30
                start_time = time.time()
                while download_obj['download'] is None and (time.time() - start_time) < timeout:
                    time.sleep(0.1)
                
                if download_obj['download']:
                    download = download_obj['download']
                    
                    download.save_as(filepath)
                    
                    if os.path.exists(filepath):
                        size_kb = os.path.getsize(filepath) / 1024
                        logs.append(f"{SUCCESS} Downloaded {filename} ({size_kb:.1f} KB)"); print(f"{SUCCESS} Downloaded {filename} ({size_kb:.1f} KB)")
                        context.close()
                        browser.close()
                        return filepath
                    else:
                        logs.append(f"{ERROR} File not saved: {filename}"); print(f"{ERROR} File not saved: {filename}")
                        context.close()
                        browser.close()
                        return None
                else:
                    logs.append(f"{ERROR} Download did not start for: {filename}"); print(f"{ERROR} Download did not start for: {filename}")
                    context.close()
                    browser.close()
                    return None
                    
            except Exception as e:
                logs.append(f"{ERROR} Failed to download {filename}: {str(e)[:100]}"); print(f"{ERROR} Failed to download {filename}: {str(e)[:100]}")
                context.close()
                browser.close()
                return None
        
    except Exception as e:
        logs.append(f"{ERROR} Error downloading {filename}: {str(e)[:100]}"); print(f"{ERROR} Error downloading {filename}: {str(e)[:100]}")
        return None
