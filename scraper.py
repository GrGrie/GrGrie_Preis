import time
import os
import requests
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import json

class WebDriverManager:
    """Manages WebDriver setup and configuration"""
    
    def __init__(self, headless=True, window_size="960,1080"):
        self.headless = headless
        self.window_size = window_size
    
    def setup_driver(self):
        """Setup Chrome driver with options"""
        options = Options()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"--window-size={self.window_size}")
        return webdriver.Chrome(options=options)

class ImageDownloader:
    """Handles image downloading functionality"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def download_image(self, url: str, filepath: str, headers: Optional[Dict] = None) -> bool:
        """Download image from URL to filepath"""
        try:
            if headers is None:
                headers = self.headers
            
            response = requests.get(url, headers=headers, stream=True)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return True
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return False

class DirectoryManager:
    """Manages directory creation and file paths"""
    
    @staticmethod
    def get_week_folder() -> str:
        """Get the current week folder name in format YYYY-MM-DD_YYYY-MM-DD"""
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return f"{monday.strftime('%Y-%m-%d')}_{sunday.strftime('%Y-%m-%d')}"
    
    @staticmethod
    def create_download_directory(base_path: str, subfolder: str = None) -> str:
        """Create and return download directory path"""
        if subfolder is None:
            subfolder = DirectoryManager.get_week_folder()
        
        download_dir = os.path.join(base_path, subfolder)
        os.makedirs(download_dir, exist_ok=True)
        return download_dir

class BaseScraper(ABC):
    """Abstract base class for website scrapers"""
    
    def __init__(self, driver_manager: WebDriverManager, image_downloader: ImageDownloader):
        self.driver_manager = driver_manager
        self.image_downloader = image_downloader
        self.driver = None
    
    @abstractmethod
    def handle_popups(self, driver) -> None:
        """Handle website-specific popups"""
        pass
    
    @abstractmethod
    def find_prospekt_links(self, driver) -> List[Tuple[str, str]]:
        """Find and return (name, url) tuples for available prospekts"""
        pass
    
    @abstractmethod
    def get_high_res_image_url(self, img_element) -> Optional[str]:
        """Extract high-resolution image URL from img element"""
        pass
    
    @abstractmethod
    def navigate_to_next_page(self, driver) -> bool:
        """Navigate to next page, return True if successful"""
        pass
    
    @abstractmethod
    def get_page_images(self, driver) -> List:
        """Get all image elements from current page"""
        pass
    
    def get_week_dates(self, driver) -> Optional[str]:
        """Extract week dates from the page, return in YYYY-MM-DD_YYYY-MM-DD format"""
        return None  # Default implementation returns None

    def select_prospekt(self, prospekt_links: List[Tuple[str, str]], index: int) -> str:
        """Return the URL of the prospekt specified by a 1-based index"""
        if not prospekt_links:
            raise ValueError("No prospekt links available")
        if index < 1 or index > len(prospekt_links):
            print(f"⚠ Invalid prospekt index {index}, defaulting to 1")
            index = 1
        name, url = prospekt_links[index - 1]
        print(f"Using prospekt #{index}: {name}")
        return url
    
    def setup_driver(self):
        """Setup and return driver"""
        self.driver = self.driver_manager.setup_driver()
        return self.driver
    
    def download_page_images(self, driver, download_dir: str) -> List[str]:
        """Navigate through pages and download images"""
        page = 1
        max_pages = 100
        downloaded_images = []
        downloaded_urls = set()
        
        while page <= max_pages:
            time.sleep(3)
            
            try:
                # Wait for page content to load
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
                )
                
                images_found = False
                page_urls = set()
                
                img_elements = self.get_page_images(driver)
                
                for i, img in enumerate(img_elements):
                    # Skip very small images
                    try:
                        width = img.get_attribute('width') or img.get_attribute('naturalWidth')
                        height = img.get_attribute('height') or img.get_attribute('naturalHeight')
                        
                        if width and height:
                            if int(width) < 200 or int(height) < 200:
                                continue
                    except:
                        pass
                    
                    img_url = self.get_high_res_image_url(img)
                    if img_url and img_url not in downloaded_urls and img_url not in page_urls:
                        filename = f"page_{page:02d}.jpg"
                        filepath = os.path.join(download_dir, filename)
                        
                        if self.image_downloader.download_image(img_url, filepath):
                            downloaded_images.append(filename)
                            downloaded_urls.add(img_url)
                            page_urls.add(img_url)
                            images_found = True
                            print(f"  ✓ Downloaded: {filename}")
                            break
                        else:
                            print(f"  ✗ Failed to download: {filename}")
                
                if not images_found:
                    print(f"  No images found on page {page}")
                
            except Exception as e:
                print(f"Error processing page {page}: {e}")
            
            # Try to navigate to next page
            if not self.navigate_to_next_page(driver):
                print("No more pages found")
                break
                
            page += 1
        
        return downloaded_images
    
    def scrape(self, url: str, download_path: str = "data/originals", prospekt_index: int = 1) -> Dict:
        """Main scraping method"""
        results = {
            'success': False,
            'downloaded_images': [],
            'download_dir': '',
            'error': None
        }
        
        driver = self.setup_driver()
        
        try:
            print(f"Opening {url}...")
            driver.get(url)
            
            # Handle popups
            self.handle_popups(driver)
            
            # Find prospekt links
            prospekt_links = self.find_prospekt_links(driver)
            if not prospekt_links:
                results['error'] = "Could not find any prospekt links"
                return results

            print("Available prospekts:")
            for idx, (name, link) in enumerate(prospekt_links, 1):
                print(f"  {idx}. {name} - {link}")

            # Choose prospekt
            prospekt_url = self.select_prospekt(prospekt_links, prospekt_index)

            # Open prospekt
            if prospekt_url != url:  # Only navigate if it's a different URL
                driver.get(prospekt_url)
                time.sleep(5)
            
            # Extract week dates from the actual prospekt    
            week_dates = self.get_week_dates(driver)
            
            # Create download directory
            if week_dates:
                download_dir = DirectoryManager.create_download_directory(download_path, week_dates)
            else:
                download_dir = DirectoryManager.create_download_directory(download_path)
            
            print(f"Created directory: {download_dir}")
            
            # Download images
            downloaded_images = self.download_page_images(driver, download_dir)
            print(f"✓ Downloaded {len(downloaded_images)} images to {download_dir}/")
            
            results.update({
                'success': True,
                'downloaded_images': downloaded_images,
                'download_dir': download_dir,
                'week_dates': week_dates
            })
            
        except Exception as e:
            results['error'] = str(e)
            print(f"Error: {e}")
        finally:
            driver.quit()
        
        return results

class LidlScraper(BaseScraper):
    """Scraper implementation for Lidl website"""
    
    def handle_popups(self, driver):
        """Handle Lidl-specific popups"""
        wait = WebDriverWait(driver, 10)
        
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
                        print(f"✓ Found prospekt: {name}")
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

class AngeboteScraper(BaseScraper):
    """Scraper implementation for angebote.com"""
    
    def handle_popups(self, driver):
        """Handle angebote.com popups"""
        # Add angebote.com specific popup handling
        try:
            # Example: Accept cookies if present
            cookie_btn = WebDriverWait(driver, 5).until(
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
    def create_scraper(url: str, driver_manager: WebDriverManager, image_downloader: ImageDownloader) -> BaseScraper:
        """Create appropriate scraper based on URL"""
        if 'lidl.de' in url:
            return LidlScraper(driver_manager, image_downloader)
        elif 'angebote.com' in url:
            return AngeboteScraper(driver_manager, image_downloader)
        else:
            raise ValueError(f"No scraper available for URL: {url}")

# Configuration management
class ScraperConfig:
    """Configuration class for scraper settings"""
    
    def __init__(self, config_file: str = "scraper_config.json"):
        self.config_file = config_file
        self.default_config = {
            "headless": True,
            "window_size": "960,1080",
            "download_path": "data/originals",
            "max_pages": 100,
            "timeout": 10
        }
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load configuration from file or use defaults"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return {**self.default_config, **json.load(f)}
            except:
                return self.default_config
        return self.default_config
    
    def save_config(self):
        """Save current configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

def main():
    """Main function with command line argument support"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Web scraper for prospekt/flyer websites')
    parser.add_argument('--url', '-u', type=str, help='URL to scrape')
    parser.add_argument('--site', '-s', type=str, choices=['lidl', 'angebote', 'all'], 
                       help='Predefined site to scrape')
    parser.add_argument('--headless', action='store_true', default=None,
                       help='Run browser in headless mode')
    parser.add_argument('--no-headless', action='store_true', default=None,
                       help='Run browser in visible mode')
    parser.add_argument('--download-path', '-d', type=str, 
                       help='Download path for images')
    parser.add_argument('--list-sites', action='store_true',
                       help='List available predefined sites')
    parser.add_argument('--prospekt-index', '--num_prospekt', '--num-prospekt',
                        type=int, default=1,
                        help='Which prospekt to download (1-based index)')

    args = parser.parse_args()
    
    # Load configuration
    config = ScraperConfig()
    
    # Override config with command line arguments
    if args.headless is not None:
        config.config['headless'] = True
    elif args.no_headless is not None:
        config.config['headless'] = False
    
    if args.download_path:
        config.config['download_path'] = args.download_path
    
    # List available sites
    if args.list_sites:
        print("Available predefined sites:")
        for site_key, site_info in config.config.get('sites', {}).items():
            print(f"  {site_key}: {site_info['name']} - {site_info['base_url']}")
        return
    
    # Setup components
    driver_manager = WebDriverManager(
        headless=config.config['headless'],
        window_size=config.config['window_size']
    )
    image_downloader = ImageDownloader()
    
    # Determine URLs to scrape
    urls = get_urls_to_scrape(args, parser, config)
    if not urls:
        print("No URLs provided to scrape. Exiting.")
        return
    
    # Scrape each URL
    for url in urls:
        print(f"\n{'='*50}")
        print(f"Scraping: {url}")
        print(f"{'='*50}")
        
        try:
            scraper = ScraperFactory.create_scraper(url, driver_manager, image_downloader)
            results = scraper.scrape(url, config.config['download_path'], args.prospekt_index)
            
            if results['success']:
                print(f"✓ Successfully scraped {len(results['downloaded_images'])} images")
                print(f"  Saved to: {results['download_dir']}")
            else:
                print(f"✗ Scraping failed: {results['error']}")
                
        except ValueError as e:
            print(f"✗ {e}")
        except Exception as e:
            print(f"✗ Unexpected error: {e}")

def get_urls_to_scrape(args, parser, config) -> list:
    """Determine URLs to scrape based on CLI arguments and config."""
    urls = []
    if args.url:
        # Custom URL provided
        urls = [args.url]
    elif args.site:
        # Predefined site
        site = args.site.lower()
        if site == 'lidl':
            urls = ["https://www.lidl.de/c/online-prospekte/s10005610"]
        elif site == 'angebote':
            urls = ["https://angebote.com/lidl/archives?page=1"]
        elif site == 'all':
            urls = [
                "https://www.lidl.de/c/online-prospekte/s10005610",
                "https://angebote.com/lidl/archives?page=1"
            ]
    else:
        # No arguments provided - show help
        parser.print_help()
        print("\nExamples:")
        print("  python newscraper.py --url 'https://angebote.com/lidl/archives?page=1'")
        print("  python newscraper.py --site lidl")
        print("  python newscraper.py --site angebote --no-headless")
        print("  python newscraper.py --url 'https://example.com' --download-path '/custom/path'")
        return []
    return urls

if __name__ == "__main__":
    main()