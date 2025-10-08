import os, argparse, json
from typing import Dict
from utils.utils import ImageDownloader
from utils.utils import WebDriverManager
from utils.utils import DirectoryManager
from utils.scrapers import ScraperFactory 

# Configuration management
class ScraperConfig:
    """Configuration class for scraper settings"""
    
    def __init__(self, config_file: str = "scraper_config.json"):
        self.config_file = config_file
        self.default_config = {
            "headless": True,
            "window_size": "960,1080",
            "download_path": "data/originals",
            "max_pages": 100,
            "timeout": 10
        }
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load configuration from file or use defaults"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return {**self.default_config, **json.load(f)}
            except:
                return self.default_config
        return self.default_config
    
    def save_config(self):
        """Save current configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
            
    @staticmethod
    def get_url_to_scrape(args, parser) -> str:
        """Determine URL to scrape based on CLI arguments and config."""
        if args.url:
            # Custom URL provided
            url = args.url
        elif args.site:
            # Predefined site
            site = args.site.lower()
            if site == 'lidl':
                url = "https://www.lidl.de/c/online-prospekte/s10005610"
            elif site == 'angebote':
                url = "https://angebote.com/lidl/archives?page=1"
            elif site == 'netto':
                url = "https://wochenprospekt.netto-online.de/hz" + DirectoryManager.get_current_week_number() + "_wrse/?storeid=8135"
            elif site == 'aldi':
                url = "https://www.aldi-sued.de/de/angebote/prospekte.html"
        else:
            # No arguments provided - show help
            parser.print_help()
            print("\nExamples:")
            print("  python scraper.py --url 'https://angebote.com/lidl/archives?page=1'")
            print("  python scraper.py --site lidl")
            print("  python scraper.py --url 'https://example.com' --download-path '/custom/path'")
            return ""
        return url

def main():
    """Main function with command line argument support"""
        
    parser = argparse.ArgumentParser(description='Web scraper for prospekt/flyer websites')
    parser.add_argument('--url', '-u', type=str, help='URL to scrape')
    parser.add_argument('--site', '-s', type=str, choices=['lidl', 'angebote', 'netto', 'aldi'], 
                       help='Predefined site to scrape')
    parser.add_argument('--no-headless', action='store_false',
                       help='Run browser in no-headless mode (default is headless)')
    parser.add_argument('--download-path', '-d', type=str, 
                       help='Download path for images')
    parser.add_argument('--num_prospekt', '--num-prospekt',
                        type=int, default=1,
                        help='Which prospekt to download (1-based index)')

    args = parser.parse_args()
    
    # Load configuration
    config = ScraperConfig()
    
    # Override config with command line arguments
    config.config['headless'] = args.no_headless if not args.no_headless else True

    if args.download_path and args.site:
        config.config['download_path'] = os.path.join(args.download_path, args.site)
    elif args.download_path:
        config.config['download_path'] = args.download_path
    elif args.site:
        config.config['download_path'] = os.path.join(config.config['download_path'], args.site)

    if args.site.lower() in ['netto', 'aldi']:
        config.config['window_size'] = "1920,1080"
    
    # Setup components
    driver_manager = WebDriverManager(
        headless=config.config['headless'],
        window_size=config.config['window_size']
    )
    image_downloader = ImageDownloader()
    
    # Determine URLs to scrape
    url = config.get_url_to_scrape(args, parser)
    if not url:
        print("No URLs provided to scrape. Exiting.")
        return
    
    try:
        scraper = ScraperFactory.create_scraper(url, driver_manager, image_downloader, config.config)
        print("[DEBUG] Scraper instance created successfully")
        results = scraper.scrape(url, config.config['download_path'], args.num_prospekt)

        if results['success']:
            print(f"✓ Successfully scraped {len(results['downloaded_images'])} images")
            print(f"  Saved to: {results['download_dir']}")
        else:
            print(f"✗ Scraping failed: {results['error']}")
                
    except ValueError as e:
        print(f"✗ {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")

if __name__ == "__main__":
    main()