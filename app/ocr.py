"""
Google Gemini Vision-based product extraction from flyer images.
FREE tier available with generous limits!
"""
from __future__ import annotations
import os
from pathlib import Path
import json, csv
import google.generativeai as genai
from PIL import Image
from typing import Optional
import time


GEN_DEFAULT = "gemini-2.0-flash"
REQUIRED_METHOD = "generateContent"   # Needed for images

class GeminiProductExtractor:
    def __init__(self, api_key: str, model: Optional[str] = None, rate_limit_delay: float = 0.5):
        self.api_key = api_key
        self.rate_limit_delay = rate_limit_delay
        genai.configure(api_key=api_key)
        # prefer passed-in model, else env/default
        preferred = model or GEN_DEFAULT
        self.model, self.model_name = _make_model(preferred)
        print(f"[INFO] Initialized Gemini model: {self.model_name}")

    def _get_prompt(self) -> str:
        """Get the extraction prompt"""
        return """Analyze this product flyer image and extract:
1. Product name (the main product being advertised)
2. Final price (the largest, most prominent price after any discounts)

Return ONLY a JSON object with this exact format:
{
  "name": "product name here",
  "price": 1.23
}

Important rules:
- Extract the actual product name, not just the brand
- Price must be a decimal number (e.g., 0.69 not "0,69€")
- Ignore asterisks (*) after prices
- Return the FINAL discounted price (the biggest, most prominent one)
- If something is missing, use null
- Do NOT include any explanation, ONLY the JSON

Examples:
Image with Pepsi and "0,69€*" → {"name": "Pepsi Cola", "price": 0.69}
Image with ski jacket and "17,99*" → {"name": "Crivit Ski-Jacke", "price": 17.99}
Image with pasta and "1,29*" → {"name": "Combino Fusilli XXL", "price": 1.29}"""
    
    def extract(self, image_path: Path) -> dict:
        """Extract product info from a single image"""
        try:
            # Load image
            img = Image.open(image_path)
            
            # Generate content with Gemini
            response = self.model.generate_content(
                [self._get_prompt(), img],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,  # Low temperature for consistent results
                    max_output_tokens=300,
                )
            )
            
            # Get response text
            response_text = response.text.strip()
            
            # Parse JSON from response
            result = self._parse_response(response_text)
            return result
            
        except Exception as e:
            print(f"[ERROR] Failed to process {image_path.name}: {e}")
            return {"name": "", "price": None, "error": str(e)}
    
    def _parse_response(self, response_text: str) -> dict:
        """Parse JSON from Gemini response"""
        try:
            # Clean markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            result = json.loads(response_text)
            
            return {
                "name": result.get("name", ""),
                "price": result.get("price"),
            }
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse JSON: {e}")
            print(f"[DEBUG] Response was: {response_text}")
            return {"name": "", "price": None, "error": "JSON parse error"}
    
    def process_folder(
        self,
        crops_dir: Path,
        out_json: Path,
        out_csv: Path,
        image_pattern: str = "*.jpg"
    ) -> dict:
        """
        Process all images in a folder.
        
        Args:
            crops_dir: Directory containing cropped product images
            out_json: Output JSON file path
            out_csv: Output CSV file path
            image_pattern: Glob pattern for images (default: *.jpg)
        
        Returns:
            Dictionary with processing statistics
        """
        rows = []
        image_files = sorted(crops_dir.glob(image_pattern))
        
        if not image_files:
            print(f"[WARNING] No images found in {crops_dir} matching pattern {image_pattern}")
            return {"count": 0, "json": str(out_json), "csv": str(out_csv)}
        
        print(f"\n[INFO] Found {len(image_files)} images to process\n")
        
        for idx, image_path in enumerate(image_files, 1):
            print(f"[{idx}/{len(image_files)}] Processing {image_path.name}...")
            
            # Extract product info
            result = self.extract(image_path)
            
            # Create row
            row = {
                "file": image_path.name,
                "name_ocr": result.get("name", ""),
                "price_raw": f"{result.get('price', '')}€".replace(".", ",") if result.get('price') else "",
                "price_eur": result.get("price"),
            }
            
            # Print results
            print(f"  ✓ Name: {row['name_ocr'] or '(not found)'}")
            print(f"  ✓ Price: {row['price_eur']}€" if row['price_eur'] else "  ✗ Price: (not found)")
            
            rows.append(row)
            
            # Rate limiting (avoid hitting API limits)
            if idx < len(image_files):  # Don't delay after last image
                time.sleep(self.rate_limit_delay)
        
        # Write JSON output
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), "utf-8")
        
        # Write CSV output
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["file", "name_ocr", "price_raw", "price_eur"])
            w.writeheader()
            w.writerows(rows)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"[SUCCESS] Processed {len(rows)} images")
        print(f"[SUCCESS] JSON saved to: {out_json}")
        print(f"[SUCCESS] CSV saved to: {out_csv}")
        
        # Statistics
        found_names = sum(1 for r in rows if r['name_ocr'])
        found_prices = sum(1 for r in rows if r['price_eur'])
        print(f"\nStatistics:")
        print(f"  - Names extracted: {found_names}/{len(rows)} ({found_names/len(rows)*100:.1f}%)")
        print(f"  - Prices extracted: {found_prices}/{len(rows)} ({found_prices/len(rows)*100:.1f}%)")
        print(f"{'='*60}\n")
        
        return {
            "count": len(rows),
            "json": str(out_json),
            "csv": str(out_csv),
            "stats": {
                "names_found": found_names,
                "prices_found": found_prices
            }
        }
    

def ocr_folder(crops_dir: Path, out_json: Path, out_csv: Path) -> dict:
    """
   Drop-in replacement for the old OCR entrypoint.
    Reads API key from env and writes the same JSON/CSV files.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Export it or pass via Docker (-e GEMINI_API_KEY=...)."
        )
    extractor = GeminiProductExtractor(
        api_key=api_key,
        model=os.getenv("GEMINI_MODEL", GEN_DEFAULT), 
        rate_limit_delay=float(os.getenv("GEMINI_RATE_DELAY", "0.5")),
    )

    return extractor.process_folder(crops_dir=crops_dir, out_json=out_json, out_csv=out_csv)

def _resolve_model(preferred: str) -> str:
    # Normalize first, prefer free-tier models
    name = preferred.replace("models/", "")
    if name in {"gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-1.5-flash-002"}:
        return "gemini-2.0-flash"          # free-tier replacement
    if name in {"gemini-1.5-pro", "gemini-1.5-pro-002"}:
        return "gemini-2.0-flash"          # or "gemini-2.5-flash-lite"
    if name == "gemini-2.5-flash":
        # 2.5 Flash is great, but to stay free by default, downshift:
        return "gemini-2.5-flash-lite"
    return name

def _make_model(preferred: Optional[str] = None):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    # genai.configure(...) is already called in __init__
    model_name = _resolve_model(preferred or GEN_DEFAULT)
    m = genai.GenerativeModel(model_name)
    return m, model_name