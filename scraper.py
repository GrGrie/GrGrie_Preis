import time
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

def setup_driver():
    #Setup Chrome driver with options
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
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

def take_screenshots(driver, screenshot_dir):
    """Navigate through prospekt pages and take screenshots"""
    page = 1
    max_pages = 100
    
    while page <= max_pages:
        # Wait for page content to load
        time.sleep(2)
        
        # Find the prospekt content div
        try:
            page_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.page__wrapper"))
            )
            
            # Take screenshot of only the prospekt content
            screenshot_path = os.path.join(screenshot_dir, f"page_{page:02d}.png")
            page_element.screenshot(screenshot_path)
            print(f"✓ Saved page_{page:02d}.png")
            
        except Exception as e:
            print(f"Could not capture page {page}: {e}")
            # Fallback to full page screenshot if page__wrapper not found
            screenshot_path = os.path.join(screenshot_dir, f"page_{page:02d}.png")
            driver.save_screenshot(screenshot_path)
            print(f"✓ Saved page_{page:02d}.png (full page fallback)")
        
        # Find next button
        next_selectors = [
            "div.content_navigation.content_navigation--right button",
            ".content_navigation--right button"
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
            time.sleep(3)
        except Exception as e:
            print(f"Could not navigate to next page: {e}")
            break
    
    return page

def main():
    """Main function to open Lidl prospekt and take screenshots"""
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
        
        # Create screenshot directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_dir = f"lidl_prospekt_screenshots_{timestamp}"
        os.makedirs(screenshot_dir, exist_ok=True)
        print(f"Created directory: {screenshot_dir}")
        
        # Take screenshots
        page_count = take_screenshots(driver, screenshot_dir)
        print(f"✓ Saved {page_count} screenshots to {screenshot_dir}/")
        
        print("Press Enter to close...")
        input()
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()