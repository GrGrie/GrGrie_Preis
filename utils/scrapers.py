from utils.basescraper import BaseScraper  
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
import time, os, tempfile, requests, fitz, re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Optional


from utils.utils import WebDriverManager, ImageDownloader

class LidlScraper(BaseScraper):
    """Scraper implementation for Lidl website"""
    
    def __init__(self, driver_manager, image_downloader, config=None):
        super().__init__(driver_manager, image_downloader, config)
    
    def handle_popups(self, driver):
        """Handle Lidl-specific popups"""
        wait = WebDriverWait(driver, self.config.get("timeout", 5))
        
        # Handle cookie banner
        try:
            wait.until(EC.presence_of_element_located((By.ID, "onetrust-banner-sdk")))
            cookie_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#onetrust-accept-btn-handler")))
            cookie_btn.click()
            print("✓ Accepted cookies")
            time.sleep(2)
        except TimeoutException:
            print("No cookie banner found")
        
        # Handle store selection popup
        try:
            close_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Übersicht schließen']"))
            )
            close_btn.click()
            print("✓ Closed store selection popup")
            time.sleep(2)
        except TimeoutException:
            print("No store selection popup found")
    
    def find_prospekt_links(self, driver) -> List[Tuple[str, str]]:
        """Find Lidl prospekt links"""
        selectors = [
            "a.flyer[data-track-name='Aktionsprospekt']",
            "a.flyer[data-track-type='flyer']",
            "a[href*='aktionsprospekt']",
            ".flyer"
        ]
        
        links: List[Tuple[str, str]] = []
        for selector in selectors:
            try:
                elements = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                for element in elements:
                    href = element.get_attribute("href")
                    name = element.get_attribute('data-track-name') or element.text or 'Prospekt'
                    if href and not any(href == l[1] for l in links):
                        links.append((name.strip(), href))
                        # print(f"[DEBUG] ✓ Found prospekt: {name}")
                if links:
                    break
            except TimeoutException:
                continue

        return links
    
    def get_high_res_image_url(self, img_element) -> Optional[str]:
        """Extract high-resolution image URL for Lidl"""
        url_attributes = ['data-src', 'data-original', 'data-large', 'src']
        
        for attr in url_attributes:
            url = img_element.get_attribute(attr)
            if url:
                if url.startswith('data:'):
                    continue
                if url.startswith('//'):
                    url = 'https:' + url
                elif url.startswith('/'):
                    url = 'https://www.lidl.de' + url
                
                # Enhance resolution
                if 'w_' in url and 'h_' in url:
                    url = url.replace('w_400', 'w_2000').replace('h_400', 'h_2000')
                    url = url.replace('w_600', 'w_2000').replace('h_600', 'h_2000')
                    url = url.replace('w_800', 'w_2000').replace('h_800', 'h_2000')
                    print(f"[DEBUG] Enhanced resolution in URL (w_): {url}")
                
                if 'q_' in url:
                    url = url.replace('q_auto', 'q_100')
                    print(f"[DEBUG] Enhanced quality in URL (q_): {url}")
                
                return url
        
        return None
    
    def navigate_to_next_page(self, driver) -> bool:
        """Navigate to next page for Lidl prospekt"""
        next_selectors = [
            "div.content_navigation.content_navigation--right button",
            ".content_navigation--right button",
            "button[aria-label*='next']",
            "button[aria-label*='weiter']"
        ]
        
        for selector in next_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for btn in elements:
                    if (btn.is_displayed() and btn.is_enabled() and 
                        not btn.get_attribute("disabled") and 
                        "disabled" not in (btn.get_attribute("class") or "").lower()):
                        driver.execute_script("arguments[0].click();", btn)
                        return True
            except:
                continue
        
        return False
    
    def get_page_images(self, driver) -> List:
        """Get image elements from current page for Lidl"""
        img_selectors = [
            "div.page__wrapper img",
            ".page img",
            ".prospekt-page img",
            "img[src*='prospekt']",
            "img[data-src*='prospekt']",
            "img"
        ]
        
        for selector in img_selectors:
            try:
                img_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if img_elements:
                    return img_elements
            except:
                continue
        
        return []

    def get_week_dates(self, driver) -> Optional[str]:
        """
        Parse week start/end from Lidl prospekt URL, e.g.
        .../aktionsprospekt-DD-MM-YYYY-DD-MM-YYYY-... -> 'YYYY-MM-DD_YYYY-MM-DD'
        If the range looks like Mon-Sat (6 days), optionally extend to Sunday.
        """
        import re
        from datetime import datetime, timedelta

        # Prefer canonical link if present; fall back to current URL
        try:
            url = (driver.find_element(By.XPATH, "//link[@rel='canonical']")
                          .get_attribute("href")) or driver.current_url
        except Exception:
            url = driver.current_url

        m = re.search(r"(\d{2})-(\d{2})-(\d{4}).{0,12}?(\d{2})-(\d{2})-(\d{4})", url)
        if not m:
            return None

        # groups: d1 m1 y1  d2 m2 y2  (dd-mm-YYYY)
        start = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        end   = datetime(int(m.group(6)), int(m.group(5)), int(m.group(4)))

        # OPTIONAL: Lidl links often end on Saturday. Extend to Sunday if want full week.
        #if (end - start).days == 5:  # 6-day range (Mon–Sat)
            # end = end + timedelta(days=1)

        return f"{start:%Y-%m-%d}_{end:%Y-%m-%d}"
class AngeboteScraper(BaseScraper):
    """Scraper implementation for angebote.com"""
    
    def __init__(self, driver_manager, image_downloader, config=None):
        super().__init__(driver_manager, image_downloader, config)
    
    def handle_popups(self, driver):
        """Handle angebote.com popups"""
        # Add angebote.com specific popup handling
        try:
            # Example: Accept cookies if present
            cookie_btn = WebDriverWait(driver, self.config.get("timeout", 5)).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='cookie-accept'], .cookie-accept, #accept-cookies"))
            )
            cookie_btn.click()
            print("✓ Accepted cookies")
            time.sleep(2)
        except TimeoutException:
            print("No cookie banner found")
    
    def find_prospekt_links(self, driver) -> List[Tuple[str, str]]:
        """Find prospekt links on angebote.com"""
        # This would need to be implemented based on angebote.com's structure
        selectors = [
            "a[href*='prospekt']",
            "a[href*='/lidl/woche-']",
            "a[href*='flyer']",
            ".prospekt-link",
            ".flyer-link"
        ]

        links: List[Tuple[str, str]] = []
        for selector in selectors:
            try:
                elements = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                for element in elements:
                    href = element.get_attribute("href")
                    name = element.text or 'Prospekt'
                    if href and not any(href == l[1] for l in links):
                        links.append((name.strip(), href))
                        print(f"✓ Found prospekt: {href}")
                if links:
                    break
            except TimeoutException:
                continue

        return links
    
    def get_week_dates(self, driver) -> Optional[str]:
        """Extract week dates from angebote.com page"""
        import re
        from datetime import datetime
        
         # Find all <a> tags with href containing '/lidl/woche-'
        links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/lidl/woche-']")
        for link in links:
            href = link.get_attribute("href")
            # Debug print
            print(f"Checking href: {href}")
            # Example href: /lidl/woche-26-ab-23-06-2025-bis-28-06-2025-seite-1-zdplp
            match = re.search(r"ab-(\d{2})-(\d{2})-(\d{4})-bis-(\d{2})-(\d{2})-(\d{4})", href)
            if match:
                start_day, start_month, start_year, end_day, end_month, end_year = match.groups()
                start_date = f"{start_year}-{start_month}-{start_day}"
                end_date = f"{end_year}-{end_month}-{end_day}"
                week_range = f"{start_date}_{end_date}"
                print(f"✓ Extracted week dates from href: {week_range}")
                return week_range

        print("⚠ Could not extract week dates from href, using current week")
        return None
    
    def get_high_res_image_url(self, img_element) -> Optional[str]:
        """Extract high-resolution image URL for angebote.com"""
        url_attributes = ['data-src', 'data-original', 'src']
        
        for attr in url_attributes:
            url = img_element.get_attribute(attr)
            if url:
                if url.startswith('data:'):
                    continue
                if url.startswith('//'):
                    url = 'https:' + url
                elif url.startswith('/'):
                    url = 'https://angebote.com' + url
                
                return url
        
        return None
    
    def navigate_to_next_page(self, driver) -> bool:
        """Navigate to next page for angebote.com"""
        next_selectors = [
            "a[href*='seite']",
        ]
        
        for selector in next_selectors:
            try:
                btn = driver.find_element(By.CSS_SELECTOR, selector)
                if btn.is_displayed() and btn.is_enabled():
                    driver.execute_script("arguments[0].click();", btn)
                    return True
            except:
                continue
        
        return False
    
    def get_page_images(self, driver) -> List:
        """Get image elements from current page for angebote.com"""
        img_selectors = [
            ".prospekt-page img",
            ".flyer-page img",
            "img[src*='prospekt']",
            "img[data-src*='prospekt']",
            "img"
        ]
        
        for selector in img_selectors:
            try:
                img_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if img_elements:
                    return img_elements
            except:
                continue
        
        return []

class NettoScraper(BaseScraper):
    """Scraper implementation for Netto website"""
    
    def __init__(self, driver_manager, image_downloader, config=None):
        super().__init__(driver_manager, image_downloader, config)
    
    def handle_popups(self, driver):
        """Handle Netto-specific popups"""
        # As of October 2025, Netto does not have significant popups to handle
    
    def find_prospekt_links(self, driver) -> List[Tuple[str, str]]:
        """Find Netto prospekt links"""        
        links: List[Tuple[str, str]] = []
        
        try: 
            # print(f"[DEBUG] Adding current URL as prospekt link for Netto: {driver.current_url}")
            links.append(("Netto Prospekt", driver.current_url))
        except Exception as e:
            print(f"[ERROR] Could not add current URL as prospekt link: {e}")

        return links
    
    def get_high_res_image_url(self, img_element) -> Optional[str]:
        """Extract high-resolution image URL for Netto. Shouldn't be needed as Netto uses pdf for prospekt"""
        return None
    
    def navigate_to_next_page(self, driver) -> bool:
        """Navigate to next page for Netto prospekt. Netto prospekts are PDFs, so this is not applicable."""
        return False
    
    def get_pdf_url(self, driver, selector: str = "#downloadAsPdf", timeout_s: int = 10):
        """Return the PDF href from the Netto 'PDF herunterladen' button, or None."""
        print(f"[DEBUG] Looking for PDF download link using selector: {selector}")
        try:
            el = WebDriverWait(driver, timeout_s).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            href = (el.get_attribute("href") or "").strip()
            return href or None
        except Exception:
            print(f"[DEBUG] No PDF download link found with selector: {selector}")
            return None
    
    def get_page_images(self, driver) -> List:
        """
        Netto override: if a 'PDF herunterladen' link is present, download & split PDF into page_XX.jpg files.
        """
        pdf_url = self.get_pdf_url(driver)
        self.config['download_path'] = os.path.join(self.config['download_path'], self.week)
        if pdf_url:
            print(f"✓ Found Netto PDF: {pdf_url}")
            pages = self._download_and_split_pdf_to_jpegs(pdf_url, self.config['download_path'])
            if pages:
                print(f"✓ Saved {len(pages)} pages to {self.config['download_path']}/")
                return pages
            else:
                raise Exception("✗ PDF download/split failed or produced no pages")

    def get_week_dates(self, driver) -> Optional[str]:
        """Extract week dates from img[alt]; fallback case is  Mon-Sat."""
        try:
            alts = " ".join(
                (el.get_attribute("alt") or "").strip()
                for el in driver.find_elements(By.CSS_SELECTOR, "img[alt]")
            )
        except Exception:
            alts = ""

        # dd.mm.yy
        m = re.findall(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2})\b", alts)
        if len(m) >= 2:
            dates = []
            for d, mo, y in m:
                y = int(y);  y = y + 2000
                try:
                    dates.append(datetime(y, int(mo), int(d)))
                except ValueError:
                    pass
            if len(dates) >= 2:
                start, end = min(dates), max(dates)
                week = f"{start:%Y-%m-%d}_{end:%Y-%m-%d}"
                self.week = week
                return week

        # Fallback: current Monday to Saturday
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        saturday = monday + timedelta(days=5)
        return f"{monday:%Y-%m-%d}_{saturday:%Y-%m-%d}"

    
    @staticmethod
    def _download_and_split_pdf_to_jpegs(pdf_url: str, out_dir: str | Path) -> list[str]:
        """
        Download a PDF and render each page to JPEG:
        page_01.jpg, page_02.jpg, ...
        Always deletes the temporary PDF at the end.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # 1) download to temp file
        headers = {"User-Agent": "Mozilla/5.0"}
        tmp_pdf_path = None
        saved: list[str] = []
        try:
            with requests.get(pdf_url, headers=headers, stream=True, timeout=30) as r:
                r.raise_for_status()
                fd, tmp_pdf_path = tempfile.mkstemp(suffix=".pdf")
                with os.fdopen(fd, "wb") as f:
                    for chunk in r.iter_content(65536):
                        if chunk:
                            f.write(chunk)

            # 2) render to JPEGs (≈200 DPI)
            doc = fitz.open(tmp_pdf_path)
            zoom = 200 / 72.0
            mat = fitz.Matrix(zoom, zoom)
            for i, page in enumerate(doc, start=1):
                pix = page.get_pixmap(matrix=mat, alpha=False)
                out_path = out_dir / f"page_{i:02d}.jpg"
                pix.save(out_path.as_posix(), jpg_quality=92)
                saved.append(out_path.name)  # return basenames to match existing behavior
            doc.close()
            return saved
        finally:
            if tmp_pdf_path and os.path.exists(tmp_pdf_path):
                try:
                    os.remove(tmp_pdf_path)
                except Exception:
                    pass

class AldiScraper(BaseScraper):
    """Scraper implementation for Aldi website"""
    week = ""
    def __init__(self, driver_manager, image_downloader, config=None):
        super().__init__(driver_manager, image_downloader, config)
    
    def handle_popups(self, driver):
        """Handle Aldi-specific popups"""
        # As of October 2025, Aldi does not have significant popups to handle

    def find_prospekt_links(self, driver) -> List[Tuple[str, str]]:
        """Find the Aldi flyer link that sits in the <p> after <h2> 'AKTUELLE WOCHE'."""
        selectors = [
            "a[href*='prospekt.aldi-sued.de']",
        ]
        
        links: List[Tuple[str, str]] = []
        
        for selector in selectors:
            try:
                elements = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                for element in elements:
                    href = element.get_attribute("href")
                    if href and not any(href == l[1] for l in links):
                        links.append(('Aldi Prospekt', href))
                        # print(f"[DEBUG] ✓ Found prospekt: {name}")
                if links:
                    break
            except TimeoutException:
                print("[DEBUG] No prospekt links found with selector:", selector)
                continue
        
        return links
    
    def get_high_res_image_url(self, img_element) -> Optional[str]:
        """Extract high-resolution image URL for Aldi. Shouldn't be needed as Aldi uses pdf for prospekt"""
        return None
    
    def navigate_to_next_page(self, driver) -> bool:
        """Navigate to next page for Aldi prospekt. Aldi prospekts are PDFs, so this is not applicable."""
        return False
    
    def get_pdf_url(self, driver, selector: str = "#downloadAsPdf", timeout_s: int = 10):
        """Return the PDF href from the Aldi 'PDF herunterladen' button, or None."""
        print(f"[DEBUG] Looking for PDF download link using selector: {selector}")
        try:
            el = WebDriverWait(driver, timeout_s).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            href = (el.get_attribute("href") or "").strip()
            return href or None
        except Exception:
            print(f"[DEBUG] No PDF download link found with selector: {selector}")
            return None
    
    def get_page_images(self, driver) -> List:
        """
        Aldi override: if a 'PDF herunterladen' link is present, download & split PDF into page_XX.jpg files.
        """
        pdf_url = self.get_pdf_url(driver)
        self.config['download_path'] = os.path.join(self.config['download_path'], self.week)
        if pdf_url:
            print(f"✓ Found Aldi PDF: {pdf_url}")
            pages = self._download_and_split_pdf_to_jpegs(pdf_url, self.config['download_path'])
            if pages:
                print(f"✓ Saved {len(pages)} pages to {self.config['download_path']}/")
                return pages
            else:
                raise Exception("✗ PDF download/split failed or produced no pages")

    def get_week_dates(self, driver) -> Optional[str]:
        """Extract week dates from url; fallback case is  Mon-Sat."""
        print(f"[DEBUG] Current URL for week extraction: {driver.current_url}")
        m = re.search(r'KW(\d+)', driver.current_url, re.IGNORECASE)
        try:
            week_number = int(m.group(1)) if m else None
            print(f"[DEBUG] Extracted week number from URL: {week_number}")
            year = date.today().year
            # ISO: weekday 1=Mon ... 7=Sun
            monday = date.fromisocalendar(year, week_number, 1)
            saturday = date.fromisocalendar(year, week_number, 6)
            self.week = f"{monday:%Y-%m-%d}_{saturday:%Y-%m-%d}"
            print(f"[DEBUG] Computed week range: {self.week}")
            return self.week
        except Exception:
            print("[DEBUG] Could not extract week dates from href, using current week")
            pass
        # Fallback: current Monday to Saturday
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        saturday = monday + timedelta(days=5)
        return f"{monday:%Y-%m-%d}_{saturday:%Y-%m-%d}"

    # def week_to_range(week: int, year: int | None = None) -> str:
    #     """
    #     Returns 'YYYY-MM-DD_YYYY-MM-DD' for the Monday..Saturday of the given ISO week.
    #     If year is omitted, uses the current year.
    #     """
    #     print(f"[DEBUG] Converting week number {week} to date range")
    #     if year is None:
        
    
    @staticmethod
    def _download_and_split_pdf_to_jpegs(pdf_url: str, out_dir: str | Path) -> list[str]:
        """
        Download a PDF and render each page to JPEG:
        page_01.jpg, page_02.jpg, ...
        Always deletes the temporary PDF at the end.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # 1) download to temp file
        headers = {"User-Agent": "Mozilla/5.0"}
        tmp_pdf_path = None
        saved: list[str] = []
        try:
            with requests.get(pdf_url, headers=headers, stream=True, timeout=30) as r:
                r.raise_for_status()
                fd, tmp_pdf_path = tempfile.mkstemp(suffix=".pdf")
                with os.fdopen(fd, "wb") as f:
                    for chunk in r.iter_content(65536):
                        if chunk:
                            f.write(chunk)

            # 2) render to JPEGs (≈200 DPI)
            doc = fitz.open(tmp_pdf_path)
            zoom = 200 / 72.0
            mat = fitz.Matrix(zoom, zoom)
            for i, page in enumerate(doc, start=1):
                pix = page.get_pixmap(matrix=mat, alpha=False)
                out_path = out_dir / f"page_{i:02d}.jpg"
                pix.save(out_path.as_posix(), jpg_quality=92)
                saved.append(out_path.name)  # return basenames to match existing behavior
            doc.close()
            return saved
        finally:
            if tmp_pdf_path and os.path.exists(tmp_pdf_path):
                try:
                    os.remove(tmp_pdf_path)
                except Exception:
                    pass
class ScraperFactory:
    """Factory class to create appropriate scraper instances"""
    
    @staticmethod
    def create_scraper(url: str, driver_manager: WebDriverManager, image_downloader: ImageDownloader, config: dict = None) -> BaseScraper:
        """Create appropriate scraper based on URL"""
        if 'lidl.de' in url:
            return LidlScraper(driver_manager, image_downloader, config)
        elif 'angebote.com' in url:
            return AngeboteScraper(driver_manager, image_downloader, config)
        elif 'netto-online.de' in url:
            return NettoScraper(driver_manager, image_downloader, config)
        elif 'aldi-sued.de' in url:
            return AldiScraper(driver_manager, image_downloader, config)
        else:
            raise ValueError(f"No scraper available for URL: {url}")
