import os

import requests
from datetime import datetime, timedelta
from typing import Optional, Dict
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from ultralytics import YOLO


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

class WebDriverManager:
    """Manages WebDriver setup and configuration"""

    def __init__(self, headless=True, window_size="960,1080"):
        self.headless = headless
        self.window_size = window_size

    def setup_driver(self):
        options = Options()
        if self.headless:
            # modern headless flag
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"--window-size={self.window_size}")
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)


class ONNXExporter:
    """Handles ONNX export functionality"""

    @staticmethod
    def export_to_onnx(pt_path="models/best.pt", onnx_path="models/best.onnx"):
        """Exports a YOLO model from .pt to .onnx format"""
        model = YOLO(pt_path)
        model.export(format="onnx", dynamic=True)
        print(f"Exported {pt_path} to {onnx_path}")