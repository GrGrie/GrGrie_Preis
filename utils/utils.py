import os
import sys
import shutil
import re
from pathlib import Path
try:
    import onnx
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def clean_price(text):
    """Extract and format price from OCR text."""
    if not text: return ""
    text = text.replace("€", "").strip()
    match = re.search(r'(\d+)[.,](\d{2})', text)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return text

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
        
        # Check if the directory already exists
        if not os.path.exists(download_dir):
            os.makedirs(download_dir, exist_ok=True)
        else:
            print(f"[DEBUG] Directory already exists: {download_dir}")
            
        return download_dir

    @staticmethod
    def get_current_week_number() -> str:
        """Get current week number"""
        now = datetime.now()
        return str(now.isocalendar()[1])
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
        # Suppress GCM/GCM registration errors
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/140.0.0.0 Safari/537.36")
        options.add_argument(f"--user-agent={ua}")
        
        # Additional useful options for scraping
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument('--log-level=3')  # Only show fatal errors

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
        
        # Check if the directory already exists
        if not os.path.exists(download_dir):
            os.makedirs(download_dir, exist_ok=True)
        else:
            print(f"[DEBUG] Directory already exists: {download_dir}")
            
        return download_dir

    @staticmethod
    def get_current_week_number() -> str:
        """Get current week number"""
        now = datetime.now()
        return str(now.isocalendar()[1])
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
        # Suppress GCM/GCM registration errors
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/140.0.0.0 Safari/537.36")
        options.add_argument(f"--user-agent={ua}")
        
        # Additional useful options for scraping
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument('--log-level=3')  # Only show fatal errors
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"--window-size={self.window_size}")
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

class ONNXExporter:
    """Handles ONNX export and compatibility checks"""

    @staticmethod
    def export_to_onnx(pt_path="models/best.pt", onnx_path="models/best.onnx", opset=11):
        """Exports a YOLO model from .pt to .onnx format"""
        try:
            from ultralytics import YOLO
            model = YOLO(pt_path)
            model.export(format="onnx", dynamic=True, simplify=True, opset=opset)
            print(f"[INFO] Exported {pt_path} to {onnx_path}")
            
            # Ensure compatibility (patch IR version if needed)
            ONNXExporter.ensure_model_compatibility(str(onnx_path))
            
            return True
        except ImportError:
            print(f"[ERROR] 'ultralytics' not installed. Cannot export from .pt.")
            return False
        except Exception as e:
            print(f"[ERROR] Export failed: {e}")
            return False

    @staticmethod
    def ensure_model_compatibility(onnx_path: str):
        """
        Ensures the ONNX model exists and has a compatible IR version.
        If ONNX is missing but .pt exists, exports it.
        If IR version is too high, patches it.
        """
        onnx_path = Path(onnx_path)
        pt_path = onnx_path.with_suffix('.pt')
        
        # 1. Export if missing
        if not onnx_path.exists():
            if pt_path.exists():
                print(f"[INFO] ONNX model not found, exporting from {pt_path}...")
                if not ONNXExporter.export_to_onnx(str(pt_path), str(onnx_path)):
                    sys.exit(1)
            else:
                print(f"[ERROR] Model not found: {onnx_path} (and no source .pt found)")
                sys.exit(1)

        # 2. Check and Patch IR Version
        if HAS_ONNX:
            try:
                model = onnx.load(str(onnx_path))
                current_ir = model.ir_version
                TARGET_IR = 8 
                
                if current_ir > 11: 
                    print(f"[WARN] Model IR version is {current_ir} (high). Patching to IR {TARGET_IR}...")
                    
                    backup_path = onnx_path.with_suffix('.onnx.bak')
                    if not backup_path.exists():
                        shutil.copy2(onnx_path, backup_path)
                    
                    model.ir_version = TARGET_IR
                    onnx.save(model, str(onnx_path))
                    print(f"[INFO] Patched model saved to {onnx_path}")
                else:
                    print(f"[INFO] Model IR version {current_ir} is compatible.")
            except Exception as e:
                print(f"[WARN] Failed to check/patch ONNX model: {e}")
        else:
            print("[WARN] 'onnx' module not found. Skipping IR version check/patching.")