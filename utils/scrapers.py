from utils.basescraper import BaseScraper  
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
import time
from typing import List, Tuple, Optional

from utils.web_driver_manager import WebDriverManager
from utils.image_downloader import ImageDownloader

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
                
                if 'q_' in url:
                    url = url.replace('q_auto', 'q_100')
                
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

        # OPTIONAL: Lidl links often end on Saturday. Extend to Sunday if you want full week.
        if (end - start).days == 5:  # 6-day range (Mon–Sat)
            end = end + timedelta(days=1)

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
class ScraperFactory:
    """Factory class to create appropriate scraper instances"""
    
    @staticmethod
    def create_scraper(url: str, driver_manager: WebDriverManager, image_downloader: ImageDownloader, config: dict = None) -> BaseScraper:
        """Create appropriate scraper based on URL"""
        if 'lidl.de' in url:
            return LidlScraper(driver_manager, image_downloader, config)
        elif 'angebote.com' in url:
            return AngeboteScraper(driver_manager, image_downloader, config)
        else:
            raise ValueError(f"No scraper available for URL: {url}")
