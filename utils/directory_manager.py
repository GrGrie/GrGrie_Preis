from datetime import datetime, timedelta
import os

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
