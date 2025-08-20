import requests
from typing import Optional, Dict


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
