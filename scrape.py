import os, argparse, json
from typing import Dict
from utils.utils import ImageDownloader
from utils.utils import WebDriverManager
from utils.utils import DirectoryManager
from utils.scrapers import ScraperFactory 

# Configuration management
class ScraperConfig:
    """Configuration class for scraper settings"""
    
    def __init__(self):
        self.config = {
            "headless": True,
            "window_size": "960,1080",
            "download_path": "data/originals",
            "max_pages": 100,
            "timeout": 10,
            "download_pdf_if_available": True,
            "contains_popups": False
        }

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
            elif site == 'kaufland':
                url = "https://filiale.kaufland.de/prospekte.html?intcid=Home+Marketplace_None_None_Leaflets"
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
    parser.add_argument('--site', '-s', type=str,
                        choices=ScraperFactory.supported_sites() + ['all'],
                        help='Predefined site to scrape (or "all")')
    parser.add_argument('--no-headless', action='store_false',
                        help='Run browser in no-headless mode (default is headless)')
    parser.add_argument('--download-path', '-d', type=str,
                        help='Download path for images')

    args = parser.parse_args()
    
    # Load configuration
    config = ScraperConfig()
    
     # Override config with command line arguments
    config.config['headless'] = args.no_headless if not args.no_headless else True
    config.config['download_path'] = args.download_path if args.download_path else config.config['download_path']

    # Setup components
    driver_manager = WebDriverManager(
        headless=config.config['headless'],
        window_size=config.config['window_size']
    )
    image_downloader = ImageDownloader()

    # -------- Case A: --site all --------
    if args.site == 'all':
        overall_ok = True
        per_site_results = {}

        for site_key in ScraperFactory.supported_sites():
            start_url = ScraperFactory.start_url_for(site_key)
            # use per-site subfolder to avoid clashes
            site_out = os.path.join(config.config['download_path'], site_key)
            os.makedirs(site_out, exist_ok=True)

            print(f"\n=== {site_key.upper()} ===")
            try:
                scraper = ScraperFactory.create_scraper(start_url, driver_manager, image_downloader, config.config)
                results = scraper.scrape(start_url, site_out)
                per_site_results[site_key] = results
                if results.get('success'):
                    print(f"✓ {site_key}: {len(results['downloaded_images'])} images -> {results['download_dir']}")
                else:
                    overall_ok = False
                    print(f"✗ {site_key}: {results.get('error')}")
            except Exception as e:
                overall_ok = False
                per_site_results[site_key] = {'success': False, 'error': str(e)}
                print(f"✗ {site_key}: {e}")

        # final summary
        print("\n=== SUMMARY ===")
        for k, v in per_site_results.items():
            if v.get('success'):
                print(f"✓ {k}: {len(v['downloaded_images'])} images -> {v['download_dir']}")
            else:
                print(f"✗ {k}: {v.get('error')}")
        return

    # -------- Case B: single URL or single site (original flow) --------
    # Prefer explicit --url; otherwise build from --site
    if args.url:
        url = args.url
    elif args.site:
        url = ScraperFactory.start_url_for(args.site)
    else:
        # No arguments provided - show help + examples
        parser.print_help()
        print("\nExamples:")
        print("  python scrape.py --site lidl")
        print("  python scrape.py --site all")
        print("  python scrape.py --url 'https://angebote.com/lidl/archives?page=1'")
        return

    # If a single site was requested, put images under /<download-path>/<site>/
    if args.site:
        config.config['download_path'] = os.path.join(config.config['download_path'], args.site)
        os.makedirs(config.config['download_path'], exist_ok=True)

    try:
        scraper = ScraperFactory.create_scraper(url, driver_manager, image_downloader, config.config)
        results = scraper.scrape(url, config.config['download_path'])

        if results['success']:
            print(f"✓ Successfully scraped {len(results['downloaded_images'])} images")
            print(f"✓ Results saved to: {results['download_dir']}")
        else:
            print(f"✗ Scraping failed: {results['error']}")

    except ValueError as e:
        print(f"✗ {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")

if __name__ == "__main__":
    main()