import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import os
from urllib.parse import urljoin
import json

class LidlScraper:
    def __init__(self, headless=True):
        """Initialize the scraper with Chrome options"""
        self.chrome_options = Options()
        if headless:
            self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")
        
        # Install and setup ChromeDriver automatically
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=self.chrome_options)
        self.wait = WebDriverWait(self.driver, 20)
    
    print("Hello!)")
    def scrape_products(self, url):
        """Scrape products from the Lidl page"""
        try:
            print(f"Loading page: {url}")
            self.driver.get(url)
            
            # Wait for the page to load and products to appear
            print("Waiting for products to load...")
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-selector='PRODUCT']"))
            )
            
            # Additional wait to ensure all products are loaded
            time.sleep(3)
            
            # Find all product containers
            products = self.driver.find_elements(By.CSS_SELECTOR, "[data-selector='PRODUCT']")
            print(f"Found {len(products)} products")
            
            scraped_data = []
            
            for i, product in enumerate(products):
                try:
                    product_data = self.extract_product_info(product, i)
                    if product_data:
                        scraped_data.append(product_data)
                except Exception as e:
                    print(f"Error extracting product {i}: {e}")
                    continue
            
            return scraped_data
            
        except Exception as e:
            print(f"Error scraping products: {e}")
            return []
    
    def extract_product_info(self, product_element, index):
        """Extract information from a single product element"""
        product_data = {}
        
        try:
            # Product name/title
            try:
                title_element = product_element.find_element(By.CSS_SELECTOR, ".product-title, .prd-title, h3, h4")
                product_data['title'] = title_element.text.strip()
            except:
                product_data['title'] = f"Product {index + 1}"
            
            # Product price
            try:
                price_element = product_element.find_element(By.CSS_SELECTOR, ".price, .prd-price, [class*='price']")
                product_data['price'] = price_element.text.strip()
            except:
                product_data['price'] = "Price not found"
            
            # Product image
            try:
                img_element = product_element.find_element(By.CSS_SELECTOR, "img")
                img_src = img_element.get_attribute("src") or img_element.get_attribute("data-src")
                if img_src:
                    # Convert relative URLs to absolute
                    product_data['image_url'] = urljoin("https://www.lidl.de", img_src)
                else:
                    product_data['image_url'] = "No image found"
            except:
                product_data['image_url'] = "No image found"
            
            # Product description/details
            try:
                desc_element = product_element.find_element(By.CSS_SELECTOR, ".product-description, .prd-description, .description")
                product_data['description'] = desc_element.text.strip()
            except:
                product_data['description'] = "No description"
            
            # Additional product info
            try:
                info_elements = product_element.find_elements(By.CSS_SELECTOR, ".product-info span, .prd-info span")
                product_data['additional_info'] = [elem.text.strip() for elem in info_elements if elem.text.strip()]
            except:
                product_data['additional_info'] = []
            
            print(f"Extracted: {product_data['title']}")
            return product_data
            
        except Exception as e:
            print(f"Error extracting product info: {e}")
            return None
    
    def download_images(self, products_data, download_folder="lidl_images"):
        """Download product images"""
        if not os.path.exists(download_folder):
            os.makedirs(download_folder)
        
        downloaded_count = 0
        
        for i, product in enumerate(products_data):
            if product['image_url'] and product['image_url'] != "No image found":
                try:
                    response = requests.get(product['image_url'], timeout=10)
                    if response.status_code == 200:
                        # Create safe filename
                        safe_title = "".join(c for c in product['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        filename = f"{i+1:03d}_{safe_title[:50]}.jpg"
                        filepath = os.path.join(download_folder, filename)
                        
                        with open(filepath, 'wb') as f:
                            f.write(response.content)
                        
                        product['local_image_path'] = filepath
                        downloaded_count += 1
                        print(f"Downloaded: {filename}")
                    
                except Exception as e:
                    print(f"Error downloading image for {product['title']}: {e}")
        
        print(f"Downloaded {downloaded_count} images to {download_folder}/")
        return downloaded_count
    
    def save_to_json(self, products_data, filename="lidl_products.json"):
        """Save scraped data to JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(products_data, f, indent=2, ensure_ascii=False)
            print(f"Data saved to {filename}")
        except Exception as e:
            print(f"Error saving to JSON: {e}")
    
    def print_products_summary(self, products_data):
        """Print a summary of scraped products"""
        print(f"\n=== SCRAPED PRODUCTS SUMMARY ===")
        print(f"Total products found: {len(products_data)}")
        print("-" * 50)
        
        for i, product in enumerate(products_data, 1):
            print(f"{i}. {product['title']}")
            print(f"   Price: {product['price']}")
            print(f"   Image: {product['image_url'][:80]}{'...' if len(product['image_url']) > 80 else ''}")
            if product.get('description') and product['description'] != "No description":
                print(f"   Description: {product['description'][:100]}{'...' if len(product['description']) > 100 else ''}")
            print()
    
    def close(self):
        """Close the browser driver"""
        if self.driver:
            self.driver.quit()

def main():
    """Main function to run the scraper"""
    url = "https://www.lidl.de/c/billiger-montag/a10006065"
    
    scraper = LidlScraper(headless=False)  # Set to True for headless mode
    
    try:
        # Scrape products
        products = scraper.scrape_products(url)
        
        if products:
            # Print summary
            scraper.print_products_summary(products)
            
            # Save to JSON
            scraper.save_to_json(products)
            
            # Download images (optional)
            download_choice = input("\nDo you want to download product images? (y/n): ").lower()
            if download_choice == 'y':
                scraper.download_images(products)
        else:
            print("No products found or error occurred during scraping.")
    
    except KeyboardInterrupt:
        print("\nScraping interrupted by user.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        scraper.close()

if __name__ == "__main__":
    main()