from selenium import webdriver
from selenium.webdriver.chrome.options import Options

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
