import tempfile
import fitz
import requests
from utils.utils import DirectoryManager, WebDriverManager, ImageDownloader
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict
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
        self.contains_pdf = self.config.get('download_pdf_if_available', True)
        self.contains_popups = False

    @abstractmethod
    def handle_popups(self, driver):
        """Handle any popups specific to the site"""
        pass
    
    @abstractmethod
    def find_scrapable_url(self, driver) -> List[Tuple[str, str]]:
        """Find and return list of (name, url) tuples for available prospekts. If found PDF URL, return [("PDF", pdf_url)]"""
        pass
    
    @abstractmethod
    def get_week_dates(self, driver) -> str:
        """Extract and return the week date range string from the page"""
        pass
    
    def setup_driver(self):
        """Setup and return driver"""
        self.driver = self.driver_manager.setup_driver()
        return self.driver
    
    def download_images_from_url(self, driver, download_dir: str) -> List[str]:
        """Navigate through pages and download images"""
        
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

    def download_available_pdf(self, pdf_url: str, save_dir: str) -> List[str]:
        """
        Download a PDF and render each page to JPEG:
        page_01.jpg, page_02.jpg, ...
        Always deletes the temporary PDF at the end.
        """
        headers = {"User-Agent": "Mozilla/5.0"}
        tmp_pdf_path = None
        saved: list[str] = []
        try:
            # Download PDF to temp file
            with requests.get(pdf_url, headers=headers, stream=True, timeout=30) as r:
                r.raise_for_status()
                fd, tmp_pdf_path = tempfile.mkstemp(suffix=".pdf")
                with os.fdopen(fd, "wb") as f:
                    for chunk in r.iter_content(65536):
                        if chunk:
                            f.write(chunk)

            # Open PDF and save each page as JPEG
            doc = fitz.open(tmp_pdf_path)
            for i, page in enumerate(doc, start=1):
                pix = page.get_pixmap()
                out_path = os.path.join(save_dir, f"page_{i:02d}.jpg")
                pix.save(out_path)
                saved.append(f"page_{i:02d}.jpg")
            doc.close()
            return saved
        finally:
            if tmp_pdf_path and os.path.exists(tmp_pdf_path):
                try:
                    os.remove(tmp_pdf_path)
                except Exception:
                    pass
    
    def scrape(self, url: str, download_path: str = "data/originals") -> Dict:
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
            
            if self.contains_popups:
                print(f"[DEBUG] Page loaded. Handling popups...")
                self.handle_popups(driver)
                print(f"[DEBUG] Popups successfully handled")
            
            # Find scrapable URLs
            print(f"[DEBUG] Finding scrapable URLs...")
            scrapable_urls = self.find_scrapable_url(driver)
            if not scrapable_urls:
                results['error'] = "Could not find any scrapable URLs"
                return results

            print(f"[DEBUG] Selecting url {scrapable_urls[0][1]} ...")
            final_url = scrapable_urls[0][1] if scrapable_urls else None

            # Open prospekt if it's a different URL and we are not dealing with a PDF
            if final_url != url and not self.contains_pdf:
                driver.get(final_url)
                time.sleep(5)
            
            # Extract week dates from the actual prospekt  
            print(f"[DEBUG] Extracting week dates...")  
            week_dates = self.get_week_dates(driver, final_url)
            
            # Create download directory
            print(f"[DEBUG] Creating download directory for week: {week_dates}")
            download_dir = DirectoryManager.create_download_directory(download_path, week_dates)
        
            # Download images or PDF
            print(f"[DEBUG] Starting image download to {download_dir} ...")
            if not self.contains_pdf:
                print(f"[DEBUG] Downloading images from HTML content...")
                downloaded_images = self.download_images_from_url(driver, download_dir)
            else:
                print(f"[DEBUG] Downloading available PDF...")
                downloaded_images = self.download_available_pdf(final_url, download_dir)
            
            results.update({
                'success': True,
                'downloaded_images': downloaded_images,
                'download_dir': download_dir,
                'week_dates': week_dates
            })
            
        except Exception as e:
            results['error'] = str(e)
            print(f"Error in base scraper: {e}")
        finally:
            driver.quit()
        
        return results
