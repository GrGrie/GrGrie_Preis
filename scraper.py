import time
import os
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime, timedelta
# from urllib.parse import urljoin, urlparse

def setup_driver():
    """Setup Chrome driver with options"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=960,1080")
    return webdriver.Chrome(options=options)

def handle_popups(driver):
    """Handle cookie banner and store selection popup"""
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

def find_prospekt(driver):
    """Find and return the first Aktionsprospekt link"""
    selectors = [
        "a.flyer[data-track-name='Aktionsprospekt']",
        "a.flyer[data-track-type='flyer']",
        "a[href*='aktionsprospekt']",
        ".flyer"
    ]
    
    for selector in selectors:
        try:
            link = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
            print(f"✓ Found prospekt: {link.get_attribute('data-track-name') or 'Unknown'}")
            return link.get_attribute("href")
        except TimeoutException:
            continue
    return None

def get_week_folder():
    """Get the current week folder name in format YYYY-MM-DD_YYYY-MM-DD"""
    today = datetime.now()
    # Find Monday of current week
    monday = today - timedelta(days=today.weekday())
    # Find Sunday of current week
    sunday = monday + timedelta(days=6)
    
    week_range = f"{monday.strftime('%Y-%m-%d')}_{sunday.strftime('%Y-%m-%d')}"
    return week_range

def download_image(url, filepath, headers=None):
    """Download image from URL to filepath"""
    try:
        if headers is None:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

def get_high_res_image_url(img_element):
    """Extract the highest resolution image URL from img element"""
    # Try different attributes that might contain high-res URLs
    url_attributes = ['data-src', 'data-original', 'data-large', 'src']
    
    for attr in url_attributes:
        url = img_element.get_attribute(attr)
        if url:
            # Check if it's a data URL or relative URL
            if url.startswith('data:'):
                continue
            if url.startswith('//'):
                url = 'https:' + url
            elif url.startswith('/'):
                url = 'https://www.lidl.de' + url
            
            # Try to find high resolution version by modifying URL
            # Common patterns: replace small dimensions with large ones
            if 'w_' in url and 'h_' in url:
                # Replace width and height parameters
                url = url.replace('w_400', 'w_2000').replace('h_400', 'h_2000')
                url = url.replace('w_600', 'w_2000').replace('h_600', 'h_2000')
                url = url.replace('w_800', 'w_2000').replace('h_800', 'h_2000')
            
            # Remove quality limitations
            if 'q_' in url:
                url = url.replace('q_auto', 'q_100')
            
            return url
    
    return None

def download_page_images(driver, download_dir):
    """Navigate through prospekt pages and download high-res images"""
    page = 1
    max_pages = 100
    downloaded_images = []
    downloaded_urls = set()  # Track downloaded URLs to avoid duplicates
    
    while page <= max_pages:
        time.sleep(3)  # Wait for page to load
        
        try:
            # Wait for page content to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.page__wrapper, .page, .prospekt-page"))
            )
            
            # Find all image elements on the page
            img_selectors = [
                "div.page__wrapper img",
                ".page img",
                ".prospekt-page img",
                "img[src*='prospekt']",
                "img[data-src*='prospekt']",
                "img"  # Fallback to all images
            ]
            
            images_found = False
            page_urls = set()  # Track URLs for this specific page
            
            for selector in img_selectors:
                try:
                    img_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if img_elements:
                        for i, img in enumerate(img_elements):
                            # Skip very small images (likely icons or UI elements)
                            try:
                                width = img.get_attribute('width') or img.get_attribute('naturalWidth')
                                height = img.get_attribute('height') or img.get_attribute('naturalHeight')
                                
                                if width and height:
                                    if int(width) < 200 or int(height) < 200:
                                        continue
                            except:
                                pass
                            
                            img_url = get_high_res_image_url(img)
                            if img_url and img_url not in downloaded_urls and img_url not in page_urls:
                                # Generate filename
                                filename = f"page_{page:02d}.jpg"  # One image per page
                                filepath = os.path.join(download_dir, filename)
                                
                                if download_image(img_url, filepath):
                                    downloaded_images.append(filename)
                                    downloaded_urls.add(img_url)
                                    page_urls.add(img_url)
                                    images_found = True
                                    print(f"  ✓ Downloaded: {filename}")
                                    break  # Only download one image per page
                                else:
                                    print(f"  ✗ Failed to download: {filename}")
                        if images_found:
                            break  # Stop trying other selectors if we found an image
                except Exception as e:
                    continue
            
            if not images_found:
                print(f"  No images found on page {page}") # Shouldn't be the issue except for the last page
            
        except Exception as e:
            print(f"Error processing page {page}: {e}")
        finally:
            # Find and click next button
            next_selectors = [
                "div.content_navigation.content_navigation--right button",
                ".content_navigation--right button",
                "button[aria-label*='next']",
            "button[aria-label*='weiter']"
        ]
        
        next_btn = None
        for selector in next_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for btn in elements:
                    if (btn.is_displayed() and btn.is_enabled() and 
                        not btn.get_attribute("disabled") and 
                        "disabled" not in (btn.get_attribute("class") or "").lower()):
                        next_btn = btn
                        break
                if next_btn:
                    break
            except:
                continue
        
        if not next_btn:
            print("No more pages found")
            break
            
        # Click next button
        try:
            driver.execute_script("arguments[0].click();", next_btn)
            page += 1
        except Exception as e:
            print(f"Could not navigate to next page: {e}")
            break
    
    return downloaded_images

def main():
    """Main function to open Lidl prospekt and download high-res images"""
    driver = setup_driver()
    
    try:
        print("Opening Lidl prospekte page...")
        driver.get("https://www.lidl.de/c/online-prospekte/s10005610")
        
        # Handle popups
        handle_popups(driver)
        
        # Find prospekt
        prospekt_url = find_prospekt(driver)
        if not prospekt_url:
            print("Could not find any prospekt")
            return
        
        # Open prospekt in new tab and close old one
        driver.execute_script(f"window.open('{prospekt_url}', '_blank');")
        driver.switch_to.window(driver.window_handles[1])
        driver.switch_to.window(driver.window_handles[0])
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        print("✓ Opened prospekt in new tab")
        
        time.sleep(5)  # Wait for prospekt to load
        
        # Create download directory
        week_folder = get_week_folder()
        download_dir = os.path.join("data", "originals", week_folder)
        os.makedirs(download_dir, exist_ok=True)
        print(f"Created directory: {download_dir}")
        
        # Download images
        downloaded_images = download_page_images(driver, download_dir)                    
        print(f"✓ Downloaded {len(downloaded_images)} images to {download_dir}/")
        
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()