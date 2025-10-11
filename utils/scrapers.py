from utils.basescraper import BaseScraper  
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
import time, re
from datetime import datetime, timedelta
from typing import List, Tuple, Optional


from utils.utils import WebDriverManager, ImageDownloader

class LidlScraper(BaseScraper):
    """Scraper implementation for Lidl website"""
    
    def __init__(self, driver_manager, image_downloader, config=None):
        super().__init__(driver_manager, image_downloader, config)
        self.contains_popups = True
        self.contains_pdf = False
    
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
    
    def find_scrapable_url(self, driver) -> List[Tuple[str, str]]:
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

    def get_week_dates(self, driver, url) -> Optional[str]:
        """
        Parse week start/end from Lidl prospekt URL, e.g.
        .../aktionsprospekt-DD-MM-YYYY-DD-MM-YYYY-... -> 'YYYY-MM-DD_YYYY-MM-DD'
        If the range looks like Mon-Sat (6 days) """
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

        return f"{start:%Y-%m-%d}_{end:%Y-%m-%d}"
class NettoScraper(BaseScraper):
    """Scraper implementation for Netto website"""
    
    def __init__(self, driver_manager, image_downloader, config=None):
        super().__init__(driver_manager, image_downloader, config)
        self.contains_popups = False
        self.contains_pdf = True
    
    def handle_popups(self, driver):
        """Handle Netto-specific popups"""
        # As of October 2025, Netto does not have significant popups to handle
        pass
    
    def find_scrapable_url(self, driver) -> List[Tuple[str, str]]:
        """Find Netto prospekt link to download PDF"""
        selector = "a[href*='wochenprospekt.netto-online.de/hz']"
        
        
        links: List[Tuple[str, str]] = []
        try:
            element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((
                By.CSS_SELECTOR, selector
            )))
            href = element.get_attribute("href")
            if href:
                    print(f"[DEBUG] ✓ Found prospekt link: {href}")
                    driver.get(href)
                    pdf_url = self.get_pdf_url(driver)
                    if pdf_url:
                        print(f"[DEBUG] ✓ Found PDF link: {pdf_url}")
                        links.append(('Netto Prospekt: ', pdf_url))
                    return links
        except Exception:
            print("[DEBUG] No prospekt links found with selector:", selector)
            pass
        
        print("[DEBUG] No prospekt links found for Netto")
        return links
    
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

    def get_week_dates(self, driver, pdf_url) -> str:
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
                print(f"[DEBUG] Extracted week dates from PDF: {week}")
                return week

        # Fallback: current Monday to Saturday
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        saturday = monday + timedelta(days=5)
        return f"{monday:%Y-%m-%d}_{saturday:%Y-%m-%d}"

class AldiScraper(BaseScraper):
    """Scraper implementation for Aldi website"""
    def __init__(self, driver_manager, image_downloader, config=None):
        super().__init__(driver_manager, image_downloader, config)
        self.contains_popups = False
        self.contains_pdf = True
    
    def handle_popups(self, driver):
        """Handle Aldi-specific popups"""
        # As of October 2025, Aldi does not have significant popups to handle

    def find_scrapable_url(self, driver) -> List[Tuple[str, str]]:
        """Find the Aldi flyer link that sits in the <p> after <h2> 'AKTUELLE WOCHE'."""
        selector = "a[href*='prospekt.aldi-sued.de']"
        
        links: List[Tuple[str, str]] = []

        try:
            el = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            href = el.get_attribute("href")
            if href:
                print(f"[DEBUG] ✓ Found prospekt link: {href}")
                driver.get(href)
                pdf_url = self.get_pdf_url(driver)
                if pdf_url:
                    links.append(('Aldi Prospekt: ', pdf_url))
        except TimeoutException:
            print("[DEBUG] No prospekt links found with selector:", selector)
            pass
        
        return links
    
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

    def get_week_dates(self, driver, pdf_url) -> str:
        """Extract week dates from img[alt]; fallback case is  Mon-Sat."""
        try:
            alts = " ".join(
                (el.get_attribute("alt") or "").strip()
                for el in driver.find_elements(By.CSS_SELECTOR, "img[alt]")
            )
        except Exception:
            print("[DEBUG] Error collecting alt texts")
            alts = ""

        m = re.search(r"von Mo\. (\d{1,2})\.(\d{1,2})\. – Sa\. (\d{1,2})\.(\d{1,2})\.", alts)
        if m:
            start_day, start_month, end_day, end_month = m.groups()
            if int(start_month) != 12 or int(end_month) != 1:
                start_year = end_year = datetime.now().year
            else:
                start_year = datetime.now().year
                end_year = start_year + 1
            start_date = datetime(int(start_year), int(start_month), int(start_day))
            end_date = datetime(int(end_year), int(end_month), int(end_day))
            week = f"{start_date:%Y-%m-%d}_{end_date:%Y-%m-%d}"
            print(f"[DEBUG] Extracted week dates from alt text: {week}")
            return week

        # Fallback: current Monday to Saturday
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        saturday = monday + timedelta(days=5)
        week = f"{monday:%Y-%m-%d}_{saturday:%Y-%m-%d}"
        print(f"[DEBUG] Using fallback week: " + week)
        return week
class KauflandScraper(BaseScraper):
    """Scraper implementation for Kaufland website"""
    
    def __init__(self, driver_manager, image_downloader, config=None):
        super().__init__(driver_manager, image_downloader, config)
        self.contains_popups = False
        self.contains_pdf = True

    def handle_popups(self, driver):
        """Handle Kaufland-specific popups"""
        # As of October 2025, Kaufland does not have significant popups to handle
        pass
    
    def find_scrapable_url(self, driver, selector: str = "[data-t-name='FlyerTile']") -> List[Tuple[str, str]]:
        """Find and return list of (name, url) tuples for available prospekts. 
        If found PDF URL, return [("PDF", pdf_url)]"""
        
        print(f"[DEBUG] Looking for PDF download link using selector: {selector}")
        try:
            el = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            href = (el.get_attribute("data-download-url") or "").strip()
            self.data_download_url = href
            return [("PDF", href)] if href else []
        except Exception:
            print(f"[DEBUG] No PDF download link found with selector: {selector}")
            return []

    def get_week_dates(self, driver, pdf_url) -> str:
        """Extract week dates from data_download_url; fallback case is Mon-Sat."""
        print(f"[DEBUG] Current URL for week extraction: {pdf_url}")

        # Look for pattern: Prospekt-DD-MM-YYYY-DD-MM-YYYY
        m = re.search(r'Prospekt-(\d{2})-(\d{2})-(\d{4})-(\d{2})-(\d{2})-(\d{4})', pdf_url)
        try:
            if m:
                start_day, start_month, start_year, end_day, end_month, end_year = m.groups()
                start_date = f"{start_year}-{start_month}-{start_day}"
                end_date = f"{end_year}-{end_month}-{end_day}"
                self.week = f"{start_date}_{end_date}"
                # print(f"[DEBUG] Extracted dates from URL: {start_day}-{start_month}-{start_year} to {end_day}-{end_month}-{end_year}")
                print(f"[DEBUG] Computed week range: {self.week}")
                return self.week
            else:
                print(f"[DEBUG] No date pattern found in URL: {pdf_url}")
        except Exception as e:
            print(f"[DEBUG] Error extracting dates: {e}")
            pass
            
        # Fallback: current Monday to Saturday
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        saturday = monday + timedelta(days=5)
        fallback_week = f"{monday:%Y-%m-%d}_{saturday:%Y-%m-%d}"
        print(f"[DEBUG] Using fallback week: {fallback_week}")
        return fallback_week

class ScraperFactory:
    """Factory class to create appropriate scraper instances"""

    DEFAULT_START_URLS = {
        "lidl":      "https://www.lidl.de/c/online-prospekte/s10005610",
        "netto":     "https://www.netto-online.de/filialen/kaiserslautern/carl-euler-str-4/8135",
        "aldi":      "https://www.aldi-sued.de/de/angebote/prospekte.html",   
        "kaufland":  "https://filiale.kaufland.de/prospekte.html?intcid=Home+Marketplace_None_None_Leaflets",
    }

    @staticmethod
    def supported_sites() -> list[str]:
        """Short keys the CLI can offer (used by --site choices and 'all')."""
        return list(ScraperFactory.DEFAULT_START_URLS.keys())

    @staticmethod
    def start_url_for(site_key: str) -> str:
        """Return canonical start URL for a site key."""
        try:
            return ScraperFactory.DEFAULT_START_URLS[site_key]
        except KeyError:
            raise ValueError(f"Unknown site key: {site_key}")

    @staticmethod
    def create_scraper(url: str, driver_manager: WebDriverManager,
                       image_downloader: ImageDownloader, config: dict = None) -> BaseScraper:
        """Create appropriate scraper based on URL"""
        if 'lidl.de' in url:
            return LidlScraper(driver_manager, image_downloader, config)
        elif 'netto-online.de' in url:
            return NettoScraper(driver_manager, image_downloader, config)
        elif 'aldi-sued.de' in url or 'prospekt.aldi-sued.de' in url or 'aldi-sued' in url:
            return AldiScraper(driver_manager, image_downloader, config)
        elif 'kaufland.de' in url:
            return KauflandScraper(driver_manager, image_downloader, config)
        else:
            raise ValueError(f"No scraper available for URL: {url}")