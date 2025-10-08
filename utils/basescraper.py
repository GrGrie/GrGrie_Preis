from utils.utils import DirectoryManager
from utils.utils import WebDriverManager
from utils.utils import ImageDownloader

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import os


class BaseScraper(ABC):
    """Abstract base class for website scrapers"""
    
    def __init__(self, driver_manager: WebDriverManager, image_downloader: ImageDownloader, config: dict = None):
        self.driver_manager = driver_manager
        self.image_downloader = image_downloader
        self.driver = None
        self.config = config or {}
        self.max_pages = self.config.get('max_pages', 100)
        self.timeout = self.config.get('timeout', 5)

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
        return None

    def select_prospekt(self, prospekt_links: List[Tuple[str, str]], index: int) -> str:
        """Return the URL of the prospekt specified by a 1-based index"""
        if not prospekt_links:
            raise ValueError("No prospekt links available")
        if index < 1 or index > len(prospekt_links):
            print(f"⚠ Invalid prospekt index {index}, defaulting to 1")
            index = 1
        name, url = prospekt_links[index - 1]
        # print(f"[DEBUG] Using prospekt #{index}: {name}")
        return url
    
    def setup_driver(self):
        """Setup and return driver"""
        self.driver = self.driver_manager.setup_driver()
        return self.driver
    
    def download_page_images(self, driver, download_dir: str) -> List[str]:
        """Navigate through pages and download images or handle PDF if applicable"""
        
        page = 1
        max_pages = self.max_pages
        downloaded_images = []
        downloaded_urls = set()
        
        while page <= max_pages:
            time.sleep(1)
            
            try:
                # Wait for page content to load
                WebDriverWait(driver, self.timeout).until(
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
                print("  No more pages found")
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
        
        try:
            print(f"[DEBUG] Starting scrape for {url}. Setting up driver...")
            driver = self.setup_driver()
            print(f"[DEBUG] Opening {url} ...")
            driver.get(url)
            print(f"[DEBUG] Page loaded. Handling popups...")
            
            # Handle popups
            self.handle_popups(driver)
            print(f"[DEBUG] Popups handled. Finding prospekt links...")
            
            # Find prospekt links
            prospekt_links = self.find_prospekt_links(driver)
            if not prospekt_links:
                results['error'] = "Could not find any prospekt links"
                return results

            print("Available prospekts:")
            for idx, (name, link) in enumerate(prospekt_links, 1):
                print(f"  {idx}. {name} - {link}")

            # Choose prospekt
            print(f"[DEBUG] Selecting prospekt #{prospekt_index} ...")
            prospekt_url = self.select_prospekt(prospekt_links, prospekt_index)

            # Open prospekt
            if prospekt_url != url:  # Only navigate if it's a different URL
                driver.get(prospekt_url)
                time.sleep(5)
            
            # Extract week dates from the actual prospekt  
            print(f"[DEBUG] Extracting week dates...")  
            week_dates = self.get_week_dates(driver)
            
            # Create download directory
            if week_dates:
                print(f"[DEBUG] Creating download directory for week: {week_dates}")
                download_dir = DirectoryManager.create_download_directory(download_path, week_dates)
            else:
                print("[DEBUG] Could not determine week dates, using current week folder")
                download_dir = DirectoryManager.create_download_directory(download_path)
                        
            # Download images
            print(f"[DEBUG] Starting image download to {download_dir} ...")
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
